import hashlib
import hmac
import time


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_debug_token(telegram_id: int, secret: str, ttl_seconds: int) -> tuple[str, int]:
    expires_at = int(time.time()) + ttl_seconds
    payload = f"{telegram_id}:{expires_at}"
    token = f"{payload}:{_sign(payload, secret)}"
    return token, expires_at


def verify_debug_token(token: str, telegram_id: int, secret: str) -> bool:
    token = token.strip()
    if not token or token.count(":") < 2:
        return False

    payload, received_sig = token.rsplit(":", 1)
    if not hmac.compare_digest(_sign(payload, secret), received_sig):
        return False

    try:
        user_part, exp_part = payload.split(":", 1)
        if int(user_part) != telegram_id:
            return False
        if int(exp_part) < time.time():
            return False
    except ValueError:
        return False

    return True
