from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from logic.telegram.debug_context import get_debug_admin_telegram_id

ADMIN_STATUSES = frozenset({ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR})


async def get_chat_member_status(
    bot: Bot,
    chat_id: int,
    user_id: int,
) -> ChatMemberStatus | None:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status
    except (TelegramBadRequest, TelegramForbiddenError):
        return None


def chat_member_display_name(member_user: object) -> str:
    first_name = getattr(member_user, "first_name", None)
    last_name = getattr(member_user, "last_name", None)
    username = getattr(member_user, "username", None)
    user_id = getattr(member_user, "id", None)
    name = " ".join(part for part in (first_name, last_name) if part).strip()
    return name or username or str(user_id or "")


async def get_chat_member_status_and_display_name(
    bot: Bot,
    chat_id: int,
    user_id: int,
) -> tuple[ChatMemberStatus | None, str]:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status, chat_member_display_name(member.user)
    except (TelegramBadRequest, TelegramForbiddenError):
        return None, ""


async def is_chat_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    if get_debug_admin_telegram_id() == user_id:
        return True
    status = await get_chat_member_status(bot, chat_id, user_id)
    return status in ADMIN_STATUSES if status is not None else False
