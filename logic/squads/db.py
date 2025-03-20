from aiosqlite import Connection

from core.db.db import record_to_model, record_to_model_list
from logic.squads.models import Squad, SquadForm
from core.db import db


async def create(conn: Connection, form: SquadForm) -> int:
    result = await db.create(
        conn,
        table="squads",
        data=form.model_dump(exclude_none=True),
    )
    await conn.commit()
    return result["last_insert_rowid"]


async def get(conn: Connection, pk: int) -> Squad | None:
    result = await db.get(
        conn,
        "squads",
        pk
    )
    if not result:
        return None
    model = record_to_model(Squad, result)
    return model


async def get_list(conn: Connection, pks: list[int]) -> list[Squad]:
    result = await db.get_list(
        conn,
        "squads",
        "id IN (?)",
        [pks]
    )
    return record_to_model_list(Squad, result)


async def get_by_chat(conn: Connection, chat_id: int, chat_thread_id: int | None = None) -> Squad | None:
    result = await db.get_by_where(
        conn,
        "squads",
        "telegram_chat_id = ? AND telegram_chat_thread_id = ?",
        [chat_id, chat_thread_id or ""],
    )
    if not result:
        return None
    model, *_ = record_to_model_list(Squad, result)
    return model


async def get_by_chat_thread_any(conn: Connection, chat_id: int) -> Squad | None:
    result = await db.get_by_where(
        conn,
        "squads",
        "telegram_chat_id = ?",
        [chat_id],
    )
    if not result:
        return None
    model, *_ = record_to_model_list(Squad, result)
    return model


async def get_by_tag(conn: Connection, clan_tag: str) -> Squad | None:
    result_found_tags = await conn.execute_fetchall(
        f"""
            WITH RECURSIVE split(value, str) AS (
                SELECT NULL, (select group_concat(tags) FROM squads WHERE tags LIKE '%' || ? || '%') || ','
                UNION ALL
                SELECT
                    SUBSTR(s.str, 0, INSTR(s.str, ',')),
                    SUBSTR(s.str, INSTR(s.str, ',')+1)
                FROM split s
                WHERE s.str != ''
            ) 
            SELECT value AS tag
            FROM split 
            WHERE value IS NOT NULL
                AND TRIM(value, '[]-=+*.') LIKE ?;
        """,
        parameters=[clan_tag, clan_tag]
    )
    found_tags = [i["tag"] for i in result_found_tags]
    if not found_tags:
        return None
    found_tag, *_ = found_tags

    result_squad = await conn.execute_fetchall(
        f"""
            SELECT *
            FROM squads
            WHERE tags LIKE '%' || ? || '%'
        """,
        parameters=[found_tag]
    )
    if not result_squad:
        return None
    result_squad, *_ = result_squad
    if not result_squad["telegram_chat_id"]:
        return None
    return record_to_model(Squad, result_squad)


async def update(conn: Connection, squad_id: int, **data) -> Squad:
    result = await db.update(
        conn,
        pk=squad_id,
        table="squads",
        data=data,
        with_updated_at=False
    )
    await conn.commit()
    return record_to_model(Squad, result)
