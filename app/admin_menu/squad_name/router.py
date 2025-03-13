from contextlib import suppress

from aiogram import types, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.admin_menu.fsm import AdminFSM
from app.admin_menu.misc import admin_menu_edit
from app.shortcuts import admin_only
from core.app_state import AppState
from logic.squads import db as squads_db

router = Router()


@router.callback_query(F.data == 'admin_menu_settings_squad_name')
async def admin_menu_settings_squad_name(callback: CallbackQuery, state: FSMContext):
    await admin_only(callback.message, callback.from_user.id)
    await state.set_state(AdminFSM.squad_name)

    squad_name_msg = await callback.message.edit_text(
        text=f"[@{callback.from_user.username}] Введите название вашего отряда в чат (не более 50 символов)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="admin_common_cancel")]
        ])
    )
    await state.update_data(
        init_tg_username=callback.from_user.username,
        squad_name_msg=squad_name_msg
    )


@router.message(AdminFSM.squad_name)
async def fsm_settings_squad_name(message: types.Message, state: FSMContext):
    await admin_only(message)
    data = await state.get_data()

    if data["init_tg_username"] != message.from_user.username:
        return

    squad = await squads_db.get_by_chat(AppState().conn, message.chat.id, message.message_thread_id)
    await squads_db.update(AppState().conn, squad.id, name=message.text[:50])
    # Чистки последних сбщ
    with suppress(TelegramBadRequest):
        await message.delete()
    await admin_menu_edit(data["squad_name_msg"])
