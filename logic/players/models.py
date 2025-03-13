from datetime import datetime

from pydantic import BaseModel


class PlayerForm(BaseModel):
    name: str
    squad_id: int
    telegram_id: int


class Player(BaseModel):
    id: int
    name: str
    squad_id: int
    telegram_id: int
    created_at: datetime
