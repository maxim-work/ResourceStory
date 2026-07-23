from aiogram.filters.callback_data import CallbackData


class AddResourceCallback(CallbackData, prefix="add"):
    option: str
