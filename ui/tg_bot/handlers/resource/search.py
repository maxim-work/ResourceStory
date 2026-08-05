from aiogram import Bot, F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.markdown import hbold

from config import RESOURCES_PER_PAGE
from data.filter import ResourceFilter
from ui.tg_bot.callbacks.resource import SearchCallback
from ui.tg_bot.keyboards.resource import create_search_keyboard
from ui.tg_bot.states.resource import ResourceState
from ui.tg_bot.utils.fsm import exit_fsm
from ui.tg_bot.utils.message import (
    cleanup_previous_message,
    get_editable_message,
    with_action_label,
)

search_router = Router()


@search_router.message(Command("search"))
@search_router.message(F.text == "Поиск")
async def cmd_search(message: Message, state: FSMContext, bot: Bot):
    await cleanup_previous_message(message, state, bot)
    await state.clear()
    await state.set_state(ResourceState.waiting_for_search)
    prompt_msg = await message.answer(
        with_action_label("edit", "Введите ключевые слова для поиска:")
    )
    await state.update_data(prompt_msg_id=prompt_msg.message_id)


@search_router.message(ResourceState.waiting_for_search)
async def process_search(message: Message, state: FSMContext, resource_db):
    if message.text is None:
        return
    if await exit_fsm(message, state):
        return

    keywords = message.text.strip()
    if not keywords:
        await message.answer("Введите хотя бы одно ключевое слово.")
        return

    if message.from_user is None:
        return

    tg_id = message.from_user.id
    f = ResourceFilter(tg_id=tg_id, keywords=keywords, limit=10)
    results = resource_db.search(tg_id=tg_id, filter=f)

    if not results:
        await message.answer("Ничего не найдено.")
        await state.clear()
        return

    await state.update_data(search_results=results)

    total_pages = (len(results) + RESOURCES_PER_PAGE - 1) // RESOURCES_PER_PAGE
    page_results = results[:RESOURCES_PER_PAGE]

    await message.answer(
        _render_search_results(page_results, 1, total_pages),
        reply_markup=create_search_keyboard(page_results, 1, total_pages),
    )


@search_router.callback_query(SearchCallback.filter())
async def search_callback(
    callback: types.CallbackQuery,
    callback_data: SearchCallback,
    state: FSMContext,
    resource_db,
):
    message = get_editable_message(callback)
    if message is None:
        return

    data = await state.get_data()
    results = data.get("search_results", [])
    action = callback_data.action
    page = callback_data.page or 1
    resource_id = callback_data.resource_id

    if action in ("page", "prev", "next"):
        total = (len(results) + RESOURCES_PER_PAGE - 1) // RESOURCES_PER_PAGE
        start = (page - 1) * RESOURCES_PER_PAGE
        page_results = results[start : start + RESOURCES_PER_PAGE]

        await message.edit_text(
            _render_search_results(page_results, page, total),
            reply_markup=create_search_keyboard(page_results, page, total),
        )

    elif action == "results":
        total = (len(results) + RESOURCES_PER_PAGE - 1) // RESOURCES_PER_PAGE
        page_results = results[:RESOURCES_PER_PAGE]

        await message.edit_text(
            _render_search_results(page_results, 1, total),
            reply_markup=create_search_keyboard(page_results, 1, total),
        )

    elif action == "view":
        tg_id = callback.from_user.id
        r = resource_db.get(resource_id, tg_id)
        if r is None:
            await callback.answer("Ресурс не найден", show_alert=True)
            return

        builder = InlineKeyboardBuilder()
        builder.button(
            text="К результатам",
            callback_data=SearchCallback(action="results", page=1).pack(),
        )
        builder.button(
            text="Редактировать",
            callback_data=SearchCallback(action="edit", resource_id=r.id).pack(),
        )
        builder.button(
            text="Удалить",
            callback_data=SearchCallback(
                action="confirm_delete", resource_id=r.id
            ).pack(),
        )
        builder.adjust(1, 2)

        await message.edit_text(
            _format_resource_detail(r), reply_markup=builder.as_markup()
        )

    elif action == "confirm_delete":
        r = resource_db.get(resource_id, callback.from_user.id)
        if r is None:
            await callback.answer("Ресурс не найден", show_alert=True)
            return

        builder = InlineKeyboardBuilder()
        builder.button(
            text="Да, удалить",
            callback_data=SearchCallback(
                action="delete", resource_id=resource_id
            ).pack(),
        )
        builder.button(
            text="Нет",
            callback_data=SearchCallback(action="view", resource_id=resource_id).pack(),
        )
        builder.adjust(2)

        await message.edit_text(
            f"Удалить ресурс «{r.title}»?",
            reply_markup=builder.as_markup(),
        )

    elif action == "delete":
        resource_db.delete(resource_id, callback.from_user.id)
        await callback.answer("Удалено")

        results = [(r, s) for r, s in results if r.id != resource_id]
        await state.update_data(search_results=results)

        if not results:
            await message.edit_text("Ресурс удалён. Больше нет результатов поиска.")
            await state.clear()
            return

        total = (len(results) + RESOURCES_PER_PAGE - 1) // RESOURCES_PER_PAGE
        page_results = results[:RESOURCES_PER_PAGE]

        await message.edit_text(
            _render_search_results(page_results, 1, total),
            reply_markup=create_search_keyboard(page_results, 1, total),
        )

    elif action == "edit":
        tg_id = callback.from_user.id
        r = resource_db.get(resource_id, tg_id)
        if r is None:
            await callback.answer("Ресурс не найден", show_alert=True)
            return

        await state.update_data(resource=r, title=r.title, edit_mode=True)
        await state.set_state(ResourceState.waiting_for_save)

        from .form import _show_save_summary

        await _show_save_summary(callback, state)

    await callback.answer()


def _render_search_results(results: list, page: int, total_pages: int) -> str:
    lines = [f"{hbold('Результаты поиска:')}"]
    for i, (r, score) in enumerate(results, 1):
        lines.append(f"{i}. [{score}] {r.title} — {r.resource_type.label}")
    if total_pages > 1:
        lines.append(f"\nСтраница {page}/{total_pages}")
    return "\n".join(lines)


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
