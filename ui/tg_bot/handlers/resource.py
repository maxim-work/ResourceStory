import asyncio
import logging

from aiogram import Bot, F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold

from config import PROXY_URL, YOUTUBE_API_KEY
from core.models.resource import Resource, ResourceKind, ResourceType
from core.service import ResourceService
from ui.tg_bot.callbacks.resource import AddResourceCallback
from ui.tg_bot.keyboards.resource import create_kb_tags, create_kb_type
from ui.tg_bot.states.resource import AddResourceState
from ui.tg_bot.utils.error_handler import handle_resource_error
from ui.tg_bot.utils.message import auto_delete, safe_delete_many, with_action_label

resource_router = Router()


def get_callback_data(option: str) -> str:
    return AddResourceCallback(option=option).pack()


def pack_callback_data_list(options: list[str]) -> list[str]:
    return [AddResourceCallback(option=opt).pack() for opt in options]


async def show_save_summary(callback: types.CallbackQuery, state: FSMContext):
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
    await callback.message.edit_text(
        msg,
        reply_markup=create_kb_tags(
            ["Сохранить", "Изменить", "Отмена"],
            pack_callback_data_list(["save", "edit", "cancel"]),
        ),
    )


@resource_router.message(Command("add"))
async def cmd_add(message: types.Message, state: FSMContext) -> None:
    await state.set_state(AddResourceState.waiting_for_link)
    await message.delete()
    prompt_msg = await message.answer(
        with_action_label("add", "Пришлите ссылку на статью, видео или другой материал")
    )
    await state.update_data(prompt_msg_id=prompt_msg.message_id)


@resource_router.message(AddResourceState.waiting_for_link, F.text)
async def process_link(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    prompt_msg_id = data.get("prompt_msg_id")
    await safe_delete_many(
        bot,
        message.chat.id,
        *([prompt_msg_id] if prompt_msg_id else []),
        message.message_id,
    )
    link = message.text
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
    await state.set_state(AddResourceState.waiting_for_type)
    await message.answer(
        with_action_label("add", "Выберите тип:", title),
        reply_markup=create_kb_type(list(ResourceType), get_callback_data),
    )


@resource_router.callback_query(
    AddResourceState.waiting_for_type, AddResourceCallback.filter()
)
async def process_type(
    callback: types.CallbackQuery, callback_data: AddResourceCallback, state: FSMContext
):
    data = await state.get_data()
    is_edit = data.get("edit_target") == "change_type"

    await state.update_data(resource_type=callback_data.option)

    if is_edit:
        resource = data["resource"]
        ResourceService.edit_resource(
            resource, resource_type=ResourceType.from_code(callback_data.option)
        )
        await state.update_data(resource=resource, edit_target=None)
        await state.set_state(AddResourceState.waiting_for_save)
        await show_save_summary(callback, state)
    else:
        await state.set_state(AddResourceState.waiting_for_format)
        await callback.message.edit_text(
            with_action_label("add", "Выберите формат", data["title"]),
            reply_markup=create_kb_type(list(ResourceKind), get_callback_data),
        )


@resource_router.callback_query(
    AddResourceState.waiting_for_format, AddResourceCallback.filter()
)
async def process_format(
    callback: types.CallbackQuery,
    callback_data: AddResourceCallback,
    state: FSMContext,
    logger: logging.Logger,
):
    data = await state.get_data()
    is_edit = data.get("edit_target") == "change_format"

    if is_edit:
        resource = data["resource"]
        ResourceService.edit_resource(
            resource, kind=ResourceKind.from_code(callback_data.option)
        )
        await state.update_data(resource=resource, edit_target=None)
        await state.set_state(AddResourceState.waiting_for_save)
        await show_save_summary(callback, state)
        return
    else:
        await state.update_data(resource_format=callback_data.option)
        try:
            resource = ResourceService.create_resource(
                user_id=callback.from_user.id,
                url=data["link"],
                resource_type=data["resource_type"],
                kind=ResourceKind.from_code(callback_data.option),
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
        await state.set_state(AddResourceState.waiting_for_save)
        await show_save_summary(callback, state)


@resource_router.message(AddResourceState.waiting_for_new_tags)
async def process_new_tags(message: types.Message, state: FSMContext, bot: Bot):
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
    await state.set_state(AddResourceState.waiting_for_save)

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


@resource_router.callback_query(
    AddResourceState.waiting_for_save, AddResourceCallback.filter()
)
async def process_save_or_edit(
    callback: types.CallbackQuery, callback_data: AddResourceCallback, state: FSMContext
):
    if callback_data.option == "save":
        data = await state.get_data()
        resource = data["resource"]
        resource_id = 0
        # try:
        #     resource_id = db.insert(resource)
        # except DuplicateResourceError as e:
        #     clear()
        #     print(f"ERROR: {e}")
        #     pause()
        #     return
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
        await state.clear()
        await callback.message.edit_text(msg)

    elif callback_data.option == "cancel":
        msg = (
            f"{hbold('Добавление отменено')}\n\n"
            "Ресурс не сохранён. Чтобы начать заново, используйте /add"
        )
        await state.clear()
        await callback.message.edit_text(msg)

    elif callback_data.option == "apply_new_tags":
        data = await state.get_data()
        resource = data["resource"]
        new_tags = data.get("new_tags")
        resource.tags = new_tags if new_tags else None
        await state.update_data(resource=resource, new_tags=None, old_tags=None)
        await show_save_summary(callback, state)

    elif callback_data.option == "keep_old_tags":
        await state.update_data(new_tags=None, old_tags=None)
        await show_save_summary(callback, state)

    elif callback_data.option == "back":
        await show_save_summary(callback, state)

    elif callback_data.option in ("change_type", "change_format", "change_tags"):
        data = await state.get_data()
        await state.update_data(edit_target=callback_data.option)

        if callback_data.option == "change_type":
            await state.set_state(AddResourceState.waiting_for_type)
            await callback.message.edit_text(
                with_action_label("edit", "Выберите новый тип:", data["title"]),
                reply_markup=create_kb_type(list(ResourceType), get_callback_data),
            )
        elif callback_data.option == "change_format":
            await state.set_state(AddResourceState.waiting_for_format)
            await callback.message.edit_text(
                with_action_label("edit", "Выберите новый формат:", data["title"]),
                reply_markup=create_kb_type(list(ResourceKind), get_callback_data),
            )
        elif callback_data.option == "change_tags":
            await state.set_state(AddResourceState.waiting_for_new_tags)
            prompt_msg = await callback.message.edit_text(
                with_action_label("edit", "Напишите новые тэги:", data["title"])
            )
            await state.update_data(prompt_msg_id=prompt_msg.message_id)

    elif callback_data.option == "edit":
        data = await state.get_data()
        resource = data["resource"]
        msg = (
            f"{hbold('Выберите, что хотите изменить')}\n\n"
            f"{hbold('Тип:')} {resource.resource_type.label}\n"
            f"{hbold('Формат:')} {resource.kind.label}\n"
            f"{hbold('Тэги:')} {', '.join(resource.tags) if resource.tags else 'не указаны'}"
        )
        await callback.message.edit_text(
            msg,
            reply_markup=create_kb_tags(
                ["Тип", "Формат", "Тэги", "Назад"],
                pack_callback_data_list(
                    ["change_type", "change_format", "change_tags", "back"]
                ),
            ),
        )
