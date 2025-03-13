from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

MARKUP_MAIN_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Кто будет на неделе", callback_data="main_menu_attendance")],
    [InlineKeyboardButton(text="Килл-лог за последнюю игру", callback_data="main_menu_kill_log")],
    [InlineKeyboardButton(text="Настроить свое расписание", callback_data="main_menu_schedule_settings")],
    [InlineKeyboardButton(text="Зарегистрировать ник A3", callback_data="main_menu_register_player")],
])
