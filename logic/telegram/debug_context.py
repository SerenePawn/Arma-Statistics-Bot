from contextvars import ContextVar

_debug_admin_telegram_id: ContextVar[int | None] = ContextVar("debug_admin_telegram_id", default=None)


def set_debug_admin_telegram_id(telegram_id: int | None) -> None:
    _debug_admin_telegram_id.set(telegram_id)


def get_debug_admin_telegram_id() -> int | None:
    return _debug_admin_telegram_id.get()
