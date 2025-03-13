import re
from contextlib import suppress
from datetime import datetime

import pytz
from aiogram import types, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.formatting import Bold, Text

from app.admin_menu.fsm import AdminFSM
from app.admin_menu.schedule.misc import get_keyboard
from app.shortcuts import admin_only
from core.app_state import AppState
from logic.schedules import db as schedules_db
from logic.schedules.misc import DAYS_OF_WEEK
from logic.schedules.models import SchedulePresetForm
from logic.squads import db as squads_db

router = Router()


@router.callback_query(F.data == 'admin_menu_settings_schedule')
async def admin_menu_settings_schedule(callback: CallbackQuery, state: FSMContext):
    await admin_only(callback.message, callback.from_user.id)
    app_state = AppState()
    await state.clear()
    await state.set_state(None)

    operational_markup = [
        InlineKeyboardButton(text="Назад", callback_data="admin_common_cancel"),
        InlineKeyboardButton(text="Добавить", callback_data="admin_menu_settings_schedule_preset_add")
    ]

    squad = await squads_db.get_by_chat(app_state.conn, callback.message.chat.id, callback.message.message_thread_id)

    schedule_preset_msg = await callback.message.edit_text(
        text=f"[{callback.from_user.username}] Чтобы убрать расписание игр(ы), нажмите кнопку с названием игр(ы)",
        reply_markup=await get_keyboard(callback.message, operational_markup)
    )
    await state.update_data(
        init_tg_username=callback.from_user.username,
        squad=squad,
        schedule_preset_msg=schedule_preset_msg,
        operational_markup=operational_markup
    )


@router.callback_query(F.data == "admin_menu_settings_schedule_preset_add")
async def admin_menu_settings_schedule_preset_add(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data["init_tg_username"] != callback.from_user.username:
        return

    await admin_only(callback.message, callback.from_user.id)
    await state.set_state(AdminFSM.schedule_dow)

    await callback.message.edit_text(
        "Введите название игр(ы) (Например, `TVT 1`, `TVT 1 вторая игра` или `A3 TVT2`)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="admin_menu_settings_schedule")],
    ]))


@router.callback_query(F.data.startswith("admin_menu_settings_schedule_preset_delete_"))
async def admin_menu_settings_schedule_preset_delete(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data["init_tg_username"] != callback.from_user.username:
        return

    await admin_only(callback.message, callback.from_user.id)
    delete_preset_id = callback.data.replace("admin_menu_settings_schedule_preset_delete_", "")
    await schedules_db.delete_preset(AppState().conn, int(delete_preset_id), data["squad"].id)
    await admin_menu_settings_schedule(callback, state)


@router.message(AdminFSM.schedule_dow)
async def fsm_schedule_preset_dow(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if data["init_tg_username"] != message.from_user.username:
        return

    await admin_only(message)
    await state.update_data(game_name=message.text)
    # Чистки последнего сбщ
    with suppress(TelegramBadRequest):
        await message.delete()

    schedule_preset_msg = data["schedule_preset_msg"]
    await schedule_preset_msg.edit_text(
        "Выберите, в какой день недели проводится игра(-ы)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            *[
                [
                    InlineKeyboardButton(
                        text=f"{i}",
                        callback_data=f"admin_menu_settings_schedule_preset_select_dow_{num}"
                    )
                ]
                for num, i in enumerate(DAYS_OF_WEEK)
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="admin_menu_settings_schedule")],
    ]))


@router.callback_query(F.data.startswith("admin_menu_settings_schedule_preset_select_dow_"))
async def admin_menu_settings_schedule_preset_select_dow(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data["init_tg_username"] != callback.from_user.username:
        return

    await admin_only(callback.message, callback.from_user.id)
    await state.set_state(AdminFSM.schedule_time)
    dow_selected = callback.data.replace("admin_menu_settings_schedule_preset_select_dow_", "")
    await state.update_data(game_day_of_week=dow_selected)

    await callback.message.edit_text(
        "Введите время игр(ы) по МСК (Например, `10:15`, `16 00`, `1200`, `20` или `20:00`)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="admin_menu_settings_schedule")],
    ]))


@router.message(AdminFSM.schedule_time)
async def fsm_schedule_preset_time(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if data["init_tg_username"] != message.from_user.username:
        return

    await admin_only(message)
    regex = re.compile(r"(?P<hour>\d{1,2})\D?(?P<minute>\d{1,2})?")
    schedule_preset_msg = data["schedule_preset_msg"]
    operational_markup = data["operational_markup"]

    try:
        current_dt = datetime.now(tz=pytz.timezone("Europe/Moscow"))
        current_dt = current_dt.replace(**{k: int(v) for k, v in regex.fullmatch(message.text).groupdict(0).items()})
        game_time = current_dt.time()
    except AttributeError:
        with suppress(TelegramBadRequest):
            await message.delete()
        await schedule_preset_msg.edit_text(
            Text(
                "Введите время игр(ы) по МСК (Например, `10:15`, `16 00`, `1200`, `20` или `20:00`)\n\n",
                Bold(f"Некорректно введено время `{message.text}`")
            ).as_html(),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Отмена", callback_data="admin_menu_settings_schedule")],
        ]))
        return

    # Чистки последнего сбщ
    with suppress(TelegramBadRequest):
        await message.delete()

    await schedules_db.create_preset(
        AppState().conn,
        data["squad"].id,
        SchedulePresetForm(
            game_name=data["game_name"],
            game_time=game_time,
            game_day_of_week=int(data["game_day_of_week"]),
        )
    )

    await state.set_state(None)
    await schedule_preset_msg.edit_text(
        "Чтобы убрать расписание игр(ы), нажмите кнопку с названием игр(ы)",
        reply_markup=await get_keyboard(message, operational_markup)
    )
