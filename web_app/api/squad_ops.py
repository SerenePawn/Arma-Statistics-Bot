from typing import Any

import asyncpg
from aiogram import Bot

from logic.squad_requests import db as squad_requests_db
from logic.games import db as games_db
from logic.schedules import db as schedules_db
from logic.schedules.models import SchedulePresetForm
from logic.schedules.recurrence import RecurrenceType
from logic.squad_requests.models import RequestStatus, RequestType
from logic.squads.chat_lookup import create_squad_for_chat, get_telegram_chat_id_by_squad_id
from logic.squads import db as squads_db
from logic.squads.access import (
    resolve_squad_access,
    squad_relation_for_ui,
)
from logic.telegram.permissions import ADMIN_STATUSES, get_chat_member_status_and_display_name, is_chat_admin
from web_app.core.permissions import SquadPermissionError
from web_app.core.security import TelegramUser

from . import repository


async def get_squad_chat_id(conn: asyncpg.Connection, squad_id: int) -> int | None:
    return await get_telegram_chat_id_by_squad_id(conn, squad_id)


async def delete_player_schedule_data(conn: asyncpg.Connection, player_id: int) -> None:
    await conn.execute("DELETE FROM attendances WHERE player_id = $1", player_id)
    await conn.execute("DELETE FROM schedules WHERE player_id = $1", player_id)


async def enrich_me(
    conn: asyncpg.Connection,
    bot: Bot,
    me: dict[str, Any],
    telegram_user: TelegramUser,
) -> dict[str, Any]:
    primary_squad_id = me.get("primary_squad_id")
    launch_source = telegram_user.launch_source
    launch_squad_id = None
    can_create_squad = False

    if launch_source == "squad_chat" and telegram_user.launch_chat_id is not None:
        launch_squad = await repository.get_squad_by_telegram_chat_id(conn, telegram_user.launch_chat_id)
        launch_squad_id = launch_squad["id"] if launch_squad else None
        if launch_squad_id is None:
            can_create_squad = await is_chat_admin(
                bot,
                telegram_user.launch_chat_id,
                me["telegram_id"],
            )

    context_squad_id = (
        launch_squad_id
        if launch_source == "squad_chat" and launch_squad_id is not None
        else primary_squad_id
    )

    has_squad_membership = any(
        membership.get("squad_id") is not None
        for membership in me.get("memberships", [])
    )
    if context_squad_id is None and not has_squad_membership:
        solo = await repository.get_solo_player(conn, me["telegram_id"])
        if solo:
            friend_squad_ids = await squads_db.get_squad_ids_for_friend_player(conn, solo["id"])
            if friend_squad_ids:
                if launch_squad_id in friend_squad_ids:
                    context_squad_id = launch_squad_id
                else:
                    context_squad_id = friend_squad_ids[0]

    is_squad_admin = False
    is_admin_of_squad_id = None
    squad_relation = None
    default_game_id = None

    for membership in me.get("memberships", []):
        squad_id = membership.get("squad_id")
        if squad_id is None:
            continue
        access = await resolve_squad_access(conn, bot, me["telegram_id"], squad_id)
        if access == "admin":
            is_admin_of_squad_id = squad_id
            if squad_id == primary_squad_id:
                is_squad_admin = True

    if context_squad_id is not None:
        access = await resolve_squad_access(conn, bot, me["telegram_id"], context_squad_id)
        pending = await squad_requests_db.get_pending(conn, context_squad_id, me["telegram_id"])
        squad_relation = squad_relation_for_ui(access, pending is not None)
        if context_squad_id == primary_squad_id:
            is_squad_admin = access == "admin"

        context_squad = await repository.get_squad(conn, context_squad_id)
        if context_squad and context_squad.get("games"):
            main_game_ids = context_squad.get("main_game_ids") or []
            default_game_id = main_game_ids[0] if main_game_ids else context_squad["games"][0]["id"]

    return me | {
        "is_squad_admin": is_squad_admin,
        "is_admin_of_squad_id": is_admin_of_squad_id,
        "squad_relation": squad_relation,
        "launch_source": launch_source,
        "launch_squad_id": launch_squad_id,
        "can_create_squad": can_create_squad,
        "context_squad_id": context_squad_id,
        "default_game_id": default_game_id,
    }


