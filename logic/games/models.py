from datetime import datetime

from pydantic import BaseModel


class GameForm(BaseModel):
    title: str


class Game(BaseModel):
    id: int
    title: str
    created_at: datetime


def parse_games_ids(v: object) -> list[int]:
    if v is None:
        return []
    if isinstance(v, list):
        return [int(item) for item in v]
    return []
