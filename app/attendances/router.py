from contextlib import suppress

from aiogram import types, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.attendances.fsm import AttendanceFSM
from app.attendances.misc import get_attendance_text, get_attendance_keyboard
from app.attendances.shortcuts import set_user_private_attendance
from core.app_state import AppState
from logic.attendances import db as attendances_db
from logic.attendances.enums import AttendStatus
from logic.attendances.models import AttendanceForm
from logic.schedules import db as schedules_db

router = Router()


@router.message(F.chat.type.in_({"private"}), Command("attendance"))
async def set_private_schedule(message: types.Message):
    # TODO: Можно сделать передачу в команду аргументов, что позволит отсеивать игры (напр. %TVT%, где %<input>%).
    await set_user_private_attendance(message.from_user)


@router.callback_query(F.data.startswith("attendance_will_attend"))
async def attendance_will_attend(callback: CallbackQuery):
    app_state = AppState()
    cmd, schedule_preset_id, player_id = callback.data.split(":")

    schedule_preset = await schedules_db.get_preset(app_state.conn, schedule_preset_id)
    attendance = await attendances_db.get_attendance(app_state.conn, schedule_preset_id, player_id)
    if schedule_preset:
        await attendances_db.update_or_create(
            app_state.conn,
            AttendanceForm(
                schedule_preset_id=schedule_preset_id,
                player_id=player_id,
                attend_status=AttendStatus.WILL_ATTEND,
            )
        )
    elif attendance:
        await attendances_db.delete(app_state.conn, attendance.id)
        await callback.message.delete()

    attendance = await attendances_db.get_attendance(app_state.conn, schedule_preset_id, player_id)
    schedule = await schedules_db.get_schedule_by_player(app_state.conn, player_id, schedule_preset_id)

    await callback.message.edit_text(
        **get_attendance_text(schedule_preset, schedule, attendance).as_kwargs(),
        reply_markup=get_attendance_keyboard(schedule_preset.id, player_id)
    )


@router.callback_query(F.data.startswith("attendance_doubt"))
async def attendance_doubt(callback: CallbackQuery, state: FSMContext):
    app_state = AppState()
    cmd, schedule_preset_id, player_id = callback.data.split(":")

    await state.set_state(AttendanceFSM.write_reason)
    write_reason_message = await app_state.bot.send_message(
        callback.from_user.id,
        "Напишите причину, по которой потенциально не сможете придти.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Отмена", callback_data="attendance_reason_cancel"),
                InlineKeyboardButton(text="Пропустить", callback_data="attendance_reason_skip"),
            ]
        ])
    )
    await state.update_data(
        schedule_preset_id=schedule_preset_id,
        player_id=player_id,
        attendance_message=callback.message,
        write_reason_message=write_reason_message,
        attend_status=AttendStatus.DOUBTS
    )


@router.callback_query(F.data.startswith("attendance_will_not_attend"))
async def attendance_will_not_attend(callback: CallbackQuery, state: FSMContext):
    app_state = AppState()
    cmd, schedule_preset_id, player_id = callback.data.split(":")

    await state.set_state(AttendanceFSM.write_reason)
    write_reason_message = await app_state.bot.send_message(
        callback.from_user.id,
        "Напишите причину, по которой точно не сможете придти.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Отмена", callback_data="attendance_reason_cancel"),
                InlineKeyboardButton(text="Пропустить", callback_data="attendance_reason_skip"),
            ]
        ])
    )
    await state.update_data(
        schedule_preset_id=schedule_preset_id,
        player_id=player_id,
        attendance_message=callback.message,
        write_reason_message=write_reason_message,
        attend_status=AttendStatus.WILL_NOT_ATTEND
    )


@router.message(AttendanceFSM.write_reason)
async def fsm_attendance_reason(message: types.Message, state: FSMContext):
    app_state = AppState()
    data = await state.get_data()
    schedule_preset_id = data["schedule_preset_id"]
    player_id = data["player_id"]
    await data["write_reason_message"].delete()
    with suppress(TelegramBadRequest):
        await message.delete()

    schedule_preset = await schedules_db.get_preset(app_state.conn, schedule_preset_id)
    attendance = await attendances_db.get_attendance(app_state.conn, schedule_preset_id, player_id)
    if schedule_preset:
        await attendances_db.update_or_create(
            app_state.conn,
            AttendanceForm(
                schedule_preset_id=schedule_preset_id,
                player_id=player_id,
                attend_status=data["attend_status"],
                comment=message.text
            )
        )
    elif attendance:
        await attendances_db.delete(app_state.conn, attendance.id)
        await data["attendance_message"].delete()
        return

    attendance = await attendances_db.get_attendance(app_state.conn, schedule_preset_id, player_id)
    schedule = await schedules_db.get_schedule_by_player(app_state.conn, player_id, schedule_preset_id)

    await data["attendance_message"].edit_text(
        **get_attendance_text(schedule_preset, schedule, attendance).as_kwargs(),
        reply_markup=get_attendance_keyboard(schedule_preset.id, player_id)
    )
    await state.clear()


@router.callback_query(F.data == "attendance_reason_skip")
async def attendance_reason_skip(callback: CallbackQuery, state: FSMContext):
    app_state = AppState()
    data = await state.get_data()
    schedule_preset_id = data["schedule_preset_id"]
    player_id = data["player_id"]
    await callback.message.delete()

    schedule_preset = await schedules_db.get_preset(app_state.conn, schedule_preset_id)
    attendance = await attendances_db.get_attendance(app_state.conn, schedule_preset_id, player_id)
    if schedule_preset:
        await attendances_db.update_or_create(
            app_state.conn,
            AttendanceForm(
                schedule_preset_id=schedule_preset_id,
                player_id=player_id,
                attend_status=data["attend_status"]
            )
        )
    elif attendance:
        await attendances_db.delete(app_state.conn, attendance.id)
        await callback.message.delete()
        await data["attendance_message"].delete()
        return

    attendance = await attendances_db.get_attendance(app_state.conn, schedule_preset_id, player_id)
    schedule = await schedules_db.get_schedule_by_player(app_state.conn, player_id, schedule_preset_id)

    await data["attendance_message"].edit_text(
        **get_attendance_text(schedule_preset, schedule, attendance).as_kwargs(),
        reply_markup=get_attendance_keyboard(schedule_preset.id, player_id)
    )
    await state.clear()


@router.callback_query(F.data.startswith("attendance_empty"))
async def attendance_empty(callback: CallbackQuery):
    app_state = AppState()
    cmd, schedule_preset_id, player_id = callback.data.split(":")

    schedule_preset = await schedules_db.get_preset(app_state.conn, schedule_preset_id)
    attendance = await attendances_db.get_attendance(app_state.conn, schedule_preset_id, player_id)
    if attendance:
        await attendances_db.delete(app_state.conn, attendance.id)
    else:
        return

    attendance = None
    schedule = await schedules_db.get_schedule_by_player(app_state.conn, player_id, schedule_preset_id)

    await callback.message.edit_text(
        **get_attendance_text(schedule_preset, schedule, attendance).as_kwargs(),
        reply_markup=get_attendance_keyboard(schedule_preset.id, player_id)
    )


@router.callback_query(F.data == "attendance_reason_cancel")
async def attendance_reason_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await state.clear()


@router.callback_query(F.data.startswith("attendance_cancel"))
async def attendance_empty(callback: CallbackQuery):
    await callback.message.delete()
