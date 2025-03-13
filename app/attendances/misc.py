from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.formatting import as_list, as_line, Text, Bold

from logic.attendances.misc import ATTENDANCE_EMOJI
from logic.attendances.models import Attendance
from logic.schedules.models import SchedulePreset


def get_attendance_keyboard(schedule_preset_id: int, player_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="+",
                callback_data=f"attendance_will_attend:{schedule_preset_id}:{player_id}"
            ),
            InlineKeyboardButton(
                text="Сомневаюсь",
                callback_data=f"attendance_doubt:{schedule_preset_id}:{player_id}"
            ),
            InlineKeyboardButton(
                text="-",
                callback_data=f"attendance_will_not_attend:{schedule_preset_id}:{player_id}"
            )
        ],
    ])


def get_attendance_text(schedule_preset: SchedulePreset, attendance: Attendance | None = None) -> Text:
    return as_list(
        as_line(
            ATTENDANCE_EMOJI[attendance.attend_status if attendance else None],
            Bold(f"{schedule_preset.game_name}"),
            sep=" "
        ),
        f"Ваш комментарий: {attendance.comment}" if attendance and attendance.comment else "",
        f"Сегодня в {schedule_preset.game_time.strftime("%H:%M")} по МСК",
        sep="\n"
    )
