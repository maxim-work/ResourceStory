import logging

from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.markdown import hbold

from core.models.resource import ResourceKind, ResourceStatus, ResourceType
from data.exceptions import DuplicateResourceError
from data.service_db import ResourceDB
from ui.tg_bot.callbacks.resource import (
    ResourceCallback,
    get_callback_data,
    pack_callback_data_list,
)
from ui.tg_bot.handlers.resource.import_data import _start_next_resource_from_callback
from ui.tg_bot.handlers.resource.import_urls import _start_next_url_from_callback
from ui.tg_bot.keyboards.resource import create_kb_tags, create_kb_type
from ui.tg_bot.states.resource import ResourceState
from ui.tg_bot.utils.message import get_editable_message, with_action_label


async def handle_form_actions(
    callback: types.CallbackQuery,
    callback_data: ResourceCallback,
    state: FSMContext,
    resource_db: ResourceDB,
    message: types.Message,
    logger: logging.Logger,
):
    action = callback_data.action

    if action == "save":
        await _handle_save(callback, state, resource_db, message, logger)

    elif action == "cancel":
        await _handle_cancel(callback, state, resource_db, message, logger)

    elif action == "apply_new_tags":
        await _handle_apply_new_tags(callback, state)

    elif action == "keep_old_tags":
        await _handle_keep_old_tags(callback, state)

    elif action == "back":
        await _show_save_summary(callback, state)

    elif action in (
        "change_type",
        "change_format",
        "change_status",
        "change_tags",
        "change_notes",
        "change_rating",
        "change_date",
    ):
        await _handle_change_field(callback, callback_data, state, message)

    elif action == "edit":
        await _show_edit_menu(callback, state, message)


async def _handle_save(callback, state, resource_db, message, logger):
    data = await state.get_data()
    resource = data["resource"]
    is_edit = data.get("edit_mode", False)

    try:
        if is_edit:
            resource_db.update(resource)
            msg = (
                f"{hbold('Ресурс обновлён')}\n\n"
                f"{hbold('Название:')} {resource.title}\n"
                f"{hbold('Тип:')} {resource.resource_type.label}\n"
                f"{hbold('Формат:')} {resource.kind.label}\n"
                f"{hbold('Статус:')} {resource.status.label}\n"
                f"{hbold('Платформа:')} {resource.platform.label}\n"
                f"{hbold('Тэги:')} {', '.join(resource.tags) if resource.tags else 'не указаны'}\n"
                f"{hbold('Заметки:')} {resource.my_notes or 'нет'}\n"
                f"{hbold('Рейтинг:')} {resource.my_rating or '—'}/5\n"
                f"{hbold('Дата завершения:')} {resource.completed_at or 'нет'}"
            )
        else:
            resource_id = resource_db.insert(resource)
            msg = (
                f"{hbold('Ресурс сохранён')}\n\n"
                f"{hbold('Название:')} {resource.title}\n"
                f"{hbold('Тип:')} {resource.resource_type.label}\n"
                f"{hbold('Формат:')} {resource.kind.label}\n"
                f"{hbold('Платформа:')} {resource.platform.label}\n"
                f"{hbold('Тэги:')} {', '.join(resource.tags) if resource.tags else 'не указаны'}\n"
                f"{hbold('Длительность:')} {resource.duration_display}\n"
                f"{hbold('Рейтинг:')} {resource.my_rating or '—'}/5\n"
                f"{hbold('ID:')} {resource_id}"
            )
    except DuplicateResourceError:
        msg = "Ресурс с такой ссылкой уже существует"

    if "import_urls" in data:
        results = data["import_results"]
        results["count"] += 1
        index = data["import_index"] + 1
        await state.update_data(import_index=index, import_results=results)

        if index >= len(data["import_urls"]):
            msg = f"Импортировано {results['count']} из {len(data['import_urls'])} ссылок."
            if results["errors"]:
                msg += "\n\nОшибки:\n" + "\n".join(results["errors"][-10:])
            await state.clear()
            await message.edit_text(msg, disable_web_page_preview=True)
            return

        await _start_next_url_from_callback(callback, state, resource_db, logger, index)
        return

    elif "import_resources" in data:
        results = data["import_results"]
        results["count"] += 1
        index = data["import_index"] + 1
        await state.update_data(import_index=index, import_results=results)

        if index >= len(data["import_resources"]):
            msg = f"Импортировано {results['count']} из {len(data['import_resources'])} ресурсов."
            if results["errors"]:
                msg += "\n\nОшибки:\n" + "\n".join(results["errors"][-10:])
            await state.clear()
            await message.edit_text(msg, disable_web_page_preview=True)
            return

        await _start_next_resource_from_callback(
            callback, state, resource_db, logger, index
        )
        return

    await state.clear()
    await message.edit_text(msg)


