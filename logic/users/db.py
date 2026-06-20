import asyncpg
from asyncpg import UndefinedTableError

from core.db.db import record_to_model
from logic.users.models import UserPreferences


async def get_preferences(conn: asyncpg.Connection, telegram_id: int) -> UserPreferences | None:
    try:
        row = await conn.fetchrow(
            """
            SELECT telegram_id, primary_squad_id, created_at, updated_at
            FROM user_preferences
            WHERE telegram_id = $1
            """,
            telegram_id,
        )
    except UndefinedTableError:
        return None
    return record_to_model(UserPreferences, row) if row else None


async def ensure_preferences(conn: asyncpg.Connection, telegram_id: int) -> UserPreferences:
    row = await conn.fetchrow(
        """
        INSERT INTO user_preferences (telegram_id)
        VALUES ($1)
        ON CONFLICT (telegram_id) DO UPDATE SET telegram_id = EXCLUDED.telegram_id
        RETURNING telegram_id, primary_squad_id, created_at, updated_at
        """,
        telegram_id,
    )
    return record_to_model(UserPreferences, row)


async def set_primary_squad(
    conn: asyncpg.Connection,
    telegram_id: int,
    squad_id: int | None,
) -> UserPreferences:
    if squad_id is not None:
        member = await conn.fetchrow(
            "SELECT id FROM players WHERE telegram_id = $1 AND squad_id = $2",
            telegram_id,
            squad_id,
        )
        if not member:
            raise ValueError("User is not a member of this squad")

    try:
        row = await conn.fetchrow(
            """
            INSERT INTO user_preferences (telegram_id, primary_squad_id, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (telegram_id) DO UPDATE
            SET primary_squad_id = EXCLUDED.primary_squad_id,
                updated_at = NOW()
            RETURNING telegram_id, primary_squad_id, created_at, updated_at
            """,
            telegram_id,
            squad_id,
        )
    except UndefinedTableError as exc:
        raise ValueError("User preferences are not available yet") from exc
    return record_to_model(UserPreferences, row)


async def reassign_primary_after_leave(
    conn: asyncpg.Connection,
    telegram_id: int,
    left_squad_id: int,
) -> None:
    prefs = await get_preferences(conn, telegram_id)
    if not prefs or prefs.primary_squad_id != left_squad_id:
        return

    next_squad = await conn.fetchval(
        """
        SELECT squad_id
        FROM players
        WHERE telegram_id = $1
        ORDER BY id DESC
        LIMIT 1
        """,
        telegram_id,
    )
    await set_primary_squad(conn, telegram_id, next_squad)
