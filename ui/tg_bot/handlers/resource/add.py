import asyncio
import logging
from datetime import datetime

from aiogram import Bot, F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold

from config import PROXY_URL, YOUTUBE_API_KEY
from core.models.resource import Resource, ResourceKind, ResourceStatus, ResourceType
from core.service import ResourceService
from data.service_db import ResourceDB
from ui.tg_bot.callbacks.resource import (
    ResourceCallback,
    get_callback_data,
    pack_callback_data_list,
)
from ui.tg_bot.keyboards.resource import create_kb_tags, create_kb_type
from ui.tg_bot.states.resource import ResourceState
from ui.tg_bot.utils.error_handler import handle_resource_error
from ui.tg_bot.utils.fsm import exit_fsm
from ui.tg_bot.utils.message import (
    auto_delete,
    cleanup_previous_message,
    get_editable_message,
    safe_delete_many,
    with_action_label,
)

from .form import _show_edit_menu, _show_save_summary, handle_form_actions

add_router = Router()


@add_router.message(Command("add"))
@add_router.message(F.text == "Добавить ресурс")
async def cmd_add(message: types.Message, state: FSMContext, bot: Bot) -> None:
    await cleanup_previous_message(message, state, bot)
    await state.clear()
    await state.set_state(ResourceState.waiting_for_link)
    await message.delete()
    prompt_msg = await message.answer(
        with_action_label(
            "add", "Пришлите ссылку на статью, видео или другой материал"
        ),
    )
    await state.update_data(prompt_msg_id=prompt_msg.message_id)


@add_router.message(ResourceState.waiting_for_link, F.text)
async def process_link(message: types.Message, state: FSMContext, bot: Bot):
    if await exit_fsm(message, state):
        return
    data = await state.get_data()
    prompt_msg_id = data.get("prompt_msg_id")
    await safe_delete_many(
        bot,
        message.chat.id,
        *([prompt_msg_id] if prompt_msg_id else []),
        message.message_id,
    )
    link = message.text
    if link is None:
        return
    if not Resource._is_valid_url(link):
        error_msg = await message.answer(
            with_action_label("error_add", f"Некорректная ссылка: {link}")
        )
        await state.update_data(error_msg_id=error_msg.message_id)
        asyncio.create_task(
            auto_delete(bot, message.chat.id, error_msg.message_id, delay=5)
        )
        return
    title = ResourceService.get_info_for_url(
        link,
        proxy=PROXY_URL,
        youtube_api_key=YOUTUBE_API_KEY,
    )["title"]
    await state.update_data(title=title)
    await state.update_data(link=link)
    await state.set_state(ResourceState.waiting_for_type)
    await message.answer(
        with_action_label("add", "Выберите тип:", title),
        reply_markup=create_kb_type(list(ResourceType), get_callback_data),
    )


@add_router.callback_query(ResourceState.waiting_for_type, ResourceCallback.filter())
async def process_type(
    callback: types.CallbackQuery, callback_data: ResourceCallback, state: FSMContext
):
    message = get_editable_message(callback)
    if message is None:
        return
    data = await state.get_data()
    is_edit = data.get("edit_target") == "change_type"

    await state.update_data(resource_type=callback_data.action)

    if is_edit:
        resource = data["resource"]
        ResourceService.edit_resource(
            resource, resource_type=ResourceType.from_code(callback_data.action)
        )
        await state.update_data(resource=resource, edit_target=None)
        await state.set_state(ResourceState.waiting_for_save)
        await _show_save_summary(callback, state)
    else:
        await state.set_state(ResourceState.waiting_for_format)
        await message.edit_text(
            with_action_label("add", "Выберите формат", data["title"]),
            reply_markup=create_kb_type(list(ResourceKind), get_callback_data),
        )


@add_router.callback_query(ResourceState.waiting_for_format, ResourceCallback.filter())
async def process_format(
    callback: types.CallbackQuery,
    callback_data: ResourceCallback,
    state: FSMContext,
    logger: logging.Logger,
):
    data = await state.get_data()
    is_edit = data.get("edit_target") == "change_format"

    if is_edit:
        resource = data["resource"]
        ResourceService.edit_resource(
            resource, kind=ResourceKind.from_code(callback_data.action)
        )
        await state.update_data(resource=resource, edit_target=None)
        await state.set_state(ResourceState.waiting_for_save)
        await _show_save_summary(callback, state)
        return
    else:
        await state.update_data(resource_format=callback_data.action)
        try:
            resource = ResourceService.create_resource(
                tg_id=callback.from_user.id,
                url=data["link"],
                resource_type=data["resource_type"],
                kind=ResourceKind.from_code(callback_data.action),
                proxy=PROXY_URL,
                youtube_api_key=YOUTUBE_API_KEY,
            )
        except Exception as e:
            handled = await handle_resource_error(
                callback=callback,
                error=e,
                context={"user_id": callback.from_user.id, "url": data.get("link")},
                logger=logger,
                with_action_label=with_action_label,
            )
            if handled:
                return
            raise
        await state.update_data(resource=resource)
        await state.set_state(ResourceState.waiting_for_save)
        await _show_save_summary(callback, state)


