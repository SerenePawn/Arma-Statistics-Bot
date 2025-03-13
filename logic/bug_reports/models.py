from datetime import datetime

from pydantic import BaseModel


class BugReportForm(BaseModel):
    telegram_id: int
    telegram_tag: str
    description: str


class BugReport(BaseModel):
    id: int
    telegram_id: int
    telegram_tag: str
    description: str
    solved: bool
    created_at: datetime
