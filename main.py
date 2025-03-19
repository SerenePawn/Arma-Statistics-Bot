import asyncio
import sys
import traceback
from asyncio import CancelledError

from loguru import logger

from app.main_router import router as main_router
from core.app_state import AppState
from core.logger import configure_logger
from core.middleware import HandledLoggerMiddleware
from core.runtime import startup_app, shutdown_app
from core.startup_commands import STARTUP_PARAMS


async def main(_state: AppState, params: list[str]):
    configure_logger(_state)
    logger.info("Arma bot startup")
    try:
        # Add middlewares
        main_router.message.middleware(HandledLoggerMiddleware())
        main_router.callback_query.middleware(HandledLoggerMiddleware())

        # Include main router
        _state.dispatcher.include_router(main_router)

        # Startup back
        await startup_app(params)
    except CancelledError:
        pass
    except (Exception, BaseException):
        logger.error(f"Failed arma bot runtime: {traceback.format_exc()}")
    finally:
        await shutdown_app()


if __name__ == "__main__":
    args = sys.argv[1:]
    for i in args:
        if i not in STARTUP_PARAMS:
            print(f"Such param ('{i}') does not exists. Existing params: {','.join([f"'{j}'" for j in STARTUP_PARAMS])}.")
            sys.exit()

    state = AppState()
    asyncio.run(main(state, args))
    sys.exit()
