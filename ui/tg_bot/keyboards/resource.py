from typing import Callable

from aiogram.types.inline_keyboard_button import InlineKeyboardButton
from aiogram.types.inline_keyboard_markup import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.models.resource import Resource
from ui.tg_bot.callbacks.resource import ResourceCallback


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


def create_list_keyboard(
    resources: list[Resource], page: int, total_pages: int
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    nav = []
    if page > 1:
        nav.append(
            InlineKeyboardButton(
                text="◀ Назад",
                callback_data=ResourceCallback(action="page", page=page - 1).pack(),
            )
        )
    if page < total_pages:
        nav.append(
            InlineKeyboardButton(
                text="Вперёд ▶",
                callback_data=ResourceCallback(action="page", page=page + 1).pack(),
            )
        )

    compact = len(resources) <= 2

    if compact and nav:
        for btn in nav:
            builder.button(text=btn.text, callback_data=btn.callback_data)

    for r in resources:
        builder.button(
            text=str(r.id),
            callback_data=ResourceCallback(
                action="view", resource_id=r.id, page=page
            ).pack(),
        )

    if compact:
        builder.adjust(len(nav) + len(resources))
    else:
        builder.adjust(3)
        if nav:
            builder.row(*nav)

    return builder.as_markup()
