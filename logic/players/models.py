from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from logic.games.models import parse_games_ids


class PlayerForm(BaseModel):
    squad_id: int
    telegram_id: int
    telegram_tag: str
    name: str
    games_ids: list[int] = Field(default_factory=list)


class Player(BaseModel):
    id: int
    squad_id: int
    telegram_id: int
    telegram_tag: str
    name: str
    games_ids: list[int] = Field(default_factory=list)
    created_at: datetime

    @field_validator("games_ids", mode="before")
    @classmethod
    def normalize_games_ids(cls, v: object) -> list[int]:
        return parse_games_ids(v)
