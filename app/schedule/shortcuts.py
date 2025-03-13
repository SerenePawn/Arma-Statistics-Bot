from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import User
from aiogram.utils.formatting import Bold, as_line

from core.app_state import AppState
from logic.players import db as players_db
from logic.schedules import db as schedules_db
from logic.schedules.misc import DAYS_OF_WEEK
from logic.squads import db as squads_db
from logic.squads.models import Squad

NOT_IN_SQUAD_MSG = (
    "Ваш аккаунт не привязан ни к одному отряду.\n\n"
    "Чтобы привязать аккаунт, напишите в чате отряда `/reg <ник>` , "
    "например, для ника `[TAG]Player` будет правильным: `/reg Player`."
)

NO_SCHEDULES = (
    "У отряда не найдено расписания. Возможно, это баг, или же ленивые администраторы еще не добавили расписание."
)


async def set_user_private_schedule(from_user: User, squad: Squad | None = None):
    # TODO: Можно сделать передачу в команду аргументов, что позволит отсеивать игры (напр. %TVT%, где %<input>%).
    app_state = AppState()
    player = await players_db.get_by_tg_id(app_state.conn, from_user.id)
    if not player:
        await app_state.bot.send_message(chat_id=from_user.id, text=NOT_IN_SQUAD_MSG)
        return

    squad = squad or await squads_db.get(app_state.conn, player.squad_id)
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
        await app_state.bot.send_message(chat_id=from_user.id, text=NO_SCHEDULES)
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
            chat_id=from_user.id,
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