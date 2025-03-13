from aiosqlite import Connection

from core.db.db import record_to_model, record_to_model_list
from core.db import db
from logic.players.models import Player, PlayerForm


async def create(conn: Connection, form: PlayerForm) -> int:
    result = await db.create(
        conn,
        table="players",
        data=form.model_dump(),
    )
    return result["last_insert_rowid"]


async def get(conn: Connection, id: int) -> Player | None:
    result = await db.get(
        conn,
        "players",
        id
    )
    if not result:
        return None
    model = record_to_model(Player, result)
    return model


async def get_by_squad_id(conn: Connection, squad_id: int) -> list[Player]:
    where = "squad_id = ?"
    values = [squad_id]

    result = await db.get_by_where(
        conn,
        "players",
        where,
        values
    )
    return record_to_model_list(Player, result)


async def get_by_tg_id(conn: Connection, telegram_id: int, squad_id: int | None = None) -> Player | None:
    where = "telegram_id = ?"
    values = [telegram_id]
    if squad_id:
        where += " AND squad_id = ?"
        values.append(squad_id)

    result = await db.get_by_where(
        conn,
        "players",
        where,
        values
    )
    if not result:
        return None
    model, *_ = record_to_model_list(Player, result)
    return model


async def update(conn: Connection, squad_id: int, **data) -> Player:
    result = await db.update(
        conn,
        pk=squad_id,
        table="players",
        data=data,
        with_updated_at=False
    )
    return record_to_model(Player, result)


async def delete(conn: Connection, telegram_id: int) -> Player:
    result = await db.delete_by_where(
        conn,
        table="players",
        where=["telegram_id = ?"],
        values=[telegram_id]
    )
    return record_to_model(Player, result)
