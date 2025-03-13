from datetime import datetime

from pydantic import BaseModel, field_validator


class SquadForm(BaseModel):
    telegram_chat_id: int
    telegram_chat_thread_id: int
    ui_message_id: int | None = None
    ui_message_hash: str | None = None
    name: str
    tags: str


class Squad(BaseModel):
    id: int
    telegram_chat_id: int
    telegram_chat_thread_id: int | None = None
    ui_message_id: int | None = None
    ui_message_hash: str | None = None
    name: str
    tags: list[str]
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
