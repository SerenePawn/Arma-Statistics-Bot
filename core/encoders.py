from datetime import datetime
from decimal import Decimal
from uuid import UUID


def json_default_encoder(obj: object) -> str | None:
    if isinstance(obj, Decimal | UUID | datetime):
        return str(obj)

    return None
