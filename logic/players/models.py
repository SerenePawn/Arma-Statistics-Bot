from datetime import datetime

from pydantic import BaseModel


class PlayerForm(BaseModel):
    squad_id: int
    telegram_id: int
    telegram_tag: str
    name: str


class Player(BaseModel):
    id: int
    squad_id: int
    telegram_id: int
    telegram_tag: str
    name: str
    created_at: datetime
