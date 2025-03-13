from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from logic.schedules import db as schedules_db

from core.app_state import AppState
from logic.schedules.misc import DAYS_OF_WEEK


async def get_keyboard(message: Message, operational_markup: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    schedules = await schedules_db.get_presets_by_chat(
        AppState().conn,
        message.chat.id,
        message.message_thread_id
    )
    schedules.sort(key=lambda x: (
        x.game_day_of_week,
        x.game_time,
    ))
    return InlineKeyboardMarkup(inline_keyboard=[
        *[
            [
                InlineKeyboardButton(
                    text=f"{i.game_name} в {DAYS_OF_WEEK[i.game_day_of_week].lower()} {i.game_time.strftime("%H:%M")}",
                    callback_data=f"admin_menu_settings_schedule_preset_delete_{i.id}"
                )
            ]
            for i in schedules
        ],
        operational_markup,
    ])