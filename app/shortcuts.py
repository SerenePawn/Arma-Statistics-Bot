from hashlib import md5

from aiogram.enums import ChatMemberStatus
from aiogram.types import Message

from core.app_state import AppState


async def admin_only(message: Message, user_id: int | None = None):
    user = await AppState().bot.get_chat_member(message.chat.id, user_id or message.from_user.id)
    if user.status not in {ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR}:
        return


def allow_msg_edit(old_hash: str, message: str) -> str | None:
    """
    Возвращает новый хэш, если редактирование разрешено.
    :param old_hash:
    :param message:
    :return:
    """
    new_hash = md5(message.encode()).hexdigest()
    if new_hash != old_hash:
        return new_hash
