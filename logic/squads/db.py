from aiosqlite import Connection

from core.db.db import record_to_model, record_to_model_list
from logic.squads.models import Squad, SquadForm
from core.db import db


async def create(conn: Connection, form: SquadForm) -> int:
    result = await db.create(
        conn,
        table="squads",
        data=form.model_dump(),
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
        [chat_id, chat_thread_id],
    )
    if not result:
        return None
    model, *_ = record_to_model_list(Squad, result)
    return model


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
