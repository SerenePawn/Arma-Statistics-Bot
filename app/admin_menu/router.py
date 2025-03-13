from contextlib import suppress

from aiogram import types, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.admin_menu.misc import admin_menu_open as adm_panel_open
from app.shortcuts import admin_only
from core.app_state import AppState
from logic.squads import db as squads_db

router = Router()


@router.message(F.chat.type.in_({"group", "supergroup"}), Command("admin_asb"))
async def admin_menu_open(message: types.Message):
    squad = await squads_db.get_by_chat(AppState().conn, message.chat.id, message.message_thread_id)

    if not squad or not (squad.telegram_chat_id and squad.telegram_chat_thread_id):
        user = await AppState().bot.get_chat_member(message.chat.id, message.from_user.id)
        if user.status not in {ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR}:
            return
        await message.reply("Отряд не зарегистрирован. "
                            "Пройдите регистрацию, написав `/start_asb` в нужном канале/теме")
        return

    with suppress(TelegramBadRequest):
        await message.delete()
    await adm_panel_open(message)


# @router.callback_query(F.data == 'admin_menu_settings_add_to_squad')
# async def admin_menu_settings_add_to_squad(callback: CallbackQuery, state: FSMContext):
#     await state.set_state(AdminFSM.add_to_squad)
#
#     await AppState().bot.send_message(
#         callback.chat.id,
#         message_thread_id=callback.message_thread_id,
#         text="Введите ник игрока ниже",
#         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
#             [
#                 InlineKeyboardButton(text="Отмена", callback_data="admin_menu_settings_mates_edit_cancel"),
#                 InlineKeyboardButton(text="Подтвердить", callback_data="admin_menu_settings_mates_edit_cancel")
#             ],
#         ])
#     )
#
#     await state.set_data({})
#     await callback.message.delete()


# @router.callback_query(F.data == 'admin_menu_settings_remove_from_squad')
# async def admin_menu_settings_remove_from_squad(callback: CallbackQuery, state: FSMContext):
#     await state.set_state(None)
#     await callback.message.delete()


@router.callback_query(F.data == 'admin_menu_close')
async def admin_menu_close(callback: CallbackQuery, state: FSMContext):
    await admin_only(callback.message, callback.from_user.id)
    await state.set_state(None)
    await callback.message.delete()
