#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/root/projects/asb}"

cd "$APP_DIR"

.venv/bin/python - <<'PY'
import asyncio

from core.db.db import migrate_up
from core.settings import BotSettings, resolve_config_path


async def main() -> None:
    settings = BotSettings.from_file(resolve_config_path())
    await migrate_up(settings)


asyncio.run(main())
PY
