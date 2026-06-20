from hashlib import md5


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
