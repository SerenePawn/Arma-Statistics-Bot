import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.settings import BotSettings, resolve_config_path  # noqa: E402


def load_settings() -> BotSettings:
    return BotSettings.from_file(resolve_config_path())


_settings = load_settings()

INIT_DATA_MAX_AGE_SECONDS = _settings.WEB_APP_INIT_DATA_MAX_AGE_SECONDS
DEV_TELEGRAM_ID = _settings.WEB_APP_DEV_TELEGRAM_ID or None
