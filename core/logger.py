import sys
from pathlib import Path

from loguru import logger

from core.app_state import AppState


def configure_logger(app_state: AppState):
    _format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    logger.add(
        Path(app_state.config.LOGS_PATH).joinpath("asb__{time:YYYY_MM_DD}.log"),
        level="DEBUG",
        format=_format,
        rotation="00:00",
    )
