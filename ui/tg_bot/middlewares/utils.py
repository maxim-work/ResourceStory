from aiogram.types import Update


def get_real_event(event: Update):
    return event.message or event.callback_query
