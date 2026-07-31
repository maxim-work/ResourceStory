from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.markdown import hbold

from core.models.resource import ResourceKind, ResourceType
from data.exceptions import DuplicateResourceError
from data.service_db import ResourceDB
from ui.tg_bot.callbacks.resource import get_callback_data, pack_callback_data_list
from ui.tg_bot.keyboards.resource import (
    ResourceCallback,
    create_kb_tags,
    create_kb_type,
)
from ui.tg_bot.utils.message import get_editable_message, with_action_label


async def handle_form_actions(
    callback: types.CallbackQuery,
    callback_data: ResourceCallback,
    state: FSMContext,
    resource_db: ResourceDB,
    message: types.Message,
    waiting_for_save_state,
):

    action = callback_data.action

    if action == "save":
        await _handle_save(callback, state, resource_db, message)

    elif action == "cancel":
        await _handle_cancel(callback, state, message)

    elif action == "apply_new_tags":
        await _handle_apply_new_tags(callback, state)

    elif action == "keep_old_tags":
        await _handle_keep_old_tags(callback, state)

    elif action == "back":
        await _show_save_summary(callback, state)

    elif action in ("change_type", "change_format", "change_tags"):
        await _handle_change_field(callback, callback_data, state, message)

    elif action == "edit":
        await _show_edit_menu(callback, state, message)


async def _handle_save(
    callback: types.CallbackQuery,
    state: FSMContext,
    resource_db: ResourceDB,
    message: types.Message,
):
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
                f"{hbold('Платформа:')} {resource.platform.label}\n"
                f"{hbold('Тэги:')} {', '.join(resource.tags) if resource.tags else 'не указаны'}\n"
                f"{hbold('Длительность:')} {resource.duration_display}\n"
                f"{hbold('Рейтинг:')} {resource.rating:.1f}"
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
                f"{hbold('Рейтинг:')} {resource.rating:.1f}\n"
                f"{hbold('ID:')} {resource_id}"
            )
    except DuplicateResourceError:
        msg = "Ресурс с такой ссылкой уже существует"

    await state.clear()
    await message.edit_text(msg)


async def _handle_cancel(
    callback: types.CallbackQuery,
    state: FSMContext,
    message: types.Message,
):
    data = await state.get_data()
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


async def _handle_apply_new_tags(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    data = await state.get_data()
    resource = data["resource"]
    new_tags = data.get("new_tags")
    resource.tags = new_tags if new_tags else None
    await state.update_data(resource=resource, new_tags=None, old_tags=None)
    await _show_save_summary(callback, state)


async def _handle_keep_old_tags(
    callback: types.CallbackQuery,
    state: FSMContext,
):
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

    if callback_data.action == "change_type":
        from ui.tg_bot.states.resource import AddResourceState

        await state.set_state(AddResourceState.waiting_for_type)
        await message.edit_text(
            with_action_label("edit", "Выберите новый тип:", data["title"]),
            reply_markup=create_kb_type(list(ResourceType), get_callback_data),
        )
    elif callback_data.action == "change_format":
        from ui.tg_bot.states.resource import AddResourceState

        await state.set_state(AddResourceState.waiting_for_format)
        await message.edit_text(
            with_action_label("edit", "Выберите новый формат:", data["title"]),
            reply_markup=create_kb_type(list(ResourceKind), get_callback_data),
        )
    elif callback_data.action == "change_tags":
        from ui.tg_bot.states.resource import AddResourceState

        await state.set_state(AddResourceState.waiting_for_new_tags)
        result = await message.edit_text(
            with_action_label("edit", "Напишите новые тэги:", data["title"])
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

    msg = (
        f"{hbold('Выберите, что хотите изменить')}\n\n"
        f"{hbold('Тип:')} {resource.resource_type.label}\n"
        f"{hbold('Формат:')} {resource.kind.label}\n"
        f"{hbold('Тэги:')} {', '.join(resource.tags) if resource.tags else 'не указаны'}"
    )
    await message.edit_text(
        msg,
        reply_markup=create_kb_tags(
            ["Тип", "Формат", "Тэги", "Назад"],
            pack_callback_data_list(
                ["change_type", "change_format", "change_tags", "back"]
            ),
        ),
    )


async def _show_save_summary(callback: types.CallbackQuery, state: FSMContext):
    message = get_editable_message(callback)
    if message is None:
        return
    data = await state.get_data()
    resource = data["resource"]
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
