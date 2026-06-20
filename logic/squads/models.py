from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from logic.games.models import parse_games_ids
from logic.squads.friends import parse_friends_ids


class SquadForm(BaseModel):
    telegram_chat_id: int
    telegram_chat_thread_id: int | None = None
    ui_message_id: int | None = None
    ui_message_hash: str | None = None
    name: str
    tags: str
    games_ids: list[int] = Field(default_factory=list)
    main_game_ids: list[int] = Field(default_factory=list)
    friends_ids: list[int] = Field(default_factory=list)


class Squad(BaseModel):
    id: int
    telegram_chat_id: int | None = None
    chatters_id: int | None = None
    telegram_chat_thread_id: int | None = None
    ui_message_id: int | None = None
    ui_message_hash: str | None = None
    name: str
    tags: list[str]
    games_ids: list[int] = Field(default_factory=list)
    main_game_ids: list[int] = Field(default_factory=list)
    friends_ids: list[int] = Field(default_factory=list)
    created_at: datetime

    @field_validator("telegram_chat_thread_id", mode="before")
    @classmethod
    def empty_field_is_none(cls, v: str) -> str | None:
        if v:
            return v

    @field_validator("tags", mode="before")
    @classmethod
    def convert_tags(cls, v: str) -> list[str]:
        return v.split(",")

    @field_validator("games_ids", mode="before")
    @classmethod
    def normalize_games_ids(cls, v: object) -> list[int]:
        return parse_games_ids(v)

    @field_validator("main_game_ids", mode="before")
    @classmethod
    def normalize_main_game_ids(cls, v: object) -> list[int]:
        return parse_games_ids(v)

    @field_validator("friends_ids", mode="before")
    @classmethod
    def normalize_friends_ids(cls, v: object) -> list[int]:
        return parse_friends_ids(v)
