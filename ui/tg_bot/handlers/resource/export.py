import os

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from data.service_db import ResourceDB
from data_io.export_data import write_data_file, write_urls_file
from ui.tg_bot.callbacks.resource import SettingsCallback
from ui.tg_bot.utils.message import get_editable_message

export_router = Router()


@export_router.callback_query(SettingsCallback.filter())
async def export_urls_callback(
    callback: CallbackQuery,
    callback_data: SettingsCallback,
    state: FSMContext,
    resource_db: ResourceDB,
):
    if callback_data.action != "export_urls":
        return

    message = get_editable_message(callback)
    if message is None:
        return

    tg_id = callback.from_user.id
    urls = resource_db.export_urls(tg_id)

    if not urls:
        await callback.answer("Нет ресурсов для экспорта", show_alert=True)
        return

    filepath, count = write_urls_file(urls, f"urls_{tg_id}.txt")

    await message.answer_document(
        document=types.FSInputFile(filepath, filename="urls_export.txt"),
        caption=f"Экспортировано {count} ссылок",
    )
    os.remove(filepath)
    await callback.answer()


@export_router.callback_query(SettingsCallback.filter())
async def export_data_callback(
    callback: CallbackQuery,
    callback_data: SettingsCallback,
    state: FSMContext,
    resource_db: ResourceDB,
):
    if callback_data.action != "export_data":
        return

    message = get_editable_message(callback)
    if message is None:
        return

    tg_id = callback.from_user.id
    resources = resource_db.export_data(tg_id)

    if not resources:
        await callback.answer("Нет ресурсов для экспорта", show_alert=True)
        return

    filepath, count = write_data_file(resources, f"data_{tg_id}.json")

    await message.answer_document(
        document=types.FSInputFile(filepath, filename="data_export.json"),
        caption=f"Экспортировано {count} ресурсов",
    )
    os.remove(filepath)
    await callback.answer()
