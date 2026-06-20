from collections.abc import AsyncGenerator
import asyncpg
from aiogram import Bot
from fastapi import Header, HTTPException, status

from .security import TelegramUser, validate_init_data
from .state import state


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    if not state.db_pool:
        raise RuntimeError("Application state has no db pool")

    async with state.db_pool.acquire() as conn:
        yield conn


def _extract_init_data(
    authorization: str | None,
    x_telegram_init_data: str | None,
) -> str | None:
    if x_telegram_init_data and x_telegram_init_data.strip():
        return x_telegram_init_data.strip()

    if authorization and authorization.lower().startswith("tma "):
        auth_data = authorization[4:].strip()
        if auth_data:
            return auth_data

    return None


async def get_telegram_user(
    authorization: str | None = Header(default=None),
    x_telegram_init_data: str | None = Header(default=None),
) -> TelegramUser:
    if not state.settings:
        raise RuntimeError("Application state has no settings")

    init_data = _extract_init_data(authorization, x_telegram_init_data)
    if init_data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram auth data required")

    return validate_init_data(init_data, state.settings.API_TOKEN)


async def get_bot() -> Bot:
    if state.bot is None:
        raise RuntimeError("Application state has no bot")
    return state.bot
