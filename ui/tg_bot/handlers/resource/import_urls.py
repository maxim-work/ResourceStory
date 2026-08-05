import logging
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import PROXY_URL, YOUTUBE_API_KEY
from core.models.resource import Resource, ResourceType
from core.service import ResourceService
from data.exceptions import DuplicateResourceError
from data.service_db import ResourceDB
from ui.tg_bot.callbacks.resource import get_callback_data
from ui.tg_bot.keyboards.resource import create_kb_type
from ui.tg_bot.states.resource import ResourceState
from ui.tg_bot.utils.message import cleanup_previous_message, with_action_label

import_urls_router = Router()


@import_urls_router.message(ResourceState.waiting_for_import_urls, F.document)
async def process_import_file(
    message: Message,
    state: FSMContext,
    resource_db: ResourceDB,
    bot: Bot,
    logger: logging.Logger,
):
    if message.from_user is None or message.document is None:
        return

    status_msg = await message.answer("Скачиваю файл...")

    file = await bot.get_file(message.document.file_id)
    file_path = file.file_path
    if file_path is None:
        await status_msg.edit_text("Ошибка: не удалось получить файл.")
        return

    from pathlib import Path

    Path("imports").mkdir(exist_ok=True)
    dest = f"imports/urls_{message.from_user.id}.txt"
    await bot.download_file(file_path, dest)

    with open(dest, "r", encoding="utf-8") as f:
        text = f.read()

    await status_msg.edit_text("Обрабатываю ссылки...")
    await _handle_urls_text(
        message=message,
        state=state,
        resource_db=resource_db,
        logger=logger,
        text=text,
        bot=bot,
        status_msg=status_msg,
    )


@import_urls_router.message(ResourceState.waiting_for_import_urls, F.text)
async def process_import_text(
    message: Message,
    state: FSMContext,
    resource_db: ResourceDB,
    logger: logging.Logger,
    bot: Bot,
):
    if message.from_user is None:
        return
    if message.text is None:
        return

    status_msg = await message.answer("Обрабатываю ссылки...")
    await _handle_urls_text(
        message=message,
        state=state,
        resource_db=resource_db,
        logger=logger,
        text=message.text,
        bot=bot,
        status_msg=status_msg,
    )


async def _handle_urls_text(
    message: Message,
    state: FSMContext,
    resource_db: ResourceDB,
    logger: logging.Logger,
    text: str,
    bot: Bot,
    status_msg: Optional[Message] = None,
):
    urls = [line.strip() for line in text.split("\n") if line.strip()]
    if not urls:
        if status_msg:
            await status_msg.edit_text("Не найдено ссылок.")
        else:
            await message.answer("Не найдено ссылок.")
        await state.clear()
        return

    data = await state.get_data()
    mode = data.get("import_mode", "fast")
    await cleanup_previous_message(message, state, bot)
    await state.clear()
    prompt_msg = None
    if mode == "fast":
        count = 0
        errors = []
        for url in urls:
            try:
                if not Resource._is_valid_url(url):
                    errors.append(f"Некорректная ссылка: {url}")
                    continue
                if message.from_user is None:
                    return
                resource = ResourceService.create_resource(
                    url=url,
                    tg_id=message.from_user.id,
                    resource_type=ResourceType.OTHER,
                    proxy=PROXY_URL,
                    youtube_api_key=YOUTUBE_API_KEY,
                )
                resource_db.insert(resource)
                count += 1
            except DuplicateResourceError:
                errors.append(f"Дубликат: {url}")
            except Exception as e:
                errors.append(str(e))

        msg = f"Импортировано {count} из {len(urls)} ссылок."
        if errors:
            msg += "\n\nОшибки:\n" + "\n".join(errors[-10:])
        if status_msg:
            prompt_msg = await status_msg.edit_text(msg, disable_web_page_preview=True)
        else:
            prompt_msg = await message.answer(msg, disable_web_page_preview=True)

    elif mode == "detailed":
        await state.update_data(
            import_urls=urls,
            import_index=0,
            import_results={"count": 0, "errors": []},
        )
        await _start_next_url(message, state, resource_db, logger, status_msg)
    if prompt_msg is Message:
        await state.update_data(prompt_msg_id=prompt_msg.message_id)


async def _start_next_url(
    message: Message,
    state: FSMContext,
    resource_db: ResourceDB,
    logger: logging.Logger,
    status_msg: Optional[Message] = None,
):
    data = await state.get_data()
    urls = data["import_urls"]
    index = data["import_index"]
    total = len(urls)
    if message.from_user is None:
        return

    tg_id = message.from_user.id

    if index >= total:
        results = data["import_results"]
        msg = f"Импортировано {results['count']} из {total} ссылок."
        if results["errors"]:
            msg += "\n\nОшибки:\n" + "\n".join(results["errors"][-10:])
        if status_msg:
            await status_msg.edit_text(msg, disable_web_page_preview=True)
        else:
            await message.answer(msg, disable_web_page_preview=True)
        await state.clear()
        return

    url = urls[index]

    existing = resource_db.get_by_url(url, tg_id)
    if existing is not None:
        results = data["import_results"]
        results["errors"].append(f"Дубликат: {url}")
        await state.update_data(import_index=index + 1, import_results=results)
        await _start_next_url(message, state, resource_db, logger, status_msg)
        return

    try:
        info = ResourceService.get_info_for_url(url, YOUTUBE_API_KEY, PROXY_URL)
        title = info["title"]
    except Exception:
        results = data["import_results"]
        results["errors"].append(f"Ошибка получения: {url}")
        await state.update_data(import_index=index + 1, import_results=results)
        await _start_next_url(message, state, resource_db, logger, status_msg)
        return

    if status_msg:
        try:
            await status_msg.delete()
        except Exception:
            pass
        status_msg = None

    await state.update_data(link=url, title=title)
    await state.set_state(ResourceState.waiting_for_type)
    await message.answer(
        with_action_label("add", f"[{index + 1}/{total}] {title}\n\nВыберите тип:"),
        reply_markup=create_kb_type(list(ResourceType), get_callback_data),
    )


async def _start_next_url_from_callback(
    callback,
    state: FSMContext,
    resource_db: ResourceDB,
    logger: logging.Logger,
    index: int = 0,
):
    data = await state.get_data()
    urls = data["import_urls"]
    total = len(urls)

    if index >= total:
        results = data["import_results"]
        msg = f"Импортировано {results['count']} из {total} ссылок."
        if results["errors"]:
            msg += "\n\nОшибки:\n" + "\n".join(results["errors"][-10:])
        await state.clear()
        await callback.message.edit_text(msg, disable_web_page_preview=True)
        return

    url = urls[index]
    try:
        info = ResourceService.get_info_for_url(url, YOUTUBE_API_KEY, PROXY_URL)
        title = info["title"]
    except Exception:
        results = data["import_results"]
        results["errors"].append(f"Ошибка получения: {url}")
        await state.update_data(import_index=index + 1, import_results=results)
        await _start_next_url_from_callback(
            callback, state, resource_db, logger, index + 1
        )
        return

    await state.update_data(link=url, title=title, import_index=index)
    await state.set_state(ResourceState.waiting_for_type)
    await callback.message.edit_text(
        with_action_label("add", f"[{index + 1}/{total}] {title}\n\nВыберите тип:"),
        reply_markup=create_kb_type(list(ResourceType), get_callback_data),
    )
