CHAT_START_PARAM_PREFIX = "chat_"


def chat_start_param(chat_id: int) -> str:
    return f"{CHAT_START_PARAM_PREFIX}{chat_id}"


def parse_chat_id_from_start_param(start_param: str) -> int | None:
    if not start_param.startswith(CHAT_START_PARAM_PREFIX):
        return None
    try:
        return int(start_param[len(CHAT_START_PARAM_PREFIX):])
    except ValueError:
        return None
