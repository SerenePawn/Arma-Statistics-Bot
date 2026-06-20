from core.app_state import AppState
from core.db import db
from core.db.db import record_to_model, record_to_model_list
from logic.bug_reports.models import BugReport, BugReportForm


async def create(form: BugReportForm) -> int:
    conn = AppState().conn
    result = await db.create(
        conn,
        table="bug_reports",
        data=form.model_dump(),
    )
    return result["id"]


async def get_list(page: int) -> list[BugReport]:
    conn = AppState().conn
    limit = AppState().config.PAGE_LIMIT
    offset = max(page - 1, 0) * limit
    result = await db.get_raw(
        conn,
        """
        SELECT *
        FROM bug_reports
        ORDER BY solved, id
        LIMIT $1 OFFSET $2
        """,
        [limit, offset],
    )
    if not result:
        return []
    return record_to_model_list(BugReport, result)


async def get_total() -> int:
    conn = AppState().conn
    result = await db.get_total(
        conn,
        "bug_reports",
    )
    return result


async def update(bug_id: int, **data) -> BugReport:
    conn = AppState().conn
    result = await db.update(
        conn,
        pk=int(bug_id),
        table="bug_reports",
        data=data,
        with_updated_at=False
    )
    return record_to_model(BugReport, result)
