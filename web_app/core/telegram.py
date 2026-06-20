from aiogram import Bot

from core.telegram_bot import create_bot
from core.settings import BotSettings


_bot: Bot | None = None


def init_bot(settings: BotSettings) -> Bot:
    global _bot
    _bot = create_bot(settings)
    return _bot


def get_bot_instance() -> Bot:
    if _bot is None:
        raise RuntimeError("Telegram bot is not initialized")
    return _bot


async def close_bot() -> None:
    global _bot
    if _bot is not None:
        await _bot.session.close()
        _bot = None
