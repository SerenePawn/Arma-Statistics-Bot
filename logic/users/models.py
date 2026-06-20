from datetime import datetime

from pydantic import BaseModel


class UserPreferences(BaseModel):
    telegram_id: int
    primary_squad_id: int | None
    created_at: datetime
    updated_at: datetime
