from datetime import datetime

from pydantic import BaseModel

from logic.attendances.enums import AttendStatus
from logic.schedules.models import SchedulePreset


class AttendanceForm(BaseModel):
    schedule_preset_id: int
    player_id: int
    attend_status: AttendStatus
    comment: str = ""


class Attendance(BaseModel):
    id: int
    schedule_preset_id: int
    attend_status: AttendStatus
    comment: str
    created_at: datetime


class AttendanceDetail(BaseModel):
    schedule_preset: SchedulePreset
    player_name: str
    attend_status: AttendStatus
    comment: str
    created_at: datetime
