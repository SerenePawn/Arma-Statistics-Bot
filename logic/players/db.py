import asyncpg

from core.db.db import record_to_model, record_to_model_list
from core.db import db
from logic.players.models import Player, PlayerForm
from logic.games import db as games_db


async def create(conn: asyncpg.Connection, form: PlayerForm) -> int:
    result = await db.create(
        conn,
        table="players",
        data=form.model_dump(),
    )
    return result["id"]


async def get(conn: asyncpg.Connection, id: int) -> Player | None:
    result = await db.get(
        conn,
        "players",
        id
    )
    if not result:
        return None
    model = record_to_model(Player, result)
    return model


async def get_by_squad_id(conn: asyncpg.Connection, squad_id: int) -> list[Player]:
    where = "squad_id = $1"
    values = [squad_id]

    result = await db.get_by_where(
        conn,
        "players",
        where,
        values,
        return_rows=True,
    )
    return record_to_model_list(Player, result)


async def get_by_tg_id(conn: asyncpg.Connection, telegram_id: int, squad_id: int | None = None) -> Player | None:
    where = "telegram_id = $1"
    values = [telegram_id]
    if squad_id:
        where += " AND squad_id = $2"
        values.append(squad_id)

    result = await db.get_by_where(
        conn,
        "players",
        where,
        values
    )
    return record_to_model(Player, result) if result else None


async def get_by_tg_and_squad(
    conn: asyncpg.Connection,
    telegram_id: int,
    squad_id: int,
) -> Player | None:
    return await get_by_tg_id(conn, telegram_id, squad_id)


async def get_all_by_tg_id(conn: asyncpg.Connection, telegram_id: int) -> list[Player]:
    result = await db.get_by_where(
        conn,
        "players",
        "telegram_id = $1",
        [telegram_id],
        return_rows=True,
    )
    return record_to_model_list(Player, result)


async def upsert_in_squad(conn: asyncpg.Connection, form: PlayerForm, **extra: object) -> Player:
    existing = await get_by_tg_and_squad(conn, form.telegram_id, form.squad_id)
    data = form.model_dump() | extra
    if existing:
        result = await db.update(
            conn,
            pk=existing.id,
            table="players",
            data=data,
            with_updated_at=False,
        )
        return record_to_model(Player, result)

    result = await db.create(
        conn,
        table="players",
        data=data,
    )
    return record_to_model(Player, result)


async def update(conn: asyncpg.Connection, squad_id: int, **data) -> Player:
    result = await db.update(
        conn,
        pk=squad_id,
        table="players",
        data=data,
        with_updated_at=False
    )
    return record_to_model(Player, result)


async def delete_from_squad(conn: asyncpg.Connection, telegram_id: int, squad_id: int) -> Player | None:
    result = await db.delete_by_where(
        conn,
        table="players",
        where=["telegram_id = $1", "squad_id = $2"],
        values=[telegram_id, squad_id],
    )
    return record_to_model(Player, result) if result else None


async def delete(conn: asyncpg.Connection, telegram_id: int) -> Player | None:
    result = await db.delete_by_where(
        conn,
        table="players",
        where=["telegram_id = $1"],
        values=[telegram_id]
    )
    return record_to_model(Player, result) if result else None


async def set_game_ids(conn: asyncpg.Connection, player_id: int, game_ids: list[int]) -> Player:
    await games_db.validate_game_ids(conn, game_ids)
    result = await db.update(
        conn,
        pk=player_id,
        table="players",
        data={"games_ids": game_ids},
        with_updated_at=False,
    )
    return record_to_model(Player, result)
