import asyncpg
from asyncpg import UndefinedTableError

from core.db.db import record_to_model, record_to_model_list
from logic.squads.chat_lookup import get_squad_id_by_telegram_chat_id, table_columns
from logic.squads.friends import parse_friends_ids
from logic.squads.models import Squad, SquadForm
from core.db import db
from logic.games import db as games_db


async def create(conn: asyncpg.Connection, form: SquadForm) -> int:
    result = await db.create(
        conn,
        table="squads",
        data=form.model_dump(exclude_none=True),
    )
    return result["id"]


async def get(conn: asyncpg.Connection, pk: int) -> Squad | None:
    result = await db.get(
        conn,
        "squads",
        pk
    )
    if not result:
        return None
    model = record_to_model(Squad, result)
    return model


async def get_list(conn: asyncpg.Connection, pks: list[int]) -> list[Squad]:
    if not pks:
        return []
    placeholders = ", ".join([f"${i + 1}" for i in range(len(pks))])
    result = await db.get_raw(conn, f"SELECT * FROM squads WHERE id IN ({placeholders})", pks)
    return record_to_model_list(Squad, result)


async def get_by_chat(conn: asyncpg.Connection, chat_id: int, chat_thread_id: int | None = None) -> Squad | None:
    squad_id = await get_squad_id_by_telegram_chat_id(conn, chat_id)
    if squad_id is None:
        return None
    if chat_thread_id is not None:
        squad_cols = await table_columns(conn, "squads")
        if "telegram_chat_id" in squad_cols:
            result = await db.get_by_where(
                conn,
                "squads",
                "telegram_chat_id = $1 AND telegram_chat_thread_id = $2",
                [chat_id, chat_thread_id or ""],
            )
            return record_to_model(Squad, result) if result else None
        if await table_columns(conn, "chatters"):
            row = await conn.fetchrow(
                """
                SELECT s.*
                FROM squads AS s
                    JOIN chatters AS c ON c.id = s.chatters_id
                WHERE c.telegram_chat_id = $1
                    AND c.telegram_chat_thread_id = $2
                ORDER BY s.id
                LIMIT 1
                """,
                str(chat_id),
                str(chat_thread_id or ""),
            )
            return record_to_model(Squad, row) if row else None
    return await get(conn, squad_id)


async def get_by_chat_thread_any(conn: asyncpg.Connection, chat_id: int) -> Squad | None:
    squad_id = await get_squad_id_by_telegram_chat_id(conn, chat_id)
    if squad_id is None:
        return None
    return await get(conn, squad_id)


async def get_by_tag(conn: asyncpg.Connection, clan_tag: str) -> Squad | None:
    result_squad = await db.get_by_where(
        conn,
        "squads",
        "tags ILIKE $1",
        [f"%{clan_tag}%"],
    )
    return record_to_model(Squad, result_squad)


async def update(conn: asyncpg.Connection, squad_id: int, **data) -> Squad:
    result = await db.update(
        conn,
        pk=squad_id,
        table="squads",
        data=data,
        with_updated_at=False
    )
    return record_to_model(Squad, result)


async def set_game_ids(conn: asyncpg.Connection, squad_id: int, game_ids: list[int]) -> list[int]:
    await games_db.validate_game_ids(conn, game_ids)
    row = await conn.fetchrow("SELECT main_game_ids FROM squads WHERE id = $1", squad_id)
    current_main_ids = Squad.normalize_main_game_ids(row["main_game_ids"]) if row else []
    next_main_ids = [game_id for game_id in current_main_ids if game_id in game_ids]
    result = await db.update(
        conn,
        pk=squad_id,
        table="squads",
        data={"games_ids": game_ids, "main_game_ids": next_main_ids},
        with_updated_at=False,
    )
    if not result:
        return []
    return Squad.normalize_games_ids(result.get("games_ids"))


async def set_game_config(
    conn: asyncpg.Connection,
    squad_id: int,
    game_ids: list[int],
    main_game_ids: list[int],
) -> tuple[list[int], list[int]]:
    await games_db.validate_game_ids(conn, game_ids)
    requested_main_ids = [int(game_id) for game_id in dict.fromkeys(main_game_ids)]
    normalized_main_ids = [game_id for game_id in requested_main_ids if game_id in game_ids]
    result = await db.update(
        conn,
        pk=squad_id,
        table="squads",
        data={"games_ids": game_ids, "main_game_ids": normalized_main_ids},
        with_updated_at=False,
    )
    if not result:
        return [], []
    return (
        Squad.normalize_games_ids(result.get("games_ids")),
        Squad.normalize_main_game_ids(result.get("main_game_ids")),
    )


