from datetime import date, timedelta
from json import dumps
from pathlib import Path
from time import time
from typing import Any

import asyncpg
from asyncpg import UndefinedTableError

from .schemas import AttendStatus, GameOut
from ..core.security import TelegramUser
from logic.games import db as games_db
from logic.games.models import parse_games_ids
from logic.players import db as players_db
from logic.schedules.recurrence import is_preset_active_this_week, sort_key_for_week
from logic.squads import db as squads_db

_columns_cache: dict[str, set[str]] = {}
_DEBUG_LOG = Path(__file__).resolve().parents[2] / ".cursor" / "debug-3243df.log"


def _debug_log(hypothesis_id: str, location: str, message: str, data: dict[str, Any] | None = None) -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": "3243df",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time() * 1000),
        }
        _DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _DEBUG_LOG.open("a", encoding="utf-8") as log_file:
            log_file.write(dumps(payload, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass
    # #endregion


async def table_columns(conn: asyncpg.Connection, table: str) -> set[str]:
    if table in _columns_cache:
        return _columns_cache[table]

    rows = await conn.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = $1
        """,
        table,
    )
    _columns_cache[table] = {row["column_name"] for row in rows}
    return _columns_cache[table]


async def next_id(conn: asyncpg.Connection, table: str) -> int:
    row = await conn.fetchrow(f"SELECT COALESCE(MAX(id), 0) + 1 AS id FROM {table}")
    return int(row["id"])


def split_tags(tags: str | list[str] | None) -> list[str]:
    if not tags:
        return []
    if isinstance(tags, list):
        return tags
    return [tag.strip() for tag in tags.split(",") if tag.strip()]


def games_out(games: list) -> list[dict[str, Any]]:
    return [GameOut.model_validate(game.model_dump()).model_dump() for game in games]


async def resolve_games(conn: asyncpg.Connection, game_ids: list[int]) -> list[dict[str, Any]]:
    if not game_ids:
        return []
    return games_out(await games_db.get_by_ids(conn, game_ids))


def _json_ids_field(table_alias: str, columns: set[str], column_name: str) -> str:
    if column_name in columns:
        return f"COALESCE({table_alias}.{column_name}, '[]'::jsonb) AS {column_name}"
    return f"'[]'::jsonb AS {column_name}"


def _games_ids_field(table_alias: str, columns: set[str]) -> str:
    return _json_ids_field(table_alias, columns, "games_ids")


def _main_game_ids_field(table_alias: str, columns: set[str]) -> str:
    return _json_ids_field(table_alias, columns, "main_game_ids")


async def _attach_games(conn: asyncpg.Connection, row: dict[str, Any]) -> dict[str, Any]:
    game_ids = parse_games_ids(row.get("games_ids"))
    main_game_ids = parse_games_ids(row.get("main_game_ids"))
    return row | {
        "games": await resolve_games(conn, game_ids),
        "main_game_ids": [game_id for game_id in main_game_ids if game_id in game_ids],
    }


async def list_games(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    return games_out(await games_db.get_list(conn))


async def list_squads(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    squad_cols = await table_columns(conn, "squads")
    games_ids_field = _games_ids_field("s", squad_cols)
    main_game_ids_field = _main_game_ids_field("s", squad_cols)
    if "chatters_id" in squad_cols:
        rows = await conn.fetch(
            f"""
            SELECT s.id, s.name, s.tags, s.chatters_id, {games_ids_field}, {main_game_ids_field}
            FROM squads AS s
            ORDER BY lower(s.name)
            """
        )
    else:
        rows = await conn.fetch(
            f"""
            SELECT s.id, s.name, s.tags, NULL::integer AS chatters_id, {games_ids_field}, {main_game_ids_field}
            FROM squads AS s
            ORDER BY lower(s.name)
            """
        )

    result = []
    for row in rows:
        squad = dict(row) | {"tags": split_tags(row["tags"])}
        result.append(await _attach_games(conn, squad))
    return result


async def get_squad(conn: asyncpg.Connection, squad_id: int) -> dict[str, Any] | None:
    squad_cols = await table_columns(conn, "squads")
    games_ids_field = _games_ids_field("s", squad_cols)
    main_game_ids_field = _main_game_ids_field("s", squad_cols)
    if "chatters_id" in squad_cols:
        row = await conn.fetchrow(
            f"""
            SELECT s.id, s.name, s.tags, s.chatters_id, {games_ids_field}, {main_game_ids_field}
            FROM squads AS s
            WHERE s.id = $1
            """,
            squad_id,
        )
    else:
        row = await conn.fetchrow(
            f"""
            SELECT s.id, s.name, s.tags, NULL::integer AS chatters_id, {games_ids_field}, {main_game_ids_field}
            FROM squads AS s
            WHERE s.id = $1
            """,
            squad_id,
        )

    if not row:
        return None
    squad = dict(row) | {"tags": split_tags(row["tags"])}
    return await _attach_games(conn, squad)


async def get_squad_by_telegram_chat_id(conn: asyncpg.Connection, chat_id: int) -> dict[str, Any] | None:
    from logic.squads.chat_lookup import get_squad_id_by_telegram_chat_id

    squad_id = await get_squad_id_by_telegram_chat_id(conn, chat_id)
    if squad_id is None:
        return None
    return await get_squad(conn, squad_id)


async def list_memberships(conn: asyncpg.Connection, telegram_id: int) -> list[dict[str, Any]]:
    player_cols = await table_columns(conn, "players")
    chatters_field = "p.chatters_id" if "chatters_id" in player_cols else "NULL::integer"
    games_ids_field = _games_ids_field("p", player_cols)
    rows = await conn.fetch(
        f"""
        SELECT
            p.id,
            p.squad_id,
            p.telegram_id,
            p.telegram_tag,
            p.name,
            p.created_at,
            {chatters_field} AS chatters_id,
            {games_ids_field},
            s.name AS squad_name
        FROM players AS p
            LEFT JOIN squads AS s ON s.id = p.squad_id
        WHERE p.telegram_id = $1
        ORDER BY p.squad_id NULLS FIRST, lower(s.name), p.id
        """,
        telegram_id,
    )
    result = []
    for row in rows:
        result.append(await _attach_games(conn, dict(row)))
    return result


async def get_player_in_squad(
    conn: asyncpg.Connection,
    telegram_id: int,
    squad_id: int,
) -> dict[str, Any] | None:
    player_cols = await table_columns(conn, "players")
    chatters_field = "p.chatters_id" if "chatters_id" in player_cols else "NULL::integer"
    games_ids_field = _games_ids_field("p", player_cols)
    row = await conn.fetchrow(
        f"""
        SELECT
            p.id,
            p.squad_id,
            p.telegram_id,
            p.telegram_tag,
            p.name,
            p.created_at,
            {chatters_field} AS chatters_id,
            {games_ids_field},
            s.name AS squad_name
        FROM players AS p
            LEFT JOIN squads AS s ON s.id = p.squad_id
        WHERE p.telegram_id = $1 AND p.squad_id = $2
        """,
        telegram_id,
        squad_id,
    )
    return await _attach_games(conn, dict(row)) if row else None


async def get_solo_player(conn: asyncpg.Connection, telegram_id: int) -> dict[str, Any] | None:
    player_cols = await table_columns(conn, "players")
    chatters_field = "p.chatters_id" if "chatters_id" in player_cols else "NULL::integer"
    games_ids_field = _games_ids_field("p", player_cols)
    row = await conn.fetchrow(
        f"""
        SELECT
            p.id,
            p.squad_id,
            p.telegram_id,
            p.telegram_tag,
            p.name,
            p.created_at,
            {chatters_field} AS chatters_id,
            {games_ids_field},
            NULL::text AS squad_name
        FROM players AS p
        WHERE p.telegram_id = $1 AND p.squad_id IS NULL
        """,
        telegram_id,
    )
    return await _attach_games(conn, dict(row)) if row else None


async def is_column_nullable(conn: asyncpg.Connection, table: str, column: str) -> bool:
    row = await conn.fetchrow(
        """
        SELECT is_nullable
        FROM information_schema.columns
        WHERE table_schema = current_schema()
            AND table_name = $1
            AND column_name = $2
        """,
        table,
        column,
    )
    return bool(row and row["is_nullable"] == "YES")


async def get_default_chatters_id(conn: asyncpg.Connection) -> int | None:
    player_cols = await table_columns(conn, "players")
    reason = "no_chatters_id_column_on_players"
    result: int | None = None

    if "chatters_id" not in player_cols:
        # #region agent log
        _debug_log(
            "F",
            "repository.get_default_chatters_id",
            "resolved chatters_id",
            {"chatters_id": None, "reason": reason},
        )
        # #endregion
        return None

    lookups: list[tuple[str, str, str]] = [
        ("chatters", "SELECT id AS chatters_id FROM chatters ORDER BY id LIMIT 1", "from_chatters_table"),
        ("squads", "SELECT chatters_id FROM squads WHERE chatters_id IS NOT NULL ORDER BY id LIMIT 1", "from_squads"),
        (
            "schedules_presets",
            "SELECT chatters_id FROM schedules_presets WHERE chatters_id IS NOT NULL ORDER BY id LIMIT 1",
            "from_presets",
        ),
        ("players", "SELECT chatters_id FROM players WHERE chatters_id IS NOT NULL ORDER BY id LIMIT 1", "from_players"),
    ]

    for table, query, reason_name in lookups:
        cols = await table_columns(conn, table)
        if not cols:
            continue
        if table != "chatters" and "chatters_id" not in cols:
            continue
        try:
            row = await conn.fetchrow(query)
        except UndefinedTableError:
            continue
        if row and row["chatters_id"] is not None:
            result = int(row["chatters_id"])
            reason = reason_name
            break

    if result is None:
        reason = "no_chatters_id_source_found"

    # #region agent log
    _debug_log(
        "F",
        "repository.get_default_chatters_id",
        "resolved chatters_id",
        {
            "chatters_id": result,
            "reason": reason,
            "has_chatters_id_on_players": True,
        },
    )
    # #endregion
    return result


async def apply_chatters_id_for_player(
    conn: asyncpg.Connection,
    data: dict[str, Any],
    preferred_chatters_id: int | None = None,
) -> None:
    player_cols = await table_columns(conn, "players")
    if "chatters_id" not in player_cols:
        return

    chatters_id = preferred_chatters_id
    if chatters_id is None:
        chatters_id = await get_default_chatters_id(conn)

    if chatters_id is not None:
        data["chatters_id"] = chatters_id
        return

    if await is_column_nullable(conn, "players", "chatters_id"):
        return

    raise ValueError("Не удалось определить chatters_id для регистрации одиночки")


async def get_primary_squad_id(conn: asyncpg.Connection, telegram_id: int) -> int | None:
    if not await table_columns(conn, "user_preferences"):
        return None
    row = await conn.fetchrow(
        "SELECT primary_squad_id FROM user_preferences WHERE telegram_id = $1",
        telegram_id,
    )
    return int(row["primary_squad_id"]) if row and row["primary_squad_id"] is not None else None


async def set_primary_squad_id(
    conn: asyncpg.Connection,
    telegram_id: int,
    squad_id: int | None,
) -> int | None:
    if squad_id is not None:
        member = await get_player_in_squad(conn, telegram_id, squad_id)
        if not member:
            solo = await get_solo_player(conn, telegram_id)
            if not solo:
                raise ValueError("User is not a member of this squad")

    if not await table_columns(conn, "user_preferences"):
        return squad_id

    try:
        await conn.execute(
            """
            INSERT INTO user_preferences (telegram_id, primary_squad_id, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (telegram_id) DO UPDATE
            SET primary_squad_id = EXCLUDED.primary_squad_id,
                updated_at = NOW()
            """,
            telegram_id,
            squad_id,
        )
    except UndefinedTableError:
        return squad_id
    return squad_id


async def reassign_primary_after_leave(
    conn: asyncpg.Connection,
    telegram_id: int,
    left_squad_id: int,
) -> None:
    current = await get_primary_squad_id(conn, telegram_id)
    if current != left_squad_id:
        return
    row = await conn.fetchrow(
        """
        SELECT squad_id
        FROM players
        WHERE telegram_id = $1 AND squad_id IS NOT NULL
        ORDER BY id DESC
        LIMIT 1
        """,
        telegram_id,
    )
    await set_primary_squad_id(conn, telegram_id, int(row["squad_id"]) if row else None)


async def get_me(conn: asyncpg.Connection, telegram_user: TelegramUser) -> dict[str, Any]:
    memberships = await list_memberships(conn, telegram_user.id)
    primary_squad_id = await get_primary_squad_id(conn, telegram_user.id)

    squad_memberships = [membership for membership in memberships if membership["squad_id"] is not None]
    if primary_squad_id is None and squad_memberships:
        primary_squad_id = squad_memberships[0]["squad_id"]
        await set_primary_squad_id(conn, telegram_user.id, primary_squad_id)

    player = None
    if primary_squad_id is not None:
        player = await get_player_in_squad(conn, telegram_user.id, primary_squad_id)
        if not player:
            player = await get_solo_player(conn, telegram_user.id)
    else:
        player = await get_solo_player(conn, telegram_user.id)

    return {
        "telegram_id": telegram_user.id,
        "telegram_tag": telegram_user.tag,
        "display_name": telegram_user.display_name,
        "memberships": memberships,
        "primary_squad_id": primary_squad_id,
        "player": player,
    }


async def get_player_by_telegram_id(conn: asyncpg.Connection, telegram_id: int) -> dict[str, Any] | None:
    primary = await get_primary_squad_id(conn, telegram_id)
    if primary is not None:
        return await get_player_in_squad(conn, telegram_id, primary)
    solo = await get_solo_player(conn, telegram_id)
    if solo:
        return solo
    memberships = await list_memberships(conn, telegram_id)
    squad_memberships = [membership for membership in memberships if membership["squad_id"] is not None]
    return squad_memberships[0] if squad_memberships else None


async def register_player(
    conn: asyncpg.Connection,
    telegram_user: TelegramUser,
    name: str,
    squad_id: int | None = None,
) -> dict[str, Any]:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Player name is required")

    # #region agent log
    _debug_log(
        "A",
        "repository.register_player",
        "register start",
        {"telegram_id": telegram_user.id, "squad_id": squad_id, "name_len": len(clean_name)},
    )
    # #endregion

    data: dict[str, Any] = {
        "telegram_id": telegram_user.id,
        "telegram_tag": telegram_user.tag,
        "name": clean_name,
    }

    existing = None
    if squad_id is None:
        existing = await get_solo_player(conn, telegram_user.id)
        data["squad_id"] = None
        await apply_chatters_id_for_player(conn, data)
    else:
        squad = await get_squad(conn, squad_id)
        if not squad:
            raise ValueError("Squad not found")

        data["squad_id"] = squad_id
        await apply_chatters_id_for_player(conn, data, squad.get("chatters_id"))
        existing = await get_player_in_squad(conn, telegram_user.id, squad_id)

    # #region agent log
    _debug_log(
        "A",
        "repository.register_player",
        "pre write",
        {
            "existing_id": existing["id"] if existing else None,
            "data_keys": sorted(data.keys()),
            "has_chatters_id": "chatters_id" in data,
            "chatters_id": data.get("chatters_id"),
        },
    )
    # #endregion

    try:
        if existing:
            assignments = []
            values: list[Any] = []
            for key, value in data.items():
                assignments.append(f"{key} = ${len(values) + 1}")
                values.append(value)
            values.append(existing["id"])
            await conn.execute(
                f"UPDATE players SET {', '.join(assignments)} WHERE id = ${len(values)}",
                *values,
            )
        else:
            data["id"] = await next_id(conn, "players")
            columns = list(data)
            placeholders = [f"${idx}" for idx in range(1, len(columns) + 1)]
            await conn.execute(
                f"""
                INSERT INTO players ({", ".join(columns)})
                VALUES ({", ".join(placeholders)})
                """,
                *[data[column] for column in columns],
            )
    except Exception as exc:
        # #region agent log
        _debug_log(
            "C",
            "repository.register_player",
            "db write failed",
            {"error_type": type(exc).__name__, "error": str(exc)},
        )
        # #endregion
        raise

    if squad_id is not None:
        squad_memberships = [
            membership for membership in await list_memberships(conn, telegram_user.id)
            if membership["squad_id"] is not None
        ]
        primary = await get_primary_squad_id(conn, telegram_user.id)
        if primary is None and squad_memberships:
            await set_primary_squad_id(conn, telegram_user.id, squad_id)

    if squad_id is None:
        player = await get_solo_player(conn, telegram_user.id)
    else:
        player = await get_player_in_squad(conn, telegram_user.id, squad_id)
    if not player:
        raise ValueError("Failed to register player")
    return player


async def update_player_name(
    conn: asyncpg.Connection,
    telegram_id: int,
    name: str,
) -> None:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Player name is required")

    memberships = await list_memberships(conn, telegram_id)
    if not memberships:
        raise ValueError("Player is not registered")

    await conn.execute(
        "UPDATE players SET name = $1 WHERE telegram_id = $2",
        clean_name,
        telegram_id,
    )


async def unregister_solo_player(conn: asyncpg.Connection, telegram_id: int) -> None:
    member = await get_solo_player(conn, telegram_id)
    if not member:
        raise ValueError("Solo player is not registered")

    from logic.squad_requests import db as squad_requests_db
    from logic.squads import db as squads_db

    await squad_requests_db.cancel_pending_for_player(conn, member["id"])
    await squads_db.remove_player_from_all_friends(conn, member["id"])
    await conn.execute(
        "DELETE FROM players WHERE telegram_id = $1 AND squad_id IS NULL",
        telegram_id,
    )


async def unregister_player(conn: asyncpg.Connection, telegram_id: int, squad_id: int) -> None:
    member = await get_player_in_squad(conn, telegram_id, squad_id)
    if not member:
        raise ValueError("Player is not registered in this squad")

    await conn.execute("DELETE FROM attendances WHERE player_id = $1", member["id"])
    await conn.execute("DELETE FROM schedules WHERE player_id = $1", member["id"])
    await conn.execute(
        "DELETE FROM players WHERE telegram_id = $1 AND squad_id = $2",
        telegram_id,
        squad_id,
    )
    await reassign_primary_after_leave(conn, telegram_id, squad_id)


async def resolve_active_player(
    conn: asyncpg.Connection,
    telegram_id: int,
    squad_id: int | None,
) -> dict[str, Any] | None:
    if squad_id is not None:
        return await get_player_in_squad(conn, telegram_id, squad_id)

    primary = await get_primary_squad_id(conn, telegram_id)
    if primary is None:
        solo = await get_solo_player(conn, telegram_id)
        if solo:
            return solo
        memberships = await list_memberships(conn, telegram_id)
        squad_memberships = [membership for membership in memberships if membership["squad_id"] is not None]
        if not squad_memberships:
            return None
        primary = squad_memberships[0]["squad_id"]
    return await get_player_in_squad(conn, telegram_id, primary)


async def list_presets_for_squad(
    conn: asyncpg.Connection,
    squad_id: int,
    *,
    current_week_only: bool = False,
    week: date | None = None,
) -> list[dict[str, Any]]:
    squad = await get_squad(conn, squad_id)
    if not squad:
        return []

    preset_cols = await table_columns(conn, "schedules_presets")
    title_expr = "COALESCE(sp.name, 'Игра')" if "name" in preset_cols else "'Игра'"
    recurrence_expr = "sp.recurrence_type" if "recurrence_type" in preset_cols else "'weekly'"
    recurrence_date_expr = "sp.recurrence_date" if "recurrence_date" in preset_cols else "NULL::date"
    day_of_month_expr = "sp.day_of_month" if "day_of_month" in preset_cols else "NULL::int"

    if "squad_id" in preset_cols:
        where = "sp.squad_id = $1"
        values = [squad_id]
    elif "chatters_id" in preset_cols and squad.get("chatters_id") is not None:
        where = "sp.chatters_id = $1"
        values = [squad["chatters_id"]]
    else:
        return []

    rows = await conn.fetch(
        f"""
        SELECT
            sp.id,
            {title_expr} AS title,
            sp.game_time,
            sp.game_day_of_week,
            {recurrence_expr} AS recurrence_type,
            {recurrence_date_expr} AS recurrence_date,
            {day_of_month_expr} AS day_of_month,
            g.id AS game_id,
            g.title AS game_title
        FROM schedules_presets AS sp
            LEFT JOIN games AS g ON g.id = sp.game_id
        WHERE {where}
        ORDER BY sp.game_day_of_week, sp.game_time, sp.id
        """,
        *values,
    )
    result = []
    for row in rows:
        preset = dict(row)
        game = None
        if preset.get("game_id") is not None:
            game = {"id": preset["game_id"], "title": preset["game_title"]}
        result.append(
            {
                "id": preset["id"],
                "title": preset["title"],
                "game_time": preset["game_time"],
                "game_day_of_week": preset["game_day_of_week"],
                "recurrence_type": preset.get("recurrence_type") or "weekly",
                "recurrence_date": preset.get("recurrence_date"),
                "day_of_month": preset.get("day_of_month"),
                "game": game,
            }
        )

    if current_week_only:
        target_week = week if week is not None else week_start()
        result = [preset for preset in result if is_preset_active_this_week(preset, target_week)]
        result.sort(key=lambda preset: sort_key_for_week(preset, target_week))
    return result


async def set_player_games(
    conn: asyncpg.Connection,
    telegram_id: int,
    game_ids: list[int],
    squad_id: int | None = None,
) -> dict[str, Any]:
    player = await resolve_active_player(conn, telegram_id, squad_id)
    if not player:
        raise ValueError("Player is not registered")

    await players_db.set_game_ids(conn, player["id"], game_ids)
    if player["squad_id"] is None:
        refreshed = await get_solo_player(conn, telegram_id)
    else:
        refreshed = await get_player_in_squad(conn, telegram_id, player["squad_id"])
    if not refreshed:
        raise ValueError("Player is not registered")
    return refreshed


async def set_squad_games(
    conn: asyncpg.Connection,
    telegram_id: int,
    squad_id: int,
    game_ids: list[int],
) -> dict[str, Any]:
    member = await get_player_in_squad(conn, telegram_id, squad_id)
    if not member:
        raise ValueError("User is not a member of this squad")

    updated_game_ids = await squads_db.set_game_ids(conn, squad_id, game_ids)
    squad = await get_squad(conn, squad_id)
    if not squad:
        raise ValueError("Squad not found")
    return squad | {"games": await resolve_games(conn, updated_game_ids)}


async def get_schedule(conn: asyncpg.Connection, player_id: int, preset_id: int) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        """
        SELECT id, player_id, schedule_preset_id, will_attend_default, created_at
        FROM schedules
        WHERE player_id = $1 AND schedule_preset_id = $2
        """,
        player_id,
        preset_id,
    )
    return dict(row) if row else None


async def set_schedule_default(
    conn: asyncpg.Connection,
    player_id: int,
    preset_id: int,
    will_attend_default: bool | None,
) -> None:
    if will_attend_default is None:
        await conn.execute(
            "DELETE FROM schedules WHERE player_id = $1 AND schedule_preset_id = $2",
            player_id,
            preset_id,
        )
        return

    existing = await get_schedule(conn, player_id, preset_id)
    if existing:
        await conn.execute(
            "UPDATE schedules SET will_attend_default = $1 WHERE id = $2",
            will_attend_default,
            existing["id"],
        )
        return

    await conn.execute(
        """
        INSERT INTO schedules (id, player_id, schedule_preset_id, will_attend_default)
        VALUES ($1, $2, $3, $4)
        """,
        await next_id(conn, "schedules"),
        player_id,
        preset_id,
        will_attend_default,
    )


def week_start() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


async def get_attendance(
    conn: asyncpg.Connection,
    player_id: int,
    preset_id: int,
    *,
    week: date | None = None,
) -> dict[str, Any] | None:
    target_week = week if week is not None else week_start()
    row = await conn.fetchrow(
        """
        SELECT id, schedule_preset_id, player_id, attend_status, comment, created_at
        FROM attendances
        WHERE player_id = $1 AND schedule_preset_id = $2 AND created_at >= $3
        ORDER BY created_at DESC
        LIMIT 1
        """,
        player_id,
        preset_id,
        target_week,
    )
    return dict(row) if row else None


async def set_attendance(
    conn: asyncpg.Connection,
    player_id: int,
    preset_id: int,
    attend_status: AttendStatus | None,
    comment: str,
) -> None:
    existing = await get_attendance(conn, player_id, preset_id)
    if attend_status is None:
        if existing:
            await conn.execute("DELETE FROM attendances WHERE id = $1", existing["id"])
        return

    if existing:
        await conn.execute(
            """
            UPDATE attendances
            SET attend_status = $1, comment = $2, created_at = NOW()
            WHERE id = $3
            """,
            attend_status.value,
            comment,
            existing["id"],
        )
        return

    await conn.execute(
        """
        INSERT INTO attendances (id, schedule_preset_id, player_id, attend_status, comment)
        VALUES ($1, $2, $3, $4, $5)
        """,
        await next_id(conn, "attendances"),
        preset_id,
        player_id,
        attend_status.value,
        comment,
    )


async def list_player_schedule_state(
    conn: asyncpg.Connection,
    player_id: int,
    squad_id: int,
    *,
    week: date | None = None,
) -> list[dict[str, Any]]:
    presets = await list_presets_for_squad(conn, squad_id, current_week_only=True, week=week)
    result = []
    for preset in presets:
        schedule = await get_schedule(conn, player_id, preset["id"])
        result.append(preset | {"will_attend_default": schedule["will_attend_default"] if schedule else None})
    return result


def resolve_effective_attend_status(
    will_attend_default: bool | None,
    weekly_status: str | None,
) -> str | None:
    if weekly_status is not None:
        return weekly_status
    if will_attend_default is True:
        return "will_attend"
    if will_attend_default is False:
        return "will_not_attend"
    return None


async def list_player_attendance_state(
    conn: asyncpg.Connection,
    player_id: int,
    squad_id: int,
    *,
    week: date | None = None,
) -> list[dict[str, Any]]:
    schedules = await list_player_schedule_state(conn, player_id, squad_id, week=week)
    result = []
    for schedule in schedules:
        attendance = await get_attendance(conn, player_id, schedule["id"], week=week)
        weekly_status = attendance["attend_status"] if attendance else None
        result.append(
            {
                "schedule_preset": schedule,
                "attend_status": resolve_effective_attend_status(
                    schedule.get("will_attend_default"),
                    weekly_status,
                ),
                "weekly_attend_status": weekly_status,
                "comment": attendance["comment"] if attendance else "",
            }
        )
    return result


async def list_attendance_summary(conn: asyncpg.Connection, squad_id: int) -> list[dict[str, Any]]:
    presets = await list_presets_for_squad(conn, squad_id, current_week_only=True)
    summary = []
    for preset in presets:
        rows = await conn.fetch(
            """
            SELECT
                p.name AS player_name,
                COALESCE(
                    atd.attend_status,
                    CASE s.will_attend_default
                        WHEN TRUE THEN 'will_attend'
                        WHEN FALSE THEN 'will_not_attend'
                    END
                ) AS attend_status,
                COALESCE(atd.comment, '') AS comment
            FROM players AS p
                LEFT JOIN schedules AS s
                    ON s.player_id = p.id
                    AND s.schedule_preset_id = $2
                LEFT JOIN attendances AS atd
                    ON atd.player_id = p.id
                    AND atd.schedule_preset_id = $2
                    AND atd.created_at >= $3
            WHERE p.squad_id = $1 AND (s.id IS NOT NULL OR atd.id IS NOT NULL)
            ORDER BY lower(p.name)
            """,
            squad_id,
            preset["id"],
            week_start(),
        )
        summary.append({"schedule_preset": preset, "players": [dict(row) for row in rows if row["attend_status"]]})
    return summary
