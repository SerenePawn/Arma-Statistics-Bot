import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from fastapi import HTTPException, status

from .config import DEV_TELEGRAM_ID, INIT_DATA_MAX_AGE_SECONDS
from core.telegram_webapp import parse_chat_id_from_start_param


@dataclass(frozen=True)
class TelegramUser:
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    launch_chat_id: int | None = None
    launch_source: str = "dm"

    @property
    def tag(self) -> str:
        return self.username or str(self.id)

    @property
    def display_name(self) -> str:
        name = " ".join(part for part in (self.first_name, self.last_name) if part).strip()
        return name or self.username or str(self.id)


def _parse_launch_context(pairs: dict[str, str]) -> tuple[int | None, str]:
    chat_type = pairs.get("chat_type", "")
    chat_raw = pairs.get("chat")
    start_param = pairs.get("start_param", "")

    launch_chat_id = None

    if chat_raw:
        try:
            chat_payload = json.loads(chat_raw)
            launch_chat_id = int(chat_payload["id"])
            chat_type = chat_type or chat_payload.get("type", "")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass

    if launch_chat_id is None:
        launch_chat_id = parse_chat_id_from_start_param(start_param)

    if chat_type in {"group", "supergroup", "channel"}:
        return launch_chat_id, "squad_chat"

    if chat_type in {"sender", "private"}:
        return launch_chat_id, "dm"

    if not chat_type:
        return launch_chat_id, "dm"

    if launch_chat_id is not None and start_param.startswith("chat_"):
        return launch_chat_id, "squad_chat"

    return launch_chat_id, "unknown"


def validate_init_data(init_data: str, bot_token: str) -> TelegramUser:
    init_data = init_data.strip()
    bot_token = bot_token.strip()

    if not init_data and DEV_TELEGRAM_ID:
        return TelegramUser(id=int(DEV_TELEGRAM_ID), username="dev", launch_source="dm")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise_auth_error()

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise_auth_error()

    auth_date = int(pairs.get("auth_date", "0") or "0")
    if INIT_DATA_MAX_AGE_SECONDS > 0 and time.time() - auth_date > INIT_DATA_MAX_AGE_SECONDS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram auth data expired")

    try:
        user_payload = json.loads(pairs["user"])
    except (KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram auth data",
        ) from exc

    launch_chat_id, launch_source = _parse_launch_context(pairs)

    return TelegramUser(
        id=int(user_payload["id"]),
        username=user_payload.get("username"),
        first_name=user_payload.get("first_name"),
        last_name=user_payload.get("last_name"),
        launch_chat_id=launch_chat_id,
        launch_source=launch_source,
    )


def raise_auth_error() -> None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram auth data")
