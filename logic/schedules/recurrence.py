import calendar
from datetime import date, timedelta
from enum import StrEnum


class RecurrenceType(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ONCE = "once"


def week_end(week_start: date) -> date:
    return week_start + timedelta(days=6)


def monthly_occurrence_on_date(year: int, month: int, day_of_month: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day_of_month, last_day))


def monthly_occurrence_in_week(week_start: date, day_of_month: int) -> date | None:
    for offset in (0, 1):
        probe = week_start + timedelta(days=offset * 7)
        occurrence = monthly_occurrence_on_date(probe.year, probe.month, day_of_month)
        if week_start <= occurrence <= week_end(week_start):
            return occurrence
    return None


def preset_occurrence_in_week(preset: dict, week_start: date) -> date | None:
    recurrence_type = preset.get("recurrence_type") or RecurrenceType.WEEKLY

    if recurrence_type == RecurrenceType.WEEKLY:
        weekday = preset.get("game_day_of_week")
        if weekday is None:
            return None
        occurrence = week_start + timedelta(days=int(weekday))
        return occurrence

    if recurrence_type == RecurrenceType.MONTHLY:
        day_of_month = preset.get("day_of_month")
        if day_of_month is None:
            return None
        return monthly_occurrence_in_week(week_start, int(day_of_month))

    recurrence_date = preset.get("recurrence_date")
    if recurrence_date is None:
        return None
    if isinstance(recurrence_date, str):
        recurrence_date = date.fromisoformat(recurrence_date)
    if week_start <= recurrence_date <= week_end(week_start):
        return recurrence_date
    return None


def is_preset_active_this_week(preset: dict, week_start: date) -> bool:
    return preset_occurrence_in_week(preset, week_start) is not None


def sort_key_for_week(preset: dict, week_start: date) -> tuple[date, str, int]:
    occurrence = preset_occurrence_in_week(preset, week_start)
    if occurrence is None:
        return (date.max, str(preset.get("game_time") or ""), int(preset.get("id") or 0))
    return (occurrence, str(preset.get("game_time") or ""), int(preset.get("id") or 0))
