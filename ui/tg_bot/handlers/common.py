from aiogram import F, Router, types
from aiogram.filters.command import Command, CommandStart

common_router = Router()

commands_text = "/start — описание\n/help — описание"


@common_router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    user = message.from_user
    name = user.full_name or user.first_name if user else "Гость"
    await message.answer(f"Привет, {name}!")


@common_router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    await message.answer(f"Вот наши команды: {commands_text}!")


@common_router.message(~F.text.startswith("/"))
async def unknown_text(message: types.Message) -> None:
    await message.answer("Я пока не умеюразговаривать на свободные темы...")


@common_router.message(F.text)
async def unknown_command(message: types.Message) -> None:
    await message.answer("Не знаю такой команды... Введите /help для списка команд.")