async def _add_user_to_squad(
    conn: asyncpg.Connection,
    telegram_user: TelegramUser,
    squad_id: int,
    *,
    set_primary: bool,
) -> None:
    if await repository.get_player_in_squad(conn, telegram_user.id, squad_id):
        return

    solo = await repository.get_solo_player(conn, telegram_user.id)
    if solo:
        data: dict[str, Any] = {
            "telegram_id": solo["telegram_id"],
            "telegram_tag": solo["telegram_tag"],
            "name": solo["name"],
            "squad_id": squad_id,
        }
        solo_games = solo.get("games") or []
        if solo_games:
            data["games_ids"] = [game["id"] for game in solo_games]
    else:
        name = telegram_user.display_name.strip()
        if not name:
            raise ValueError("User is not registered")
        data = {
            "telegram_id": telegram_user.id,
            "telegram_tag": telegram_user.tag,
            "name": name,
            "squad_id": squad_id,
        }

    squad = await repository.get_squad(conn, squad_id)
    await repository.apply_chatters_id_for_player(
        conn,
        data,
        squad.get("chatters_id") if squad else None,
    )
    data["id"] = await repository.next_id(conn, "players")
    columns = list(data)
    placeholders = [f"${idx}" for idx in range(1, len(columns) + 1)]
    await conn.execute(
        f"INSERT INTO players ({', '.join(columns)}) VALUES ({', '.join(placeholders)})",
        *[data[column] for column in columns],
    )

    if set_primary:
        await repository.set_primary_squad_id(conn, telegram_user.id, squad_id)


async def create_squad_from_launch_chat(
    conn: asyncpg.Connection,
    telegram_user: TelegramUser,
    name: str,
    tags: str,
) -> dict[str, Any]:
    if telegram_user.launch_chat_id is None:
        raise ValueError("Launch chat is required")

    existing = await repository.get_squad_by_telegram_chat_id(conn, telegram_user.launch_chat_id)
    if existing:
        raise ValueError("squad_exists")

    clean_name = name.strip()
    clean_tags = tags.strip()
    if not clean_name or not clean_tags:
        raise ValueError("Squad name and tags are required")

    squad_id = await create_squad_for_chat(
        conn,
        telegram_user.launch_chat_id,
        clean_name,
        clean_tags,
    )
    await _add_user_to_squad(conn, telegram_user, squad_id, set_primary=True)
    squad = await repository.get_squad(conn, squad_id)
    if not squad:
        raise ValueError("Squad not found")
    return squad


async def set_primary_squad_for_user(
    conn: asyncpg.Connection,
    telegram_id: int,
    squad_id: int | None,
) -> int | None:
    return await repository.set_primary_squad_id(conn, telegram_id, squad_id)


async def list_squad_members(
    conn: asyncpg.Connection,
    bot: Bot,
    squad_id: int,
) -> list[dict[str, Any]]:
    chat_id = await get_squad_chat_id(conn, squad_id)
    players = await players_db_get_by_squad(conn, squad_id)
    result = []
    for player in players:
        is_admin = False
        display_name = ""
        if chat_id is not None:
            status, display_name = await get_chat_member_status_and_display_name(
                bot,
                chat_id,
                player["telegram_id"],
            )
            is_admin = status in ADMIN_STATUSES if status is not None else False
        result.append(
            {
                "id": player["id"],
                "telegram_id": player["telegram_id"],
                "display_name": display_name,
                "name": player["name"],
                "is_telegram_admin": is_admin,
            }
        )
    return result


