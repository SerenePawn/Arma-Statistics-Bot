from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


ADMIN_MENU_SETTINGS = InlineKeyboardMarkup(inline_keyboard=[
    # [InlineKeyboardButton(text="Добавить игрока в отряд", callback_data="admin_menu_settings_add_to_squad")],
    # [InlineKeyboardButton(text="Убрать игрока из отряда", callback_data="admin_menu_settings_remove_from_squad")],
    [InlineKeyboardButton(text="Изменить тэг отряда", callback_data="admin_menu_settings_name_tag")],
    [InlineKeyboardButton(text="Изменить название отряда", callback_data="admin_menu_settings_squad_name")],
    [InlineKeyboardButton(text="Изменить расписание игр", callback_data="admin_menu_settings_schedule")],
    [InlineKeyboardButton(text="Закрыть", callback_data="admin_menu_close")],
])
