from contextlib import suppress

from aiogram import types, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command

from app.kill_log.shortcuts import edit_ui_with_ocap
from core.app_state import AppState
from logic.squads import db as squads_db

router = Router()


@router.message(Command("tvt1", "tvt2", "if", prefix="!", ignore_case=True, ignore_mention=True))
async def get_ocap_info(message: types.Message):
    with suppress(TelegramBadRequest):
        await message.delete()
    app_state = AppState()
    squad = await squads_db.get_by_chat(app_state.conn, message.chat.id, message.message_thread_id)
    await edit_ui_with_ocap(squad, message, message.text)
