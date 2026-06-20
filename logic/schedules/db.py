from datetime import date, time, timedelta

import asyncpg

from core.db import db
from core.db.db import record_to_model, record_to_model_list
from logic.schedules.models import SchedulePreset, SchedulePresetForm, ScheduleForm, Schedule
from logic.schedules.recurrence import RecurrenceType, monthly_occurrence_in_week, week_end

_PRESET_FIELDS = [
    "sp.id",
    "sp.squad_id",
    "sp.name",
    "sp.game_id",
    "g.title AS game_title",
    "sp.game_time",
    "sp.game_day_of_week",
    "sp.recurrence_type",
    "sp.recurrence_date",
    "sp.day_of_month",
    "sp.created_at",
]
_PRESET_JOIN = "LEFT JOIN games AS g ON g.id = sp.game_id"


def _parse_game_time(value: time | str) -> time:
    if isinstance(value, time):
        return value
    parts = [int(part) for part in str(value).split(":")]
    return time(parts[0], parts[1], parts[2] if len(parts) > 2 else 0)


def _prepare_preset_db_data(data: dict) -> dict:
    prepared = dict(data)
    if "game_time" in prepared:
        prepared["game_time"] = _parse_game_time(prepared["game_time"])
    recurrence_type = prepared.get("recurrence_type")
    if recurrence_type is not None and hasattr(recurrence_type, "value"):
        prepared["recurrence_type"] = recurrence_type.value
    return prepared


async def create_preset(
    conn: asyncpg.Connection,
    squad_id: int,
    form: SchedulePresetForm,
    *,
    chatters_id: int | None = None,
) -> int:
    data = _prepare_preset_db_data(form.model_dump(exclude_none=True) | {"squad_id": squad_id})
    if chatters_id is not None:
        data["chatters_id"] = chatters_id
    result = await db.create(
        conn,
        table="schedules_presets",
        data=data,
    )
    return result["id"]


async def create_schedule(conn: asyncpg.Connection, form: ScheduleForm) -> int:
    result = await db.create(
        conn,
        table="schedules",
        data=form.model_dump(),
    )
    return result["id"]


async def _preset_from_row(row: asyncpg.Record | dict | None) -> SchedulePreset | None:
    if not row:
        return None
    return record_to_model(SchedulePreset, row)


async def get_preset(conn: asyncpg.Connection, pk: int) -> SchedulePreset | None:
    row = await db.get_raw_one(
        conn,
        f"""
        SELECT {", ".join(_PRESET_FIELDS)}
        FROM schedules_presets AS sp
            {_PRESET_JOIN}
        WHERE sp.id = $1
        """,
        [pk],
    )
    return _preset_from_row(row)


async def get_schedule(conn: asyncpg.Connection, pk: int) -> Schedule | None:
    result = await db.get(
        conn,
        "schedules",
        pk
    )
    if not result:
        return None
    return record_to_model(Schedule, result)


async def get_schedule_by_player(conn: asyncpg.Connection, player_id: int, preset_id: int) -> Schedule | None:
    where = "player_id = $1 AND schedule_preset_id = $2"

    result = await db.get_by_where(
        conn,
        "schedules",
        where=where,
        values=[player_id, preset_id],
    )
    return record_to_model(Schedule, result)


def _preset_matches_rest_of_week(preset: SchedulePreset, today: date) -> bool:
    if preset.recurrence_type == RecurrenceType.WEEKLY:
        return preset.game_day_of_week >= today.weekday()
    if preset.recurrence_type == RecurrenceType.ONCE:
        if preset.recurrence_date is None:
            return False
        week_start = today - timedelta(days=today.weekday())
        return week_start <= preset.recurrence_date <= week_end(week_start)
    if preset.recurrence_type == RecurrenceType.MONTHLY:
        week_start = today - timedelta(days=today.weekday())
        if preset.day_of_month is None:
            return False
        return monthly_occurrence_in_week(week_start, preset.day_of_month) is not None
    return False


async def get_presets(
        conn: asyncpg.Connection,
        squad_id: int | None = None,
        all_week: bool = False,
) -> list[SchedulePreset]:
    values: list = []
    where_parts: list[str] = []

    if squad_id:
        where_parts.append(f"sp.squad_id = ${len(values) + 1}")
        values.append(squad_id)

    result = await db.get_raw(
        conn,
        f"""
        SELECT {", ".join(_PRESET_FIELDS)}
        FROM schedules_presets AS sp
            {_PRESET_JOIN}
        {f"WHERE {' AND '.join(where_parts)}" if where_parts else ""}
        ORDER BY sp.game_day_of_week, sp.game_time
        """,
        values,
    )
    if not result:
        return []
    presets = record_to_model_list(SchedulePreset, result)
    if all_week:
        return presets
    today = date.today()
    return [preset for preset in presets if _preset_matches_rest_of_week(preset, today)]


async def get_presets_by_chat(conn: asyncpg.Connection, chat_id: int, chat_thread_id: int) -> list[SchedulePreset]:
    result = await db.get_raw(
        conn,
        f"""
        SELECT {", ".join(_PRESET_FIELDS)}
        FROM schedules_presets AS sp
            {_PRESET_JOIN}
            LEFT OUTER JOIN squads AS s ON s.id = sp.squad_id
        WHERE s.telegram_chat_id = $1 AND s.telegram_chat_thread_id = $2
        ORDER BY sp.game_day_of_week, sp.game_time
        """,
        [chat_id, chat_thread_id],
    )
    if not result:
        return []
    return record_to_model_list(SchedulePreset, result)


async def update_schedule(conn: asyncpg.Connection, schedule_id: int, **data) -> Schedule:
    result = await db.update(
        conn,
        table="schedules",
        pk=schedule_id,
        data=data,
        with_updated_at=False
    )
    return record_to_model(Schedule, result)


async def update_preset(conn: asyncpg.Connection, preset_schedule_id: int, **data) -> SchedulePreset:
    await db.update(
        conn,
        pk=preset_schedule_id,
        table="schedules_presets",
        data=_prepare_preset_db_data(data),
        with_updated_at=False
    )
    preset = await get_preset(conn, preset_schedule_id)
    if preset:
        return preset
    raise ValueError("Schedule preset not found")


async def delete_preset(conn: asyncpg.Connection, schedule_preset_id: int, squad_id: int) -> SchedulePreset:
    preset = await get_preset(conn, schedule_preset_id)
    if not preset or preset.squad_id != squad_id:
        raise ValueError("Schedule preset not found")
    await conn.execute("DELETE FROM attendances WHERE schedule_preset_id = $1", schedule_preset_id)
    await conn.execute("DELETE FROM schedules WHERE schedule_preset_id = $1", schedule_preset_id)
    await db.delete_by_where(
        conn,
        pk=schedule_preset_id,
        table="schedules_presets",
        where=["squad_id = $1"],
        values=[squad_id]
    )
    return preset


async def delete_schedule(conn: asyncpg.Connection, schedule_id: int) -> Schedule:
    result = await db.delete(
        conn,
        table="schedules",
        pk=schedule_id,
    )
    return record_to_model(Schedule, result)
