import logging
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.markdown import hbold

from data.service_db import ResourceDB
from data_io.import_data import parse_data
from ui.tg_bot.callbacks.resource import pack_callback_data_list
from ui.tg_bot.keyboards.resource import create_kb_tags
from ui.tg_bot.states.resource import ResourceState
from ui.tg_bot.utils.error_handler import handle_resource_error
from ui.tg_bot.utils.message import cleanup_previous_message, with_action_label

import_data_router = Router()


@import_data_router.message(ResourceState.waiting_for_import_data, F.document)
async def process_import_data(
    message: Message,
    state: FSMContext,
    resource_db: ResourceDB,
    bot: Bot,
    logger: logging.Logger,
):
    if message.document is None or message.from_user is None:
        return

    data = await state.get_data()
    mode = data.get("import_mode", "fast")
    tg_id = message.from_user.id
    await cleanup_previous_message(message, state, bot)
    await state.clear()

    status_msg = await message.answer("Скачиваю файл...")

    file = await bot.get_file(message.document.file_id)
    file_path = file.file_path
    if file_path is None:
        await status_msg.edit_text("Ошибка: не удалось получить файл.")
        return

    imports_dir = Path("imports")
    imports_dir.mkdir(exist_ok=True)
    dest = str(imports_dir / f"{tg_id}_{message.document.file_name}")
    await bot.download_file(file_path, dest)

    await status_msg.edit_text("Обрабатываю данные...")

    resources = parse_data(dest)
    if mode == "fast":
        try:
            count, total, errors = resource_db.import_data(resources, tg_id)
        except Exception as e:
            await handle_resource_error(
                error=e,
                logger=logger,
                with_action_label=with_action_label,
                action="error_import",
                message=message,
                context={"user_id": tg_id},
            )
            await status_msg.delete()
            await state.clear()
            return

        msg = f"Импортировано {count} из {total} ресурсов."
        if errors:
            msg += "\n\nОшибки:\n" + "\n".join(errors[-10:])
        await status_msg.edit_text(msg, disable_web_page_preview=True)

        await state.clear()
        await state.update_data(prompt_msg_id=status_msg.message_id)

    elif mode == "detailed":
        await state.update_data(
            import_resources=resources,
            import_index=0,
            import_results={"count": 0, "errors": []},
        )
        await status_msg.delete()
        await _start_next_resource(message, state, resource_db, logger)


async def _start_next_resource(
    message: Message, state: FSMContext, resource_db: ResourceDB, logger: logging.Logger
):
    data = await state.get_data()
    resources = data["import_resources"]
    index = data["import_index"]
    total = len(resources)
    if message.from_user is None:
        return
    tg_id = message.from_user.id

    if index >= total:
        results = data["import_results"]
        msg = f"Импортировано {results['count']} из {total} ресурсов."
        if results["errors"]:
            msg += "\n\nОшибки:\n" + "\n".join(results["errors"][-10:])
        await message.answer(msg, disable_web_page_preview=True)
        await state.clear()
        return

    resource = resources[index]

    existing = resource_db.get_by_url(resource.url, tg_id)
    if existing is not None:
        results = data["import_results"]
        results["errors"].append(f"Дубликат: {resource.url}")
        await state.update_data(import_index=index + 1, import_results=results)
        await _start_next_resource(message, state, resource_db, logger)
        return

    await state.update_data(
        resource=resource,
        title=resource.title,
        edit_mode=True,
    )
    await state.set_state(ResourceState.waiting_for_save)
    await message.answer(
        f"[{index + 1}/{total}] {hbold(resource.title)}\n\nПроверьте данные и сохраните или измените.",
        reply_markup=create_kb_tags(
            ["Сохранить", "Изменить", "Отмена"],
            pack_callback_data_list(["save", "edit", "cancel"]),
        ),
        disable_web_page_preview=True,
    )


async def _start_next_resource_from_callback(
    callback,
    state: FSMContext,
    resource_db: ResourceDB,
    logger: logging.Logger,
    index: int,
):
    data = await state.get_data()
    resources = data["import_resources"]
    total = len(resources)
    tg_id = callback.from_user.id

    if index >= total:
        results = data["import_results"]
        msg = f"Импортировано {results['count']} из {total} ресурсов."
        if results["errors"]:
            msg += "\n\nОшибки:\n" + "\n".join(results["errors"][-10:])
        await state.clear()
        await callback.message.edit_text(msg, disable_web_page_preview=True)
        return

    resource = resources[index]

    existing = resource_db.get_by_url(resource.url, tg_id)
    if existing is not None:
        results = data["import_results"]
        results["errors"].append(f"Дубликат: {resource.url}")
        await state.update_data(import_index=index + 1, import_results=results)
        await _start_next_resource_from_callback(
            callback, state, resource_db, logger, index + 1
        )
        return

    await state.update_data(
        resource=resource,
        title=resource.title,
        edit_mode=True,
        import_index=index,
    )
    await state.set_state(ResourceState.waiting_for_save)
    await callback.message.edit_text(
        f"[{index + 1}/{total}] {hbold(resource.title)}\n\n"
        f"{hbold('Проверьте данные перед сохранением')}\n\n"
        f"{hbold('Название:')} {resource.title}\n"
        f"{hbold('Тип:')} {resource.resource_type.label}\n"
        f"{hbold('Формат:')} {resource.kind.label}\n"
        f"{hbold('Тэги:')} {', '.join(resource.tags) if resource.tags else 'не указаны'}",
        reply_markup=create_kb_tags(
            ["Сохранить", "Изменить", "Отмена"],
            pack_callback_data_list(["save", "edit", "cancel"]),
        ),
        disable_web_page_preview=True,
    )
