from aiogram.fsm.state import StatesGroup, State


class BugFSM(StatesGroup):
    bug_written = State()
