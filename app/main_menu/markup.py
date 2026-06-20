from urllib.parse import quote

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from core.settings import WEB_APP_URI
from core.telegram_webapp import chat_start_param


def _is_direct_telegram_link(url: str) -> bool:
    return url.startswith("https://t.me/") or url.startswith("http://t.me/")


def group_webapp_url(chat_id: int) -> str:
    if _is_direct_telegram_link(WEB_APP_URI):
        separator = "&" if "?" in WEB_APP_URI else "?"
        return f"{WEB_APP_URI}{separator}startapp={quote(chat_start_param(chat_id), safe='')}"
    return WEB_APP_URI


def build_group_menu(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть приложение", url=group_webapp_url(chat_id))],
    ])


def build_private_menu() -> InlineKeyboardMarkup:
    if _is_direct_telegram_link(WEB_APP_URI):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Открыть приложение", url=WEB_APP_URI)],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть приложение", web_app=WebAppInfo(url=WEB_APP_URI))],
    ])


MARKUP_MAIN_MENU = build_private_menu()
