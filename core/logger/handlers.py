import asyncio
import traceback

from loguru import logger

from core.app_state import AppState

app_state = AppState()


def catch_exception_tg(exception: BaseException):
    logger.exception(f"Fired exception: {traceback.format_exception(exception)}")
    asyncio.run(
        app_state.bot.send_message(
            app_state.config.DEV_TG_ID,
            text=f"FCKD {exception=}"
        )
    )