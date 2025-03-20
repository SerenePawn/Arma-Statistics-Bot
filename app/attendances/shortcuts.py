from aiogram.types import User

from app.attendances.misc import get_attendance_keyboard, get_attendance_text
from core.app_state import AppState
from logic.attendances import db as attendances_db
from logic.schedules import db as schedules_db
from logic.players import db as players_db
from logic.squads import db as squads_db

NOT_IN_SQUAD_MSG = (
    "Ваш аккаунт не привязан ни к одному отряду.\n\n"
    "Чтобы привязать аккаунт, напишите в любом чате группы отряда `/reg <ник>` , "
    "например, для ника `[TAG]Player` будет правильным: `/reg Player`."
)

NO_SCHEDULES = (
    "У отряда не найдено расписания. Возможно, это баг, или же ленивые администраторы еще не добавили расписание."
)


async def set_user_private_attendance(from_user: User):
    app_state = AppState()
    player = await players_db.get_by_tg_id(app_state.conn, from_user.id)
    if not player:
        await app_state.bot.send_message(
            player.telegram_id,
            "Вы не состоите ни в каком отряде. "
            "Для начала, напишите в любой чат группы отряда `/reg <свой никнейм без тегов>`",
        )
        return
    squad = await squads_db.get(app_state.conn, player.squad_id)
    attendances_to_remind = await schedules_db.get_presets(app_state.conn, squad.id, all_week=True)
    if not attendances_to_remind:
        return

    futures = []

    for schedule_preset in attendances_to_remind:
        # TODO сделать мапу посещений; оптимизация
        attendance = await attendances_db.get_attendance(app_state.conn, schedule_preset.id, player.id)
        schedule = await schedules_db.get_schedule_by_player(app_state.conn, player.id, schedule_preset.id)

        await app_state.bot.send_message(
            player.telegram_id,
            **get_attendance_text(schedule_preset, schedule, attendance).as_kwargs(),
            reply_markup=get_attendance_keyboard(schedule_preset.id, player.id)
        )

    for i in futures:
        i.result()
