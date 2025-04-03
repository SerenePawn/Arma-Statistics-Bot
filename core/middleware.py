import traceback
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from aiogram.utils.formatting import Text, Pre, as_list, Code, as_line
from loguru import logger

from core.app_state import AppState
from core.context import AppRequest

app_state = AppState()


class HandledLoggerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ):
        AppRequest.gen_id()
        user = event.from_user
        tg_id = user.id
        username = user.username

        log_data = ""
        if isinstance(event, Message):
            log_data = f"Command text='{event.text}'"
        elif isinstance(event, CallbackQuery):
            log_data = (f"Callback data='{event.data}', "
                        f"msg_id={event.message.message_id}, "
                        f"msg_thread_id={event.message.message_thread_id}")

        log_text = f"({AppRequest.id()}) [tg_id={tg_id}:username=@{username}] >>> {log_data}"
        logger.debug(log_text)
        try:
            return await handler(event, data)
        except Exception as exc:
            logger.exception(
                log_text
            )
            await app_state.bot.send_message(
                app_state.config.DEV_TG_ID,
                **as_list(
                    as_line(
                        "(", Code(str(AppRequest.id())), ")",
                        " [tg_id=", Code(str(tg_id)), ":", "username=", f"@{username}", "]",
                    ),
                    as_line(
                        log_data
                    ),
                    f"Exception: ", Pre(traceback.format_exc()),
                    sep=""
                ).as_kwargs()
            )
