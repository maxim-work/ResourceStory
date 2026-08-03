from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.markdown import hbold

from config import RESOURCES_PER_PAGE
from ui.tg_bot.callbacks.resource import ResourceCallback
from ui.tg_bot.keyboards.resource import create_list_keyboard
from ui.tg_bot.states.resource import ResourceState
from ui.tg_bot.utils.message import get_editable_message

from .form import _show_save_summary

list_router = Router()


def _format_resource_detail(r) -> str:
    return (
        f"{hbold(r.title)}\n\n"
        f"{hbold('Ссылка:')} {r.url}\n"
        f"{hbold('Тип:')} {r.resource_type.label}\n"
        f"{hbold('Формат:')} {r.kind.label}\n"
        f"{hbold('Платформа:')} {r.platform.label}\n"
        f"{hbold('Статус:')} {r.status.label}\n"
        f"{hbold('Тэги:')} {', '.join(r.tags) if r.tags else 'не указаны'}\n"
        f"{hbold('Длительность:')} {r.duration_display}\n"
        f"{hbold('Рейтинг:')} {r.my_rating or '—'}\n"
    )


@list_router.message(Command("list"))
@list_router.message(F.text == "Мои ресурсы")
async def cmd_list(message: Message, state: FSMContext, resource_db):
    await state.clear()
    if message.from_user is None:
        return

    resources = resource_db.get_all_resources(message.from_user.id)

    if not resources:
        await message.answer("У вас пока нет сохранённых ресурсов.")
        return

    total_pages = (len(resources) + RESOURCES_PER_PAGE - 1) // RESOURCES_PER_PAGE
    page_resources = resources[:RESOURCES_PER_PAGE]

    await message.answer(
        _render_resource_list(page_resources, 1, total_pages),
        reply_markup=create_list_keyboard(page_resources, 1, total_pages),
    )


@list_router.callback_query(ResourceCallback.filter())
async def list_callback(
    callback: CallbackQuery,
    callback_data: ResourceCallback,
    state: FSMContext,
    resource_db,
):
    message = get_editable_message(callback)
    if message is None:
        return

    tg_id = callback.from_user.id
    action = callback_data.action
    page = callback_data.page or 1
    resource_id = callback_data.resource_id

    if action in ("page", "prev", "next"):
        resources = resource_db.get_all_resources(tg_id)
        total = (len(resources) + RESOURCES_PER_PAGE - 1) // RESOURCES_PER_PAGE
        start = (page - 1) * RESOURCES_PER_PAGE
        page_resources = resources[start : start + RESOURCES_PER_PAGE]

        await message.edit_text(
            _render_resource_list(page_resources, page, total),
            reply_markup=create_list_keyboard(page_resources, page, total),
        )

    elif action in ("view", "edit", "delete", "confirm_delete"):
        if resource_id is None:
            return

        if action == "view":
            r = resource_db.get(resource_id, tg_id)
            if r is None:
                await callback.answer("Ресурс не найден", show_alert=True)
                return

            builder = InlineKeyboardBuilder()
            builder.button(
                text="К списку",
                callback_data=ResourceCallback(action="page", page=1).pack(),
            )
            builder.button(
                text="Редактировать",
                callback_data=ResourceCallback(action="edit", resource_id=r.id).pack(),
            )
            builder.button(
                text="Удалить",
                callback_data=ResourceCallback(
                    action="confirm_delete", resource_id=r.id, page=page
                ).pack(),
            )
            builder.adjust(1, 2)

            await message.edit_text(
                _format_resource_detail(r), reply_markup=builder.as_markup()
            )

        elif action == "edit":
            r = resource_db.get(resource_id, tg_id)
            if r is None:
                await callback.answer("Ресурс не найден", show_alert=True)
                return

            await state.update_data(
                resource=r,
                title=r.title,
                edit_mode=True,
            )
            await state.set_state(ResourceState.waiting_for_save)
            await _show_save_summary(callback, state)

        elif action == "confirm_delete":
            r = resource_db.get(resource_id, tg_id)
            if r is None:
                await callback.answer("Ресурс не найден", show_alert=True)
                return

            builder = InlineKeyboardBuilder()
            builder.button(
                text="Да, удалить",
                callback_data=ResourceCallback(
                    action="delete", resource_id=resource_id, page=page
                ).pack(),
            )
            builder.button(
                text="Нет",
                callback_data=ResourceCallback(
                    action="view", resource_id=resource_id, page=page
                ).pack(),
            )
            builder.adjust(2)

            await message.edit_text(
                f"Удалить ресурс «{r.title}»?",
                reply_markup=builder.as_markup(),
            )

        elif action == "delete":
            resource_db.delete(resource_id, tg_id)
            await callback.answer("Удалено")

            resources = resource_db.get_all_resources(tg_id)

            if not resources:
                await message.edit_text(
                    "Ресурс удалён. У вас больше нет сохранённых ресурсов."
                )
                return

            total = (len(resources) + RESOURCES_PER_PAGE - 1) // RESOURCES_PER_PAGE
            start = (page - 1) * RESOURCES_PER_PAGE
            page_resources = resources[start : start + RESOURCES_PER_PAGE]
            if not page_resources and page > 1:
                page -= 1
                start = (page - 1) * RESOURCES_PER_PAGE
                page_resources = resources[start : start + RESOURCES_PER_PAGE]

            await message.edit_text(
                _render_resource_list(page_resources, page, total),
                reply_markup=create_list_keyboard(page_resources, page, total),
            )

    await callback.answer()


def _render_resource_list(resources: list, page: int, total_pages: int) -> str:
    lines = [f"{hbold('Ваши ресурсы:')}"]
    for i, r in enumerate(resources, 1):
        lines.append(f"{i}. {r.title} — {r.resource_type.label}")
    if total_pages > 1:
        lines.append(f"\nСтраница {page}/{total_pages}")
    return "\n".join(lines)
