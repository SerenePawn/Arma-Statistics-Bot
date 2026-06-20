from aiohttp import BasicAuth
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from core.settings import BotSettings


def _build_proxy(config: BotSettings) -> str | tuple[str, BasicAuth]:
    proxy_url = f"{config.PROXY_PROTOCOL}://{config.PROXY_IP}:{config.PROXY_PORT}"
    if config.PROXY_LOGIN or config.PROXY_PASSWORD:
        return proxy_url, BasicAuth(
            login=config.PROXY_LOGIN,
            password=config.PROXY_PASSWORD,
        )
    return proxy_url


def create_bot(settings: BotSettings) -> Bot:
    if settings.USE_PROXY:
        session = AiohttpSession(
            proxy=_build_proxy(settings),
            timeout=120.0,
        )
        return Bot(token=settings.API_TOKEN, session=session)
    return Bot(token=settings.API_TOKEN)
