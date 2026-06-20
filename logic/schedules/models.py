from datetime import date, datetime, time

from pydantic import BaseModel, field_validator, model_validator

from logic.schedules.recurrence import RecurrenceType


class SchedulePresetForm(BaseModel):
    name: str
    game_id: int | None = None
    game_time: str
    game_day_of_week: int
    recurrence_type: RecurrenceType = RecurrenceType.WEEKLY
    recurrence_date: date | None = None
    day_of_month: int | None = None

    @field_validator("game_time", mode="before")
    @classmethod
    def transform_time(cls, v: time | str) -> str:
        if isinstance(v, time):
            return v.strftime("%H:%M:00")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Event title is required")
        return clean

    @model_validator(mode="after")
    def validate_recurrence(self) -> "SchedulePresetForm":
        if self.recurrence_type == RecurrenceType.WEEKLY:
            if not 0 <= self.game_day_of_week <= 6:
                raise ValueError("Weekday must be between 0 and 6")
            return self
        if self.recurrence_type == RecurrenceType.MONTHLY:
            if self.day_of_month is None or not 1 <= self.day_of_month <= 31:
                raise ValueError("Day of month must be between 1 and 31")
            return self
        if self.recurrence_date is None:
            raise ValueError("Date is required for one-time events")
        self.game_day_of_week = self.recurrence_date.weekday()
        return self


class ScheduleForm(BaseModel):
    player_id: int
    schedule_preset_id: int
    will_attend_default: bool


class SchedulePreset(BaseModel):
    id: int
    squad_id: int
    name: str | None = None
    game_id: int | None = None
    game_title: str | None = None
    game_time: time
    game_day_of_week: int
    recurrence_type: RecurrenceType = RecurrenceType.WEEKLY
    recurrence_date: date | None = None
    day_of_month: int | None = None
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
