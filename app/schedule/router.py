from aiogram import types, F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.formatting import Bold, as_line

from core.app_state import AppState
from logic.players import db as players_db
from logic.schedules import db as schedules_db
from logic.schedules.misc import DAYS_OF_WEEK
from logic.schedules.models import ScheduleForm
from logic.squads import db as squads_db

router = Router()

NOT_IN_SQUAD_MSG = (
    "Ваш аккаунт не привязан ни к одному отряду.\n\n"
    "Чтобы привязать аккаунт, напишите в чате отряда `/reg <ник>` , "
    "например, для ника `[TAG]Player` будет правильным: `/reg Player`."
)

NO_SCHEDULES = (
    "У отряда не найдено расписания. Возможно, это баг, или же ленивые администраторы."
)


@router.message(F.chat.type.in_({"private"}), Command("schedule"))
async def set_private_schedule(message: types.Message):
    # TODO: Можно сделать передачу в команду аргументов, что позволит отсеивать игры (напр. %TVT%, где %<input>%).
    app_state = AppState()
    player = await players_db.get_by_tg_id(app_state.conn, message.from_user.id)
    if not player:
        await message.answer(NOT_IN_SQUAD_MSG)
        return

    squad = await squads_db.get(app_state.conn, player.squad_id)
    squad_schedules = await schedules_db.get_presets_by_chat(
        app_state.conn,
        squad.telegram_chat_id,
        squad.telegram_chat_thread_id
    )
    squad_schedules.sort(key=lambda x: (
        x.game_day_of_week,
        x.game_time,
    ))

    if not squad_schedules:
        await message.answer(NO_SCHEDULES)
        return

    for schedule in squad_schedules:
        await app_state.bot.send_message(
            **as_line(
                Bold(schedule.game_name),
                " — ",
                schedule.game_name,
                " в ",
                DAYS_OF_WEEK[schedule.game_day_of_week].lower(),
                " по МСК"
            ).as_kwargs(),
            chat_id=message.chat.id,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🟢 Буду приходить",
                        callback_data=f"update_user_schedule:{player.id}:{schedule.id}:1"
                    ),
                    InlineKeyboardButton(
                        text="🔴 Не буду приходить",
                        callback_data=f"update_user_schedule:{player.id}:{schedule.id}:0"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔵 Пока неизвестно",
                        callback_data=f"delete_user_schedule:{player.id}:{schedule.id}"
                    ),
                ],
                [
                    InlineKeyboardButton(text="Отмена", callback_data="cancel_user_schedule")
                ],
            ])
        )


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