async def get_friends_ids(conn: asyncpg.Connection, squad_id: int) -> list[int]:
    row = await conn.fetchrow("SELECT friends_ids FROM squads WHERE id = $1", squad_id)
    if not row:
        return []
    return parse_friends_ids(row["friends_ids"])


async def get_squad_ids_for_friend_player(conn: asyncpg.Connection, player_id: int) -> list[int]:
    rows = await conn.fetch(
        """
        SELECT id
        FROM squads
        WHERE friends_ids @> to_jsonb(ARRAY[$1::int])
        ORDER BY id
        """,
        player_id,
    )
    return [int(row["id"]) for row in rows]


async def add_friend(conn: asyncpg.Connection, squad_id: int, player_id: int) -> Squad:
    friends_ids = await get_friends_ids(conn, squad_id)
    if player_id not in friends_ids:
        friends_ids.append(player_id)
    result = await db.update(
        conn,
        pk=squad_id,
        table="squads",
        data={"friends_ids": friends_ids},
        with_updated_at=False,
    )
    return record_to_model(Squad, result)


async def remove_friend(conn: asyncpg.Connection, squad_id: int, player_id: int) -> Squad:
    friends_ids = [friend_id for friend_id in await get_friends_ids(conn, squad_id) if friend_id != player_id]
    result = await db.update(
        conn,
        pk=squad_id,
        table="squads",
        data={"friends_ids": friends_ids},
        with_updated_at=False,
    )
    return record_to_model(Squad, result)


async def remove_player_from_all_friends(conn: asyncpg.Connection, player_id: int) -> None:
    rows = await conn.fetch("SELECT id, friends_ids FROM squads")
    for row in rows:
        friends_ids = parse_friends_ids(row["friends_ids"])
        if player_id not in friends_ids:
            continue
        await db.update(
            conn,
            pk=row["id"],
            table="squads",
            data={"friends_ids": [friend_id for friend_id in friends_ids if friend_id != player_id]},
            with_updated_at=False,
        )


async def _delete_squad_presets(
    conn: asyncpg.Connection,
    squad_id: int,
    chatters_id: int | None,
) -> None:
    preset_cols = await table_columns(conn, "schedules_presets")
    if "squad_id" in preset_cols:
        preset_rows = await conn.fetch(
            "SELECT id FROM schedules_presets WHERE squad_id = $1",
            squad_id,
        )
    elif chatters_id is not None and "chatters_id" in preset_cols:
        preset_rows = await conn.fetch(
            "SELECT id FROM schedules_presets WHERE chatters_id = $1",
            chatters_id,
        )
    else:
        return

    for row in preset_rows:
        preset_id = row["id"]
        await conn.execute("DELETE FROM attendances WHERE schedule_preset_id = $1", preset_id)
        await conn.execute("DELETE FROM schedules WHERE schedule_preset_id = $1", preset_id)
        await conn.execute("DELETE FROM schedules_presets WHERE id = $1", preset_id)


async def delete_squad(conn: asyncpg.Connection, squad_id: int) -> bool:
    from logic.users import db as users_db

    squad = await get(conn, squad_id)
    if not squad:
        return False

    await _delete_squad_presets(conn, squad_id, squad.chatters_id)

    player_rows = await conn.fetch(
        "SELECT id, telegram_id FROM players WHERE squad_id = $1",
        squad_id,
    )
    for player in player_rows:
        await conn.execute("DELETE FROM attendances WHERE player_id = $1", player["id"])
        await conn.execute("DELETE FROM schedules WHERE player_id = $1", player["id"])
        await users_db.reassign_primary_after_leave(conn, player["telegram_id"], squad_id)

    await conn.execute("DELETE FROM players WHERE squad_id = $1", squad_id)

    try:
        await conn.execute("DELETE FROM usage_statistics WHERE squad_id = $1", squad_id)
    except UndefinedTableError:
        pass

    await conn.execute("DELETE FROM squads WHERE id = $1", squad_id)
    return True
