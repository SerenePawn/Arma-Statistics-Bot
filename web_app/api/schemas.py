from datetime import date, datetime, time
from enum import StrEnum

from pydantic import BaseModel, Field


class AttendStatus(StrEnum):
    WILL_ATTEND = "will_attend"
    WILL_NOT_ATTEND = "will_not_attend"
    DOUBTS = "doubts"


class GameOut(BaseModel):
    id: int
    title: str


class SquadOut(BaseModel):
    id: int
    name: str
    tags: list[str]
    games: list[GameOut] = Field(default_factory=list)
    main_game_ids: list[int] = Field(default_factory=list)


class PlayerOut(BaseModel):
    id: int
    squad_id: int | None = None
    squad_name: str | None = None
    telegram_id: int
    telegram_tag: str
    name: str
    created_at: datetime | None = None
    games: list[GameOut] = Field(default_factory=list)


class MeOut(BaseModel):
    telegram_id: int
    telegram_tag: str
    display_name: str
    memberships: list[PlayerOut] = Field(default_factory=list)
    primary_squad_id: int | None = None
    context_squad_id: int | None = None
    player: PlayerOut | None = None
    is_squad_admin: bool = False
    is_admin_of_squad_id: int | None = None
    squad_relation: str | None = None
    launch_source: str = "dm"
    launch_squad_id: int | None = None
    can_create_squad: bool = False
    default_game_id: int | None = None
    is_debug_admin: bool = False


class DebugUnlockIn(BaseModel):
    code: str = Field(min_length=1, max_length=200)


class DebugUnlockOut(BaseModel):
    token: str
    expires_at: datetime


class CreateSquadFromChatIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    tags: str = Field(min_length=1, max_length=100)


class RegisterPlayerIn(BaseModel):
    squad_id: int | None = None
    name: str = Field(min_length=1, max_length=50)


class PrimarySquadIn(BaseModel):
    squad_id: int | None = None


class PlayerNameUpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class GamesUpdateIn(BaseModel):
    game_ids: list[int] = Field(default_factory=list)
    main_game_ids: list[int] = Field(default_factory=list)


class SquadGameCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=50)


class SchedulePresetOut(BaseModel):
    id: int
    title: str
    game_time: time
    game_day_of_week: int
    recurrence_type: str = "weekly"
    recurrence_date: date | None = None
    day_of_month: int | None = None
    will_attend_default: bool | None = None
    game: GameOut | None = None


class SchedulePresetCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=50)
    game_id: int | None = None
    game_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    recurrence_type: str = Field(pattern="^(weekly|monthly|once)$")
    game_day_of_week: int | None = Field(default=None, ge=0, le=6)
    recurrence_date: date | None = None
    day_of_month: int | None = Field(default=None, ge=1, le=31)


class SchedulePresetUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=50)
    game_id: int | None = None
    game_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    recurrence_type: str | None = Field(default=None, pattern="^(weekly|monthly|once)$")
    game_day_of_week: int | None = Field(default=None, ge=0, le=6)
    recurrence_date: date | None = None
    day_of_month: int | None = Field(default=None, ge=1, le=31)


class ScheduleUpdateIn(BaseModel):
    will_attend_default: bool | None


class AttendanceOut(BaseModel):
    schedule_preset: SchedulePresetOut
    attend_status: AttendStatus | None = None
    weekly_attend_status: AttendStatus | None = None
    comment: str = ""


class AttendanceUpdateIn(BaseModel):
    attend_status: AttendStatus | None
    comment: str = Field(default="", max_length=100)


class AttendancePlayerOut(BaseModel):
    player_name: str
    attend_status: AttendStatus
    comment: str = ""


class AttendanceSummaryOut(BaseModel):
    schedule_preset: SchedulePresetOut
    players: list[AttendancePlayerOut]


class SquadRequestIn(BaseModel):
    request_type: str = Field(pattern="^(join|friend)$")


class SquadRequestOut(BaseModel):
    id: int
    squad_id: int
    telegram_id: int
    player_id: int
    request_type: str
    status: str
    player_name: str | None = None
    created_at: datetime | None = None


class SquadMemberOut(BaseModel):
    id: int
    telegram_id: int
    display_name: str = ""
    name: str
    is_telegram_admin: bool = False


class SquadFriendOut(BaseModel):
    id: int
    telegram_id: int
    display_name: str = ""
    name: str


class BlockedUserOut(BaseModel):
    telegram_id: int
    player_id: int
    player_name: str
    blocked_at: datetime
