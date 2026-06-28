from configparser import ConfigParser
import os
from pathlib import Path

from pydantic import BaseModel


def resolve_config_path(path: str | None = None) -> str:
    return path or os.getenv("ARMA_BOT_CONFIG", "config.ini")


class BotSettings(BaseModel):
    API_TOKEN: str
    PSQL_PATH: str = "postgres://postgres@localhost:5432/postgres"
    MIGRATIONS_PATH: str = "db/migrations"
    TEMPLATE_FOLDER: str = "core/l10n"
    DEV_TG_ID: int  # ТГ создателя; нужен, чтобы присылались баги от юзеров на мой тг акк и логгировались ошибки
    PAGE_LIMIT: int = 10
    BUTTONS_PAGE_LIMIT: int = 5

    OCAPS_DOWNLOAD: bool = True
    OCAPS_PATH: Path = "./ocaps"
    OCAPS_PLY_VEHICLES_SPREAD_COORDS: int

    SEND_LOGS_TO_DEV: bool = True
    LOGS_PATH: Path = "./logs"

    USE_PROXY: bool = False
    PROXY_PROTOCOL: str = "http"
    PROXY_LOGIN: str = ""
    PROXY_PASSWORD: str = ""
    PROXY_IP: str = ""
    PROXY_PORT: str = ""

    WEB_APP_URI: str = "https://t.me/RE_ArmaBot/scheduler"
    WEB_APP_INIT_DATA_MAX_AGE_SECONDS: int = 86400
    WEB_APP_DEV_TELEGRAM_ID: int | None = None
    WEB_APP_DEBUG_CODE: str = ""
    WEB_APP_DEBUG_TOKEN_TTL_SECONDS: int = 604800

    @staticmethod
    def from_file(path: str | None = None) -> "BotSettings":
        path = resolve_config_path(path)
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
                value = config.get(section, option).strip()
                key = option.upper()
                if key == "WEB_APP_DEV_TELEGRAM_ID" and not value:
                    continue
                if key == "WEB_APP_DEBUG_CODE" and not value:
                    continue
                data[key] = value

            return BotSettings(**data)


WEB_APP_URI: str = BotSettings.from_file().WEB_APP_URI