@add_router.message(ResourceState.waiting_for_new_tags)
async def process_new_tags(message: types.Message, state: FSMContext, bot: Bot):
    if message.text is None:
        return
    if await exit_fsm(message, state):
        return
    new_tags = [t.strip() for t in message.text.split(",") if t.strip()]
    data = await state.get_data()
    prompt_msg_id = data.get("prompt_msg_id")
    await safe_delete_many(
        bot,
        message.chat.id,
        *([prompt_msg_id] if prompt_msg_id else []),
        message.message_id,
    )

    resource = data["resource"]
    old_tags = resource.tags.copy()

    await state.update_data(
        new_tags=new_tags if new_tags else None,
        old_tags=old_tags,
        edit_target=None,
    )
    await state.set_state(ResourceState.waiting_for_save)

    msg = (
        f"{hbold('Новые тэги:')}\n\n"
        f"{hbold('Название:')} {resource.title}\n"
        f"{hbold('Старые тэги:')} {', '.join(old_tags) if old_tags else 'не указаны'}\n"
        f"{hbold('Новые тэги:')} {', '.join(new_tags) if new_tags else 'удалены'}\n\n"
        "Что делаем?"
    )
    await message.answer(
        msg,
        reply_markup=create_kb_tags(
            ["Применить новые", "Изменить ещё", "Оставить старые", "Отмена"],
            pack_callback_data_list(
                ["apply_new_tags", "change_tags", "keep_old_tags", "back"]
            ),
        ),
    )


@add_router.callback_query(ResourceState.waiting_for_save, ResourceCallback.filter())
async def process_save_or_edit(
    callback: types.CallbackQuery,
    callback_data: ResourceCallback,
    state: FSMContext,
    resource_db: ResourceDB,
    logger: logging.Logger,
):
    message = get_editable_message(callback)
    if message is None:
        return

    data = await state.get_data()
    edit_target = data.get("edit_target")

    if edit_target == "change_status":
        resource = data["resource"]
        try:
            new_status = ResourceStatus.from_code(callback_data.action)
            resource.update_status(new_status)
        except Exception:
            await callback.answer("Неверный статус", show_alert=True)
            return

        await state.update_data(resource=resource, edit_target=None)
        await _show_save_summary(callback, state)
        return

    if callback_data.action.startswith("set_rating_"):
        rating = int(callback_data.action.split("_")[2])
        data = await state.get_data()
        resource = data["resource"]
        resource.my_rating = rating if rating > 0 else None
        await state.update_data(resource=resource)
        await _show_edit_menu(callback, state, message)

    await handle_form_actions(
        callback=callback,
        callback_data=callback_data,
        state=state,
        resource_db=resource_db,
        message=message,
        logger=logger,
    )


@add_router.message(ResourceState.waiting_for_notes)
async def process_notes(message: types.Message, state: FSMContext, bot: Bot):
    if message.text is None:
        return
    if await exit_fsm(message, state):
        return

    data = await state.get_data()
    resource = data["resource"]
    text = message.text.strip()

    if text == "-":
        resource.my_notes = None
    else:
        resource.my_notes = text

    await message.delete()
    await state.update_data(resource=resource, edit_target=None)
    await state.set_state(ResourceState.waiting_for_save)
    await _show_save_summary_direct(message, state)


@add_router.message(ResourceState.waiting_for_rating)
async def process_rating(message: types.Message, state: FSMContext, bot: Bot):
    if message.text is None:
        return
    if await exit_fsm(message, state):
        return

    data = await state.get_data()
    resource = data["resource"]
    text = message.text.strip()

    if not text.isdigit() or not (1 <= int(text) <= 5):
        error_msg = await message.answer("Введите число от 1 до 5.")
        await state.update_data(error_msg_id=error_msg.message_id)
        asyncio.create_task(
            auto_delete(bot, message.chat.id, error_msg.message_id, delay=3)
        )
        return

    resource.my_rating = int(text)
    await message.delete()
    await state.update_data(resource=resource, edit_target=None)
    await state.set_state(ResourceState.waiting_for_save)
    await _show_save_summary_direct(message, state)


@add_router.message(ResourceState.waiting_for_date)
async def process_date(message: types.Message, state: FSMContext, bot: Bot):
    if message.text is None:
        return
    if await exit_fsm(message, state):
        return

    data = await state.get_data()
    resource = data["resource"]
    text = message.text.strip()

    if text == "-":
        resource.completed_at = None
    else:
        try:
            resource.completed_at = datetime.fromisoformat(text)
        except ValueError:
            error_msg = await message.answer(
                "Неверный формат. Используйте ГГГГ-ММ-ДД или '-' для сброса."
            )
            await state.update_data(error_msg_id=error_msg.message_id)
            asyncio.create_task(
                auto_delete(bot, message.chat.id, error_msg.message_id, delay=4)
            )
            return

    await message.delete()
    await state.update_data(resource=resource, edit_target=None)
    await state.set_state(ResourceState.waiting_for_save)
    await _show_save_summary_direct(message, state)


async def _show_save_summary_direct(message: types.Message, state: FSMContext):
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

    await message.answer(
        msg,
        reply_markup=create_kb_tags(
            ["Сохранить", "Изменить", "Отмена"],
            pack_callback_data_list(["save", "edit", "cancel"]),
        ),
    )
