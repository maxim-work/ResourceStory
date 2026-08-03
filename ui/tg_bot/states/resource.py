from aiogram.fsm.state import State, StatesGroup


class ResourceState(StatesGroup):
    waiting_for_link = State()
    waiting_for_type = State()
    waiting_for_format = State()
    waiting_for_new_tags = State()
    waiting_for_save = State()
    waiting_for_notes = State()
    waiting_for_rating = State()
    waiting_for_date = State()
    waiting_for_search = State()