async def _handle_cancel(callback, state, resource_db, message, logger):
    data = await state.get_data()

    if "import_urls" in data:
        results = data["import_results"]
        results["errors"].append(
            f"Пропущено: {data['import_urls'][data['import_index']]}"
        )
        index = data["import_index"] + 1
        await state.update_data(import_index=index, import_results=results)

        if index >= len(data["import_urls"]):
            msg = f"Импортировано {results['count']} из {len(data['import_urls'])} ссылок."
            if results["errors"]:
                msg += "\n\nОшибки:\n" + "\n".join(results["errors"][-10:])
            await state.clear()
            await message.edit_text(msg, disable_web_page_preview=True)
            return

        await _start_next_url_from_callback(callback, state, resource_db, logger, index)
        return

    elif "import_resources" in data:
        results = data["import_results"]
        results["errors"].append(
            f"Пропущено: {data['import_resources'][data['import_index']].title}"
        )
        index = data["import_index"] + 1
        await state.update_data(import_index=index, import_results=results)

        if index >= len(data["import_resources"]):
            msg = f"Импортировано {results['count']} из {len(data['import_resources'])} ресурсов."
            if results["errors"]:
                msg += "\n\nОшибки:\n" + "\n".join(results["errors"][-10:])
            await state.clear()
            await message.edit_text(msg, disable_web_page_preview=True)
            return

        await _start_next_resource_from_callback(
            callback, state, resource_db, logger, index
        )
        return

    is_edit = data.get("edit_mode", False)

    if is_edit:
        msg = f"{hbold('Редактирование отменено')}\n\nИзменения не сохранены."
    else:
        msg = (
            f"{hbold('Добавление отменено')}\n\n"
            "Ресурс не сохранён. Чтобы начать заново, используйте /add"
        )
    await state.clear()
    await message.edit_text(msg)


