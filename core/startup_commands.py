from enum import StrEnum

from core.db.db import migrate_up


STARTUP_PARAMS = {
    "--migrate": migrate_up
}


class StartupParams(StrEnum):
    MIGRATE = "--migrate"
