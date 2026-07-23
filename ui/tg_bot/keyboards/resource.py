from typing import Callable

from aiogram.types.inline_keyboard_button import InlineKeyboardButton
from aiogram.types.inline_keyboard_markup import InlineKeyboardMarkup


def _build_keyboard(
    items: list[tuple[str, str]], len_row: int = 2
) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for text, callback_data in items:
        row.append(InlineKeyboardButton(text=text, callback_data=callback_data))
        if len(row) == len_row:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_kb_type(
    options: list, get_cb: Callable[[str], str], len_row: int = 2
) -> InlineKeyboardMarkup:
    return _build_keyboard([(opt.label, get_cb(opt.code)) for opt in options], len_row)


def create_kb_tags(
    labels: list[str], data: list[str], len_row: int = 2
) -> InlineKeyboardMarkup:
    return _build_keyboard(list(zip(labels, data)), len_row)