async def _handle_apply_new_tags(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    resource = data["resource"]
    new_tags = data.get("new_tags")
    resource.tags = new_tags if new_tags else None
    await state.update_data(resource=resource, new_tags=None, old_tags=None)
    await _show_save_summary(callback, state)


async def _handle_keep_old_tags(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(new_tags=None, old_tags=None)
    await _show_save_summary(callback, state)


async def _handle_change_field(
    callback: types.CallbackQuery,
    callback_data: ResourceCallback,
    state: FSMContext,
    message: types.Message,
):
    data = await state.get_data()
    await state.update_data(edit_target=callback_data.action)

    action = callback_data.action

    if action == "change_type":
        await state.set_state(ResourceState.waiting_for_type)
        await message.edit_text(
            with_action_label("edit", "Выберите новый тип:", data.get("title", "")),
            reply_markup=create_kb_type(list(ResourceType), get_callback_data),
        )

    elif action == "change_format":
        await state.set_state(ResourceState.waiting_for_format)
        await message.edit_text(
            with_action_label("edit", "Выберите новый формат:", data.get("title", "")),
            reply_markup=create_kb_type(list(ResourceKind), get_callback_data),
        )

    elif action == "change_status":
        await state.set_state(ResourceState.waiting_for_save)
        await message.edit_text(
            with_action_label("edit", "Выберите новый статус:", data.get("title", "")),
            reply_markup=create_kb_type(list(ResourceStatus), get_callback_data),
        )

    elif action == "change_tags":
        await state.set_state(ResourceState.waiting_for_new_tags)
        result = await message.edit_text(
            with_action_label("edit", "Напишите новые тэги:", data.get("title", ""))
        )
        if isinstance(result, Message):
            await state.update_data(prompt_msg_id=result.message_id)

    elif action == "change_notes":
        await state.set_state(ResourceState.waiting_for_notes)
        current = data["resource"].my_notes or "нет"
        result = await message.edit_text(
            with_action_label(
                "edit",
                f"Текущая заметка: {current}\n\nНапишите новую (или '-' для удаления):",
                data.get("title", ""),
            )
        )
        if isinstance(result, Message):
            await state.update_data(prompt_msg_id=result.message_id)

    elif action == "change_rating":
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        current = data["resource"].my_rating
        builder = InlineKeyboardBuilder()
        for i in range(1, 6):
            text = f"★{i}" if current and i <= current else str(i)
            builder.button(
                text=text,
                callback_data=ResourceCallback(action=f"set_rating_{i}").pack(),
            )
        builder.button(
            text="Убрать оценку",
            callback_data=ResourceCallback(action="set_rating_0").pack(),
        )
        builder.button(
            text="Назад",
            callback_data=ResourceCallback(action="edit").pack(),
        )
        builder.adjust(5, 2)

        await message.edit_text(
            with_action_label(
                "edit",
                f"Текущий рейтинг: {current or '—'}/5\n\nВыберите новый:",
                data.get("title", ""),
            ),
            reply_markup=builder.as_markup(),
        )

    elif action == "change_date":
        await state.set_state(ResourceState.waiting_for_date)
        current = data["resource"].completed_at or "не указана"
        result = await message.edit_text(
            with_action_label(
                "edit",
                f"Текущая дата: {current}\n\nВведите дату (ГГГГ-ММ-ДД или '-' для сброса):",
                data.get("title", ""),
            )
        )
        if isinstance(result, Message):
            await state.update_data(prompt_msg_id=result.message_id)


async def _show_edit_menu(
    callback: types.CallbackQuery,
    state: FSMContext,
    message: types.Message,
):
    data = await state.get_data()
    resource = data["resource"]
    is_edit = data.get("edit_mode", False)

    if is_edit:
        msg = (
            f"{hbold('Выберите, что хотите изменить')}\n\n"
            f"{hbold('Тип:')} {resource.resource_type.label}\n"
            f"{hbold('Формат:')} {resource.kind.label}\n"
            f"{hbold('Статус:')} {resource.status.label}\n"
            f"{hbold('Тэги:')} {', '.join(resource.tags) if resource.tags else 'не указаны'}\n"
            f"{hbold('Заметки:')} {resource.my_notes or 'нет'}\n"
            f"{hbold('Рейтинг:')} {resource.my_rating or '—'}/5\n"
            f"{hbold('Дата завершения:')} {resource.completed_at or 'не указана'}"
        )
        buttons = [
            "Тип",
            "Формат",
            "Статус",
            "Тэги",
            "Заметки",
            "Рейтинг",
            "Дата",
            "Назад",
        ]
        actions = [
            "change_type",
            "change_format",
            "change_status",
            "change_tags",
            "change_notes",
            "change_rating",
            "change_date",
            "back",
        ]
    else:
        msg = (
            f"{hbold('Выберите, что хотите изменить')}\n\n"
            f"{hbold('Тип:')} {resource.resource_type.label}\n"
            f"{hbold('Формат:')} {resource.kind.label}\n"
            f"{hbold('Тэги:')} {', '.join(resource.tags) if resource.tags else 'не указаны'}"
        )
        buttons = ["Тип", "Формат", "Тэги", "Назад"]
        actions = ["change_type", "change_format", "change_tags", "back"]

    await message.edit_text(
        msg,
        reply_markup=create_kb_tags(buttons, pack_callback_data_list(actions)),
    )


async def _show_save_summary(callback: types.CallbackQuery, state: FSMContext):
    message = get_editable_message(callback)
    if message is None:
        return
    data = await state.get_data()
    resource = data["resource"]
    is_edit = data.get("edit_mode", False)

    if is_edit:
        msg = (
            f"Проверьте изменения перед сохранением\n\n"
            f"{hbold('Название:')} {resource.title}\n"
            f"{hbold('Тип:')} {resource.resource_type.label}\n"
            f"{hbold('Формат:')} {resource.kind.label}\n"
            f"{hbold('Статус:')} {resource.status.label}\n"
            f"{hbold('Тэги:')} {', '.join(resource.tags) if resource.tags else 'не указаны'}\n"
            f"{hbold('Заметки:')} {resource.my_notes or 'нет'}\n"
            f"{hbold('Рейтинг:')} {resource.my_rating or '—'}/5\n"
            f"{hbold('Дата завершения:')} {resource.completed_at or 'не указана'}"
        )
    else:
        msg = (
            f"Проверьте данные перед сохранением\n\n"
            f"{hbold('Ссылка:')} {resource.url}\n"
            f"{hbold('Название:')} {resource.title}\n"
            f"{hbold('Тип:')} {resource.resource_type.label}\n"
            f"{hbold('Формат:')} {resource.kind.label}\n"
            f"{hbold('Тэги:')} {', '.join(resource.tags) if resource.tags else 'не указаны'}"
        )

    await message.edit_text(
        msg,
        reply_markup=create_kb_tags(
            ["Сохранить", "Изменить", "Отмена"],
            pack_callback_data_list(["save", "edit", "cancel"]),
        ),
    )
