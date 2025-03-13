from aiogram.types import Message

from app.admin_menu.markup import ADMIN_MENU_SETTINGS
from core.app_state import AppState


async def admin_menu_open(message: Message):
    await AppState().bot.send_message(
        message.chat.id,
        message_thread_id=message.message_thread_id,
        text="Панель управления (Админ сервера)",
        reply_markup=ADMIN_MENU_SETTINGS,
        protect_content=True,
        disable_notification=True
    )


async def admin_menu_edit(message: Message):
    await message.edit_text(
        text="Панель управления (Админ сервера)",
        reply_markup=ADMIN_MENU_SETTINGS
    )