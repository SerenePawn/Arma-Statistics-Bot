from datetime import date, timedelta

from aiosqlite import Connection

from core.db import db
from core.db.db import record_to_model, record_to_model_list
from logic.attendances.models import Attendance, AttendanceForm, AttendanceDetail
from logic.schedules.models import SchedulePreset


async def update_or_create(conn: Connection, form: AttendanceForm) -> int:
    attendance = await get_attendance(conn, form.schedule_preset_id, form.player_id)
    if not attendance:
        result = await db.create(
            conn,
            table="attendances",
            data=form.model_dump(),
        )
        await conn.commit()
        return result["last_insert_rowid"]
    result = await db.update(
        conn,
        table="attendances",
        data=form.model_dump(),
        pk=attendance.id,
        with_updated_at=False
    )
    await conn.commit()
    return result["id"]


async def get(conn: Connection, pk: int) -> Attendance | None:
    result = await db.get(
        conn,
        "attendances",
        pk
    )
    if not result:
        return None
    model = record_to_model(Attendance, result)
    return model


async def get_attendance(conn: Connection, schedule_preset_id: int, player_id: int) -> Attendance | None:
    now = date.today()
    weekday = now.weekday()
    date_since = now - timedelta(days=weekday)

    result = await db.get_by_where(
        conn,
        "attendances",
        where="schedule_preset_id = ? AND player_id = ? AND created_at >= ?",
        values=[schedule_preset_id, player_id, date_since]
    )
    if not result:
        return None
    model, *_ = record_to_model_list(Attendance, result)
    return model


async def get_list_by_squad_id(conn: Connection, squad_id: int) -> list[AttendanceDetail]:
    now = date.today()
    weekday = now.weekday()
    date_since = now - timedelta(days=weekday)

    result_attendances = await db.get_by_where(
        conn,
        "attendances AS atd",
        "sp.squad_id = ? AND atd.created_at >= ?",
        [squad_id, date_since],
        fields=["atd.*", "p.name AS player_name"],
        left_outer_join=[
            "schedules_presets sp ON atd.schedule_preset_id = sp.id",
            "players p ON atd.player_id = p.id",
        ]
    )
    if not result_attendances:
        result_attendances = []

    result_schedules = await conn.execute_fetchall(
        """
            SELECT 
                p.name AS player_name, 
                s.schedule_preset_id,
                s.player_id,
                '' AS comment,
                s.created_at,
                CASE s.will_attend_default WHEN 1 THEN 'will_attend' ELSE 'will_not_attend' END AS attend_status
            FROM schedules AS s
                LEFT JOIN schedules_presets sp ON s.schedule_preset_id = sp.id
                LEFT JOIN players p ON s.player_id = p.id
        """
    )
    if not result_schedules:
        result_schedules = []

    if not result_attendances and not result_schedules:
        return []

    attendnaces_preset_id_player_id = [(i["schedule_preset_id"], i["player_id"]) for i in result_attendances]
    week_result = result_attendances + [
        i for i in result_schedules if (i["schedule_preset_id"], i["player_id"]) not in attendnaces_preset_id_player_id
    ]

    unique_schedules_preset_ids = {i["schedule_preset_id"] for i in week_result}
    sp_result = await db.get_by_where(
        conn,
        "schedules_presets AS sp",
        " OR ".join(["id = ?" for i in unique_schedules_preset_ids]),
        [*unique_schedules_preset_ids],
        fields=["sp.*"]
    )
    schedule_presets: dict[int, SchedulePreset] = {i.id: i for i in record_to_model_list(SchedulePreset, sp_result)}

    # Сортировка результатов по дням недели
    week_result.sort(key=lambda x: (
        schedule_presets[x["schedule_preset_id"]].game_day_of_week,
        schedule_presets[x["schedule_preset_id"]].game_time
    ))

    attendances = [
        AttendanceDetail(
            schedule_preset=schedule_presets[i["schedule_preset_id"]],
            **dict(i)
        )
        for i in week_result
    ]
    return attendances


async def update(conn: Connection, squad_id: int, **data) -> Attendance:
    result = await db.update(
        conn,
        pk=squad_id,
        table="attendances",
        data=data,
        with_updated_at=False
    )
    await conn.commit()
    return record_to_model(Attendance, result)
