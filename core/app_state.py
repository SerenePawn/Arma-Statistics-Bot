from threading import Thread, Event

import asyncpg
from aiohttp import BasicAuth
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession

from core.settings import BotSettings, resolve_config_path
from core.singleton import SingletonMeta


def _build_proxy(config: BotSettings) -> str | tuple[str, BasicAuth]:
    proxy_url = f"{config.PROXY_PROTOCOL}://{config.PROXY_IP}:{config.PROXY_PORT}"
    if config.PROXY_LOGIN or config.PROXY_PASSWORD:
        return proxy_url, BasicAuth(
            login=config.PROXY_LOGIN,
            password=config.PROXY_PASSWORD,
        )
    return proxy_url


class AppState(metaclass=SingletonMeta):
    config: BotSettings
    bot: Bot
    dispatcher: Dispatcher
    conn: asyncpg.Connection | None
    background_tasks_threads: list[Thread] = []
    shutdown_event: Event

    def __init__(self, config_path: str | None = None) -> None:
        self.config = BotSettings.from_file(config_path or resolve_config_path())

        if self.config.USE_PROXY:
            session = AiohttpSession(
                proxy=_build_proxy(self.config),
                timeout=120.0,
            )
            self.bot = Bot(token=self.config.API_TOKEN, session=session)
        else:
            self.bot = Bot(token=self.config.API_TOKEN)
        self.dispatcher = Dispatcher(storage=MemoryStorage())
        self.conn = None
        self.background_tasks_threads = []
        self.shutdown_event = Event()
