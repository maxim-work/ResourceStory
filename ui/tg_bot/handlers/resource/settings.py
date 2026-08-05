import os

from aiogram import Bot, F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.markdown import hbold

from data.service_db import ResourceDB
from data_io.export_data import write_data_file, write_urls_file
from ui.tg_bot.callbacks.resource import SettingsCallback
from ui.tg_bot.keyboards.resource import (
    create_import_data_menu,
    create_import_urls_menu,
    create_settings_menu,
)
from ui.tg_bot.states.resource import ResourceState
from ui.tg_bot.utils.message import get_editable_message

settings_router = Router()


@settings_router.message(Command("settings"))
@settings_router.message(F.text == "Ещё")
async def cmd_settings(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user is None:
        return

    await message.answer(
        f"{hbold('Дополнительные действия')}",
        reply_markup=create_settings_menu(),
    )


@settings_router.callback_query(SettingsCallback.filter())
async def settings_callback(
    callback: CallbackQuery,
    callback_data: SettingsCallback,
    state: FSMContext,
    resource_db: ResourceDB,
    bot: Bot,
):
    message = get_editable_message(callback)
    if message is None:
        return

    tg_id = callback.from_user.id
    action = callback_data.action

    if action == "export_urls":
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

    elif action == "export_data":
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

    elif action == "import_urls_menu":
        await message.edit_text(
            "Импорт ссылок:\n\n"
            "• Быстрый — все ссылки сохранятся с типом «Другое» и форматом по умолчанию.\n"
            "• Детальный — для каждой ссылки можно выбрать тип и формат.",
            reply_markup=create_import_urls_menu(),
        )

    elif action == "import_data_menu":
        await message.edit_text(
            "Импорт данных:\n\n"
            "• Быстрый — загрузите JSON-файл, ресурсы добавятся без подтверждения.\n"
            "• Детальный — для каждого ресурса из файла можно изменить данные перед сохранением.",
            reply_markup=create_import_data_menu(),
        )

    elif action == "import_urls_fast":
        await state.set_state(ResourceState.waiting_for_import_urls)
        await state.update_data(import_mode="fast", import_type="urls")
        await message.edit_text(
            "Пришлите список ссылок (по одной на строку) или файл.txt:"
        )

    elif action == "import_urls_detailed":
        await state.set_state(ResourceState.waiting_for_import_urls)
        await state.update_data(import_mode="detailed", import_type="urls")
        await message.edit_text(
            "Пришлите список ссылок (по одной на строку) или файл.txt:"
        )

    elif action == "import_data_fast":
        await state.set_state(ResourceState.waiting_for_import_data)
        await state.update_data(import_mode="fast", import_type="data")
        await message.edit_text("Пришлите JSON-файл с данными:")

    elif action == "import_data_detailed":
        await state.set_state(ResourceState.waiting_for_import_data)
        await state.update_data(import_mode="detailed", import_type="data")
        await message.edit_text("Пришлите JSON-файл с данными:")
