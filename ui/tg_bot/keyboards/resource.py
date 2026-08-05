from typing import Callable

from aiogram.types.inline_keyboard_button import InlineKeyboardButton
from aiogram.types.inline_keyboard_markup import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import RESOURCES_PER_PAGE
from ui.tg_bot.callbacks.resource import (
    ResourceCallback,
    SearchCallback,
    SettingsCallback,
)


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


def _build_paginated_keyboard(
    items: list,
    page: int,
    total_pages: int,
    get_text: Callable,
    get_callback: Callable,
    compact_threshold: int = 2,
) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()

    nav = []
    if page > 1:
        nav.append(
            InlineKeyboardButton(
                text="◀ Назад",
                callback_data=get_callback("nav", page - 1),
            )
        )
    if page < total_pages:
        nav.append(
            InlineKeyboardButton(
                text="Вперёд ▶",
                callback_data=get_callback("nav", page + 1),
            )
        )

    compact = len(items) <= compact_threshold

    if compact and nav:
        for btn in nav:
            builder.button(text=btn.text, callback_data=btn.callback_data)

    for i, item in enumerate(items):
        builder.button(
            text=get_text(i, item),
            callback_data=get_callback(i, item),
        )

    if compact:
        builder.adjust(len(nav) + len(items))
    else:
        builder.adjust(3)
        if nav:
            builder.row(*nav)

    return builder.as_markup()


def create_list_keyboard(
    resources: list, page: int, total_pages: int
) -> InlineKeyboardMarkup:
    return _build_paginated_keyboard(
        items=resources,
        page=page,
        total_pages=total_pages,
        get_text=lambda i, r: str(i + 1),
        get_callback=lambda flag, val: (
            ResourceCallback(action="page", page=val).pack()
            if flag == "nav"
            else ResourceCallback(action="view", resource_id=val.id, page=page).pack()
        ),
    )


def create_search_keyboard(
    results: list, page: int, total_pages: int
) -> InlineKeyboardMarkup:
    return _build_paginated_keyboard(
        items=results,
        page=page,
        total_pages=total_pages,
        get_text=lambda i, item: str((page - 1) * RESOURCES_PER_PAGE + i + 1),
        get_callback=lambda flag, val: (
            SearchCallback(action="page", page=val).pack()
            if flag == "nav"
            else SearchCallback(
                action="view",
                resource_id=val[0].id if isinstance(val, tuple) else val.id,
                page=page,
            ).pack()
        ),
    )


def create_settings_menu():
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Экспорт ссылок",
        callback_data=SettingsCallback(action="export_urls").pack(),
    )
    builder.button(
        text="Экспорт данных",
        callback_data=SettingsCallback(action="export_data").pack(),
    )
    builder.button(
        text="Импорт ссылок",
        callback_data=SettingsCallback(action="import_urls_menu").pack(),
    )
    builder.button(
        text="Импорт данных",
        callback_data=SettingsCallback(action="import_data_menu").pack(),
    )
    builder.adjust(2)
    return builder.as_markup()


def create_import_urls_menu():
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Быстрый импорт",
        callback_data=SettingsCallback(action="import_urls_fast").pack(),
    )
    builder.button(
        text="Детальный импорт",
        callback_data=SettingsCallback(action="import_urls_detailed").pack(),
    )
    builder.button(
        text="Назад", callback_data=SettingsCallback(action="settings").pack()
    )
    builder.adjust(2, 1)
    return builder.as_markup()


def create_import_data_menu():
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Быстрый импорт",
        callback_data=SettingsCallback(action="import_data_fast").pack(),
    )
    builder.button(
        text="Детальный импорт",
        callback_data=SettingsCallback(action="import_data_detailed").pack(),
    )
    builder.button(
        text="Назад", callback_data=SettingsCallback(action="settings").pack()
    )
    builder.adjust(2, 1)
    return builder.as_markup()
