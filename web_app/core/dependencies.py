from collections.abc import AsyncGenerator
import asyncpg
from aiogram import Bot
from fastapi import Depends, Header, HTTPException, status

from logic.telegram.debug_context import set_debug_admin_telegram_id

from .debug_token import verify_debug_token
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


def debug_mode_enabled() -> bool:
    settings = state.settings
    if settings is None:
        return False
    return bool(settings.WEB_APP_DEBUG_CODE.strip())


def _activate_debug_admin_from_token(telegram_id: int, x_debug_token: str | None) -> None:
    if not debug_mode_enabled() or state.settings is None:
        return

    token = (x_debug_token or "").strip()
    if not token:
        return

    if verify_debug_token(token, telegram_id, state.settings.API_TOKEN):
        set_debug_admin_telegram_id(telegram_id)


async def get_telegram_user(
    authorization: str | None = Header(default=None),
    x_telegram_init_data: str | None = Header(default=None),
    x_debug_token: str | None = Header(default=None, alias="X-Debug-Token"),
) -> TelegramUser:
    if not state.settings:
        raise RuntimeError("Application state has no settings")

    init_data = _extract_init_data(authorization, x_telegram_init_data)
    if init_data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram auth data required")

    telegram_user = validate_init_data(init_data, state.settings.API_TOKEN)
    _activate_debug_admin_from_token(telegram_user.id, x_debug_token)
    return telegram_user


async def activate_debug_admin(
    telegram_user: TelegramUser = Depends(get_telegram_user),
) -> None:
    return None


async def get_bot() -> Bot:
    if state.bot is None:
        raise RuntimeError("Application state has no bot")
    return state.bot
