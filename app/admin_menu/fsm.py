from aiogram.fsm.state import StatesGroup, State


class AdminFSM(StatesGroup):
    # add_to_squad = State()
    # remove_from_squad = State()
    name_tag = State()
    squad_name = State()

    # schedule
    schedule_dow = State()  # dow = day of week
    schedule_time = State()
