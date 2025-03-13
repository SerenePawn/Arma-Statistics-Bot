from threading import Thread, Event

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiosqlite import Connection

from core.settings import BotSettings
from core.singleton import SingletonMeta


class AppState(metaclass=SingletonMeta):
    config: BotSettings
    bot: Bot
    dispatcher: Dispatcher
    conn: Connection | None
    background_tasks_threads: list[Thread] = []
    shutdown_event: Event

    def __init__(self, config_path: str | None = None) -> None:
        self.config = BotSettings.from_file(config_path)
        self.bot = Bot(token=self.config.API_TOKEN)
        self.dispatcher = Dispatcher(storage=MemoryStorage())
        self.conn = None
        self.background_tasks_threads = []
        self.shutdown_event = Event()