async def players_db_get_by_squad(conn: asyncpg.Connection, squad_id: int) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT id, telegram_id, name
        FROM players
        WHERE squad_id = $1
        ORDER BY lower(name)
        """,
        squad_id,
    )
    return [dict(row) for row in rows]


async def remove_squad_member(
    conn: asyncpg.Connection,
    bot: Bot,
    squad_id: int,
    target_telegram_id: int,
) -> None:
    target = await repository.get_player_in_squad(conn, target_telegram_id, squad_id)
    if not target:
        raise SquadPermissionError("target_not_in_squad")

    chat_id = await get_squad_chat_id(conn, squad_id)
    if chat_id is not None and await is_chat_admin(bot, chat_id, target_telegram_id):
        raise SquadPermissionError("cannot_remove_admin")

    await delete_player_schedule_data(conn, target["id"])
    await conn.execute(
        "DELETE FROM players WHERE telegram_id = $1 AND squad_id = $2",
        target_telegram_id,
        squad_id,
    )
    await repository.reassign_primary_after_leave(conn, target_telegram_id, squad_id)


async def list_squad_friends(
    conn: asyncpg.Connection,
    squad_id: int,
) -> list[dict[str, Any]]:
    friends_ids = await squads_db.get_friends_ids(conn, squad_id)
    if not friends_ids:
        return []
    rows = await conn.fetch(
        """
        SELECT id, telegram_id, name
        FROM players
        WHERE id = ANY($1::int[])
        ORDER BY lower(name)
        """,
        friends_ids,
    )
    return [dict(row) for row in rows]


async def remove_squad_friend(
    conn: asyncpg.Connection,
    squad_id: int,
    player_id: int,
) -> None:
    friends_ids = await squads_db.get_friends_ids(conn, squad_id)
    if player_id not in friends_ids:
        raise SquadPermissionError("target_not_in_squad")
    await squads_db.remove_friend(conn, squad_id, player_id)


async def create_squad_request(
    conn: asyncpg.Connection,
    telegram_user: TelegramUser,
    squad_id: int,
    request_type: RequestType,
) -> dict[str, Any]:
    solo = await repository.get_solo_player(conn, telegram_user.id)
    if not solo:
        raise ValueError("Player not found")

    squad = await repository.get_squad(conn, squad_id)
    if not squad:
        raise ValueError("Squad not found")

    request = await squad_requests_db.create(
        conn,
        squad_id,
        telegram_user.id,
        solo["id"],
        request_type,
    )
    return request.model_dump()


async def accept_squad_request(
    conn: asyncpg.Connection,
    squad_id: int,
    request_id: int,
) -> None:
    request = await squad_requests_db.get_by_id(conn, request_id, squad_id)
    if not request or request.status != RequestStatus.PENDING:
        raise ValueError("Request not found")

    if request.request_type == RequestType.JOIN:
        solo = await repository.get_solo_player(conn, request.telegram_id)
        if not solo:
            raise ValueError("Player not found")
        if await repository.get_player_in_squad(conn, request.telegram_id, squad_id):
            raise ValueError("already_member")

        friends_ids = await squads_db.get_friends_ids(conn, squad_id)
        if solo["id"] in friends_ids:
            await squads_db.remove_friend(conn, squad_id, solo["id"])

        data: dict[str, Any] = {
            "telegram_id": solo["telegram_id"],
            "telegram_tag": solo["telegram_tag"],
            "name": solo["name"],
            "squad_id": squad_id,
        }
        solo_games = solo.get("games") or []
        if solo_games:
            data["games_ids"] = [game["id"] for game in solo_games]
        squad = await repository.get_squad(conn, squad_id)
        await repository.apply_chatters_id_for_player(conn, data, squad.get("chatters_id") if squad else None)
        data["id"] = await repository.next_id(conn, "players")
        columns = list(data)
        placeholders = [f"${idx}" for idx in range(1, len(columns) + 1)]
        await conn.execute(
            f"INSERT INTO players ({', '.join(columns)}) VALUES ({', '.join(placeholders)})",
            *[data[column] for column in columns],
        )
        primary = await repository.get_primary_squad_id(conn, request.telegram_id)
        if primary is None:
            await repository.set_primary_squad_id(conn, request.telegram_id, squad_id)
    else:
        if await repository.get_player_in_squad(conn, request.telegram_id, squad_id):
            raise ValueError("already_member")
        await squads_db.add_friend(conn, squad_id, request.player_id)

    await squad_requests_db.set_status(conn, request_id, RequestStatus.ACCEPTED)


async def reject_squad_request(
    conn: asyncpg.Connection,
    squad_id: int,
    request_id: int,
) -> None:
    request = await squad_requests_db.get_by_id(conn, request_id, squad_id)
    if not request or request.status != RequestStatus.PENDING:
        raise ValueError("Request not found")
    await squad_requests_db.set_status(conn, request_id, RequestStatus.REJECTED)


async def block_squad_request(
    conn: asyncpg.Connection,
    squad_id: int,
    request_id: int,
) -> None:
    request = await squad_requests_db.get_by_id(conn, request_id, squad_id)
    if not request or request.status != RequestStatus.PENDING:
        raise ValueError("Request not found")
    await squad_requests_db.set_status(conn, request_id, RequestStatus.BLOCKED)


async def unblock_squad_user(
    conn: asyncpg.Connection,
    squad_id: int,
    target_telegram_id: int,
) -> None:
    if not await squad_requests_db.unblock(conn, squad_id, target_telegram_id):
        raise SquadPermissionError("not_blocked")


async def set_squad_games_admin(
    conn: asyncpg.Connection,
    squad_id: int,
    game_ids: list[int],
    main_game_ids: list[int] | None = None,
) -> dict[str, Any]:
    if main_game_ids is None:
        updated_game_ids = await squads_db.set_game_ids(conn, squad_id, game_ids)
    else:
        updated_game_ids, _ = await squads_db.set_game_config(conn, squad_id, game_ids, main_game_ids)
    squad = await repository.get_squad(conn, squad_id)
    if not squad:
        raise ValueError("Squad not found")
    return squad | {"games": await repository.resolve_games(conn, updated_game_ids)}


async def add_squad_game_admin(
    conn: asyncpg.Connection,
    squad_id: int,
    title: str,
) -> dict[str, Any]:
    clean_title = title.strip()
    if not clean_title:
        raise ValueError("Game title is required")
    game = await games_db.get_or_create_by_title(conn, clean_title)
    squad = await repository.get_squad(conn, squad_id)
    if not squad:
        raise ValueError("Squad not found")

    game_ids = [entry["id"] for entry in squad.get("games", [])]
    if game.id not in game_ids:
        game_ids.append(game.id)
    main_game_ids = squad.get("main_game_ids") or []
    await squads_db.set_game_config(conn, squad_id, game_ids, main_game_ids)
    refreshed = await repository.get_squad(conn, squad_id)
    if not refreshed:
        raise ValueError("Squad not found")
    return refreshed


async def _has_squad_game_dependencies(
    conn: asyncpg.Connection,
    squad_id: int,
    game_id: int,
) -> bool:
    row = await conn.fetchrow(
        """
        SELECT EXISTS(
            SELECT 1
            FROM schedules_presets
            WHERE squad_id = $1 AND game_id = $2
        ) AS has_links
        """,
        squad_id,
        game_id,
    )
    return bool(row and row["has_links"])


async def remove_squad_game_admin(
    conn: asyncpg.Connection,
    squad_id: int,
    game_id: int,
) -> dict[str, Any]:
    squad = await repository.get_squad(conn, squad_id)
    if not squad:
        raise ValueError("Squad not found")

    game_ids = [entry["id"] for entry in squad.get("games", [])]
    if game_id not in game_ids:
        return squad
    if await _has_squad_game_dependencies(conn, squad_id, game_id):
        raise SquadPermissionError("game_has_dependencies")

    updated_game_ids = [existing_id for existing_id in game_ids if existing_id != game_id]
    main_game_ids = [existing_id for existing_id in (squad.get("main_game_ids") or []) if existing_id != game_id]
    await squads_db.set_game_config(conn, squad_id, updated_game_ids, main_game_ids)
    refreshed = await repository.get_squad(conn, squad_id)
    if not refreshed:
        raise ValueError("Squad not found")
    return refreshed


def _validate_preset_game(conn_squad_games: list[dict[str, Any]], game_id: int | None) -> None:
    if game_id is None:
        return
    squad_game_ids = {entry["id"] for entry in conn_squad_games}
    if game_id not in squad_game_ids:
        raise ValueError("Game is not linked to this squad")


def _preset_payload_to_form(payload: dict[str, Any]) -> SchedulePresetForm:
    recurrence_type = RecurrenceType(payload.get("recurrence_type", RecurrenceType.WEEKLY))
    game_day_of_week = payload.get("game_day_of_week", 0)
    if recurrence_type == RecurrenceType.ONCE and payload.get("recurrence_date"):
        from datetime import date

        recurrence_date = payload["recurrence_date"]
        if isinstance(recurrence_date, str):
            recurrence_date = date.fromisoformat(recurrence_date)
        game_day_of_week = recurrence_date.weekday()
    return SchedulePresetForm(
        name=payload["title"],
        game_id=payload.get("game_id"),
        game_time=payload["game_time"],
        game_day_of_week=game_day_of_week,
        recurrence_type=recurrence_type,
        recurrence_date=payload.get("recurrence_date"),
        day_of_month=payload.get("day_of_month"),
    )


async def list_schedule_presets_admin(
    conn: asyncpg.Connection,
    squad_id: int,
) -> list[dict[str, Any]]:
    return await repository.list_presets_for_squad(conn, squad_id)


async def create_schedule_preset_admin(
    conn: asyncpg.Connection,
    squad_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    squad = await repository.get_squad(conn, squad_id)
    if not squad:
        raise ValueError("Squad not found")
    _validate_preset_game(squad.get("games", []), payload.get("game_id"))
    form = _preset_payload_to_form(payload)
    preset_id = await schedules_db.create_preset(
        conn,
        squad_id,
        form,
        chatters_id=squad.get("chatters_id"),
    )
    presets = await repository.list_presets_for_squad(conn, squad_id)
    created = next((preset for preset in presets if preset["id"] == preset_id), None)
    if not created:
        raise ValueError("Failed to create schedule preset")
    return created


async def update_schedule_preset_admin(
    conn: asyncpg.Connection,
    squad_id: int,
    preset_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    presets = await repository.list_presets_for_squad(conn, squad_id)
    if preset_id not in {preset["id"] for preset in presets}:
        raise ValueError("Schedule preset not found")
    squad = await repository.get_squad(conn, squad_id)
    if not squad:
        raise ValueError("Squad not found")
    if "game_id" in payload:
        _validate_preset_game(squad.get("games", []), payload.get("game_id"))

    merged = next(preset for preset in presets if preset["id"] == preset_id) | payload
    if "title" in payload:
        merged["title"] = payload["title"]
    game_time = merged.get("game_time")
    if hasattr(game_time, "strftime"):
        game_time = game_time.strftime("%H:%M:00")
    elif isinstance(game_time, str) and len(game_time) == 5:
        game_time = f"{game_time}:00"
    form = _preset_payload_to_form(
        {
            "title": merged.get("title") or "Событие",
            "game_id": merged.get("game_id"),
            "game_time": game_time or "20:00:00",
            "game_day_of_week": merged.get("game_day_of_week", 0),
            "recurrence_type": merged.get("recurrence_type", RecurrenceType.WEEKLY),
            "recurrence_date": merged.get("recurrence_date"),
            "day_of_month": merged.get("day_of_month"),
        }
    )
    await schedules_db.update_preset(
        conn,
        preset_id,
        name=form.name,
        game_id=form.game_id,
        game_time=form.game_time,
        game_day_of_week=form.game_day_of_week,
        recurrence_type=form.recurrence_type.value,
        recurrence_date=form.recurrence_date,
        day_of_month=form.day_of_month,
    )
    refreshed = await repository.list_presets_for_squad(conn, squad_id)
    updated = next((preset for preset in refreshed if preset["id"] == preset_id), None)
    if not updated:
        raise ValueError("Schedule preset not found")
    return updated


async def delete_schedule_preset_admin(
    conn: asyncpg.Connection,
    squad_id: int,
    preset_id: int,
) -> None:
    await schedules_db.delete_preset(conn, preset_id, squad_id)
