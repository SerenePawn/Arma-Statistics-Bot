from aiogram.types import Message

from app.main_menu.markup import build_group_menu
from core.app_state import AppState
from logic.squads import db as squads_db
from logic.squads.models import Squad


async def main_menu_open(message: Message, squad: Squad | None = None):
    app_state = AppState()
    await app_state.bot.send_message(
        message.chat.id,
        message_thread_id=message.message_thread_id,
        text="Перед взаимодействием с ботом, напишите ему в личку /start\nГлавное меню",
        reply_markup=build_group_menu(message.chat.id),
        protect_content=True,
        disable_notification=True
    )
    await main_menu_ui_open(message, squad)


async def main_menu_ui_open(message: Message, squad: Squad | None = None):
    app_state = AppState()
    _squad = squad or await squads_db.get_by_chat(app_state.conn, message.chat.id, message.message_thread_id)
    ui_message = await app_state.bot.send_message(
        message.chat.id,
        message_thread_id=message.message_thread_id,
        text="Это служебное сообщение, не удаляйте его. Здесь будет появляться инфа от тыкалок.",
        protect_content=True,
        disable_notification=True
    )
    await squads_db.update(app_state.conn, _squad.id, ui_message_id=ui_message.message_id)


async def main_menu_edit(message: Message):
    await message.edit_text(
        text="Перед взаимодействием с ботом, чирканите ему в личку /start\nГлавное меню",
        reply_markup=build_group_menu(message.chat.id),
    )
