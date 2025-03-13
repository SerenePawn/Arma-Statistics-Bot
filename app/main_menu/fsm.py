from aiogram.fsm.state import StatesGroup, State


class SquadFSM(StatesGroup):
    name = State()
    tags = State()
