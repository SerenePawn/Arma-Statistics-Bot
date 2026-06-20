import asyncpg

from core.db import db
from core.db.db import record_to_model, record_to_model_list
from logic.games.models import Game, GameForm


async def create(conn: asyncpg.Connection, form: GameForm) -> int:
    result = await db.create(
        conn,
        table="games",
        data=form.model_dump(),
    )
    return result["id"]


async def get(conn: asyncpg.Connection, pk: int) -> Game | None:
    result = await db.get(conn, "games", pk)
    if not result:
        return None
    return record_to_model(Game, result)


async def get_list(conn: asyncpg.Connection) -> list[Game]:
    result = await db.get_list(conn, "games", order=["title", "id"])
    return record_to_model_list(Game, result)


async def get_by_ids(conn: asyncpg.Connection, game_ids: list[int]) -> list[Game]:
    if not game_ids:
        return []
    ordered_ids = [int(game_id) for game_id in dict.fromkeys(game_ids)]
    rows = await conn.fetch(
        """
        SELECT id, title, created_at
        FROM games
        WHERE id = ANY($1::int[])
        ORDER BY array_position($1::int[], id)
        """,
        ordered_ids,
    )
    return record_to_model_list(Game, rows)


async def update(conn: asyncpg.Connection, pk: int, **data: object) -> Game:
    result = await db.update(
        conn,
        pk=pk,
        table="games",
        data=data,
        with_updated_at=False,
    )
    return record_to_model(Game, result)


async def delete(conn: asyncpg.Connection, pk: int) -> Game | None:
    await conn.execute(
        """
        UPDATE squads
        SET games_ids = COALESCE(
            (
                SELECT jsonb_agg(value)
                FROM jsonb_array_elements(games_ids) AS value
                WHERE value::int <> $1
            ),
            '[]'::jsonb
        )
        WHERE games_ids @> to_jsonb(ARRAY[$1]::int[])
        """,
        pk,
    )
    await conn.execute(
        """
        UPDATE players
        SET games_ids = COALESCE(
            (
                SELECT jsonb_agg(value)
                FROM jsonb_array_elements(games_ids) AS value
                WHERE value::int <> $1
            ),
            '[]'::jsonb
        )
        WHERE games_ids @> to_jsonb(ARRAY[$1]::int[])
        """,
        pk,
    )
    await conn.execute(
        "UPDATE schedules_presets SET game_id = NULL WHERE game_id = $1",
        pk,
    )
    result = await db.delete(conn, table="games", pk=pk)
    return record_to_model(Game, result) if result else None


async def get_or_create_by_title(conn: asyncpg.Connection, title: str) -> Game:
    clean_title = title.strip()
    row = await conn.fetchrow(
        """
        SELECT id, title, created_at
        FROM games
        WHERE title = $1
        """,
        clean_title,
    )
    if row:
        return record_to_model(Game, row)

    game_id = await create(conn, GameForm(title=clean_title))
    game = await get(conn, game_id)
    if not game:
        raise RuntimeError("Failed to create game")
    return game


async def validate_game_ids(conn: asyncpg.Connection, game_ids: list[int]) -> None:
    if not game_ids:
        return

    unique_ids = sorted(set(game_ids))
    rows = await conn.fetch(
        "SELECT id FROM games WHERE id = ANY($1::int[])",
        unique_ids,
    )
    found_ids = {int(row["id"]) for row in rows}
    missing = [game_id for game_id in unique_ids if game_id not in found_ids]
    if missing:
        raise ValueError(f"Unknown game ids: {', '.join(str(game_id) for game_id in missing)}")
