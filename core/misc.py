import logging
import traceback
from datetime import datetime, timedelta, time
from typing import Callable

from aiogram.exceptions import TelegramBadRequest

from core.app_state import AppState


def time_to_sleep(hour: int, minute: int = 0, second: int = 0) -> float:
    """Получает секунды до указанного времени (на текущий день, или на следующий, если время прошло)"""
    time_now = datetime.now()
    time_dest = time_now.replace(hour=hour, minute=minute, second=second)

    if time_dest - time_now <= timedelta(0):
        time_dest = time_dest.replace(day=time_dest.day + 1)

    return (time_dest - time_now).total_seconds()


async def run_timer(state: AppState, wait_time: time | int | float, coro: Callable, *coro_args, **coro_kwargs):
    """

    :param state:
    :param coro:
    :param wait_time: time to run at defined time. int | float to run with seconds interval.
    :return:
    """
    while not state.shutdown_event.is_set():
        if isinstance(wait_time, time):
            delay = time_to_sleep(wait_time.hour, wait_time.minute, wait_time.second)
        else:
            delay = wait_time

        state.shutdown_event.wait(delay)

        try:
            await coro(state, *coro_args, **coro_kwargs)
        except ValueError as exc:
            logging.error(f"DB connection lost: [state={state}] {exc}")
        except TelegramBadRequest as exc:
            logging.error(f"TG Request failed: [args={coro_args}, kwargs={coro_kwargs}] {exc}")
        except Exception:
            logging.error(f"Unexpected exception: [args={coro_args}, kwargs={coro_kwargs}] {traceback.format_exc()}")
