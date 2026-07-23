from aiogram.fsm.state import State, StatesGroup


class AddResourceState(StatesGroup):
    waiting_for_link = State()
    waiting_for_type = State()
    waiting_for_format = State()
    waiting_for_new_tags = State()
    waiting_for_save = State()
