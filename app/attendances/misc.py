import datetime

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.formatting import as_list, as_line, Text, Bold

from logic.attendances.misc import ATTENDANCE_EMOJI
from logic.attendances.models import Attendance
from logic.schedules.misc import DAYS_OF_WEEK
from logic.schedules.models import SchedulePreset, Schedule


def get_attendance_keyboard(schedule_preset_id: int, player_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🟢 Приду",
                callback_data=f"attendance_will_attend:{schedule_preset_id}:{player_id}"
            ),
            InlineKeyboardButton(
                text="🟡 Сомневаюсь",
                callback_data=f"attendance_doubt:{schedule_preset_id}:{player_id}"
            ),
            InlineKeyboardButton(
                text="🔴 Не приду",
                callback_data=f"attendance_will_not_attend:{schedule_preset_id}:{player_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔵 Пока неизвестно",
                callback_data=f"attendance_empty:{schedule_preset_id}:{player_id}"
            ),
        ],
        [
            InlineKeyboardButton(text="Отмена", callback_data="attendance_cancel")
        ],
    ])


def get_attendance_text(
        schedule_preset: SchedulePreset,
        schedule: Schedule | None = None,
        attendance: Attendance | None = None
) -> Text:
    now = datetime.datetime.now()
    dow = now.weekday()
    return as_list(
        as_line(
            ATTENDANCE_EMOJI[attendance.attend_status if attendance else None],
            f"(Расписание: {ATTENDANCE_EMOJI[schedule.will_attend_default if schedule else None]})",
            Bold(f"{schedule_preset.game_name}"),
            sep=" "
        ),
        f"Ваш комментарий: {attendance.comment}" if attendance and attendance.comment else "",
        f"{"Сегодня" if schedule_preset.game_day_of_week == dow else DAYS_OF_WEEK[schedule_preset.game_day_of_week]} "
        f"в {schedule_preset.game_time.strftime("%H:%M")} по МСК",
        sep="\n"
    )
