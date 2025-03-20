import asyncio
import threading
from asyncio import AbstractEventLoop
from datetime import time
from sqlite3 import Cursor, Row

from loguru import logger

from core.app_state import AppState
from core.background import send_attendances, parse_ocaps
from core.db.db import init
from core.misc import run_timer
from core.startup_commands import StartupParams, STARTUP_PARAMS


def bg_attendances(state: AppState, loop: AbstractEventLoop):
    asyncio.run(run_timer(state, time(10), send_attendances, loop))


def bg_ocaps(state: AppState, loop: AbstractEventLoop):
    asyncio.run(run_timer(state, 60, parse_ocaps, loop))


async def startup_app(params: list[str]):
    logger.info("Init state")
    state = AppState()

    state.conn = await init(state.config)

    if StartupParams.MIGRATE in params:
        logger.info("Start db migrate")
        await STARTUP_PARAMS[StartupParams.MIGRATE](state.config)

    logger.info("Init bg tasks")
    bg_loop = asyncio.get_event_loop()
    state.background_tasks_threads.extend((
        threading.Thread(target=bg_ocaps, args=(state, bg_loop), daemon=True),
        threading.Thread(target=bg_attendances, args=(state, bg_loop), daemon=True),
    ))
    for thread in state.background_tasks_threads:
        thread.start()

    logger.info("Startup complete; Start TG polling")
    await state.dispatcher.start_polling(state.bot)


async def shutdown_app():
    logger.info("Shutdown...")
    state = AppState()
    state.shutdown_event.set()

    logger.info("Stopping background tasks (may take few minutes)...")
    for thread in state.background_tasks_threads:
        thread.join()

    logger.info("Closing db connection")
    if state.conn:
        await state.conn.close()
    logger.info("Closing bot session connection")
    await state.bot.session.close()
    logger.info("Shutdown complete")
