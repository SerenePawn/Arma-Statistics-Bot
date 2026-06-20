from aiogram import Bot

from core.settings import BotSettings

import asyncpg


class AppState:
    settings: BotSettings | None = None
    db_pool: asyncpg.Pool | None = None
    bot: Bot | None = None


state = AppState()
