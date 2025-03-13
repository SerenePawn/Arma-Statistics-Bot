from datetime import date

from aiosqlite import Connection

from core.db import db
from core.db.db import record_to_model, record_to_model_list
from logic.schedules.models import SchedulePreset, SchedulePresetForm, ScheduleForm, Schedule


async def create_preset(conn: Connection, squad_id: int, form: SchedulePresetForm) -> int:
    result = await db.create(
        conn,
        table="schedules_presets",
        data=form.model_dump() | {"squad_id": squad_id},
    )
    return result["last_insert_rowid"]


async def create_schedule(conn: Connection, form: ScheduleForm) -> int:
    result = await db.create(
        conn,
        table="schedules",
        data=form.model_dump(),
    )
    return result["last_insert_rowid"]


async def get_preset(conn: Connection, pk: int) -> SchedulePreset | None:
    result = await db.get(
        conn,
        "schedules_presets",
        pk
    )
    if not result:
        return None
    return record_to_model(SchedulePreset, result)


async def get_schedule(conn: Connection, pk: int) -> Schedule | None:
    result = await db.get(
        conn,
        "schedules",
        pk
    )
    if not result:
        return None
    return record_to_model(Schedule, result)


async def get_schedule_by_player(conn: Connection, player_id: int, preset_id: int) -> Schedule | None:
    where = "player_id = ? AND schedule_preset_id = ?"

    result = await db.get_by_where(
        conn,
        "schedules",
        where=where,
        values=[player_id, preset_id],
    )
    if not result:
        return None
    model, *_ = record_to_model_list(Schedule, result)
    return model


async def get_presets_today(conn: Connection) -> list[SchedulePreset]:
    result = await db.get_by_where(
        conn,
        "schedules_presets AS sp",
        "sp.game_day_of_week = ?",
        [date.today().weekday()],
        fields=["sp.*"]

    )
    if not result:
        return []
    return record_to_model_list(SchedulePreset, result)


async def get_presets_by_chat(conn: Connection, chat_id: int, chat_thread_id: int) -> list[SchedulePreset]:
    result = await db.get_by_where(
        conn,
        "schedules_presets AS sp",
        "s.telegram_chat_id = ? AND s.telegram_chat_thread_id = ?",
        [chat_id, chat_thread_id],
        left_outer_join=["squads AS s ON s.id = sp.squad_id"],
        fields=["sp.*"]

    )
    if not result:
        return []
    return record_to_model_list(SchedulePreset, result)


async def update_schedule(conn: Connection, schedule_id: int, **data) -> Schedule:
    result = await db.update(
        conn,
        table="schedules",
        pk=schedule_id,
        data=data,
        with_updated_at=False
    )
    return record_to_model(Schedule, result)


async def update_preset(conn: Connection, preset_schedule_id: int, **data) -> SchedulePreset:
    result = await db.update(
        conn,
        pk=preset_schedule_id,
        table="schedules_presets",
        data=data,
        with_updated_at=False
    )
    return record_to_model(SchedulePreset, result)


async def delete_preset(conn: Connection, schedule_preset_id: int, squad_id: int) -> SchedulePreset:
    result = await db.delete_by_where(
        conn,
        pk=schedule_preset_id,
        table="schedules_presets",
        where=["squad_id = ?"],
        values=[squad_id]
    )
    return record_to_model(SchedulePreset, result)


async def delete_schedule(conn: Connection, schedule_id: int) -> Schedule:
    result = await db.delete(
        conn,
        table="schedules",
        pk=schedule_id,
    )
    return record_to_model(Schedule, result)
