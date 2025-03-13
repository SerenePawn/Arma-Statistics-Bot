from aiogram import types, F, Router
from aiogram.filters import Command

from app.schedule.shortcuts import set_user_private_schedule
from core.app_state import AppState
from logic.schedules import db as schedules_db
from logic.schedules.models import ScheduleForm

router = Router()


@router.message(F.chat.type.in_({"private"}), Command("schedule"))
async def set_private_schedule(message: types.Message):
    # TODO: Можно сделать передачу в команду аргументов, что позволит отсеивать игры (напр. %TVT%, где %<input>%).
    await set_user_private_schedule(message.from_user)


@router.callback_query(F.data.startswith("update_user_schedule"))
async def callback_register_schedule(callback: types.CallbackQuery):
    cmd, player_id, schedule_preset_id, will_attend = callback.data.split(":")
    will_attend_bool = True if will_attend == "1" else False

    app_state = AppState()
    existing_schedule = await schedules_db.get_schedule_by_player(
        app_state.conn,
        player_id,
        schedule_preset_id,
    )
    if existing_schedule:
        await schedules_db.update_schedule(
            app_state.conn,
            existing_schedule.id,
            will_attend_default=will_attend_bool,
        )
    else:
        await schedules_db.create_schedule(
            app_state.conn,
            ScheduleForm(
                player_id=player_id,
                schedule_preset_id=schedule_preset_id,
                will_attend_default=will_attend_bool,
            )
        )

    await callback.message.delete()


@router.callback_query(F.data.startswith("delete_user_schedule"))
async def callback_delete_schedule(callback: types.CallbackQuery):
    cmd, player_id, schedule_preset_id = callback.data.split(":")

    app_state = AppState()
    existing_schedule = await schedules_db.get_schedule_by_player(
        app_state.conn,
        player_id,
        schedule_preset_id,
    )
    if not existing_schedule:
        await callback.message.delete()
        return

    await schedules_db.delete_schedule(
        app_state.conn,
        schedule_id=existing_schedule.id,
    )

    await callback.message.delete()


@router.callback_query(F.data == "cancel_user_schedule")
async def callback_cancel_schedule(callback: types.CallbackQuery):
    await callback.message.delete()
