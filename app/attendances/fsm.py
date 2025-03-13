from aiogram.fsm.state import StatesGroup, State


class AttendanceFSM(StatesGroup):
    write_reason = State()
