from datetime import datetime, time

from pydantic import BaseModel, field_validator


class SchedulePresetForm(BaseModel):
    game_name: str
    game_time: str
    game_day_of_week: int

    @field_validator("game_time", mode="before")
    @classmethod
    def transform_time(cls, v: time) -> str:
        return v.strftime('%H:%M:00')


class ScheduleForm(BaseModel):
    player_id: int
    schedule_preset_id: int
    will_attend_default: bool


class SchedulePreset(BaseModel):
    id: int
    squad_id: int
    game_name: str
    game_time: time
    game_day_of_week: int
    created_at: datetime

    @field_validator("game_time", mode="before")
    @classmethod
    def transform_time(cls, v: str) -> time:
        return time(*[int(i) for i in v.split(":")])


class Schedule(BaseModel):
    id: int
    player_id: int
    schedule_preset_id: int
    will_attend_default: bool
    created_at: datetime
