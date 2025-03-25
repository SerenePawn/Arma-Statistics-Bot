import asyncio

from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger

from core.app_state import AppState
from core.background import send_attendances, parse_ocaps
from core.db.db import init
from core.startup_commands import StartupParams, STARTUP_PARAMS


async def startup_app(params: list[str]):
    logger.info("Init state")
    state = AppState()

    state.conn = await init(state.config)

    if StartupParams.MIGRATE in params:
        logger.info("Start db migrate")
        await STARTUP_PARAMS[StartupParams.MIGRATE](state.config)

    logger.info("Init bg tasks")
    bg_loop = asyncio.get_event_loop()

    scheduler = BackgroundScheduler(timezone="Europe/Moscow")
    scheduler.add_job(lambda: bg_loop.create_task(parse_ocaps(state, bg_loop)), "cron", second=0)
    scheduler.add_job(lambda: bg_loop.create_task(send_attendances(state, bg_loop)), "cron", hour=12, minute=0)
    scheduler.start()

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
