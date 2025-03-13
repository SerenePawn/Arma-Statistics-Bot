from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from loguru import logger


class HandledLoggerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ):
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

        logger.debug(f"[tg_id={tg_id}:username=@{username}] >>> {log_data}")
        return await handler(event, data)
