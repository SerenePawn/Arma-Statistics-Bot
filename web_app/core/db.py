import asyncpg

from core.db.db import init_connection

from .config import load_settings


async def init_pool() -> asyncpg.Pool:
    settings = load_settings()
    if not settings.PSQL_PATH:
        raise RuntimeError("DB connection parameters not defined")

    return await asyncpg.create_pool(
        dsn=settings.PSQL_PATH,
        init=init_connection,
        min_size=1,
        max_size=3,
    )


async def close_pool(pool: asyncpg.Pool | None) -> None:
    if pool:
        await pool.close()
