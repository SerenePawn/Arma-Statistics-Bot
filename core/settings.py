from configparser import ConfigParser
from pathlib import Path

from pydantic import BaseModel


class BotSettings(BaseModel):
    API_TOKEN: str
    SQLITE_PATH: str = "db/arma_statistics_bot.db"
    MIGRATIONS_PATH: str = "db/migrations"
    TEMPLATE_FOLDER: str = "core/l10n"
    DEV_TG_ID: int  # ТГ создателя; нужен, чтобы присылались баги от юзеров на мой тг акк и логгировались ошибки
    PAGE_LIMIT: int = 10
    BUTTONS_PAGE_LIMIT: int = 5

    OCAPS_PATH: Path = "./ocaps"
    OCAPS_PLY_VEHICLES_SPREAD_COORDS: int

    SEND_LOGS_TO_DEV: bool = True
    LOGS_PATH: Path = "./logs"


    @staticmethod
    def from_file(path: str | None = None) -> "BotSettings":
        path = path or "config.ini"
        with open(path, "r") as fd:
            config = ConfigParser()
            config.read_file(fd)

            opts = [
                (section, option)
                for section in config.sections()
                for option in config.options(section=section)
            ]
            data = {}
            for section, option in opts:
                data[option.upper()] = config.get(section, option)

            return BotSettings(**data)


