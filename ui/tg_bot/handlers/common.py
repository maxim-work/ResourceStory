from aiogram import F, Router, types
from aiogram.filters.command import Command, CommandStart

from config import USER_COMMANDS
from ui.tg_bot.keyboards.reply import get_user_start_keyboard

common_router = Router()


@common_router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    if message.from_user is None:
        return
    user = message.from_user
    name = user.full_name or user.first_name if user else "Гость"
    await message.answer(f"Привет, {name}!", reply_markup=get_user_start_keyboard())


@common_router.message(Command("help"))
@common_router.message(F.text == "Помощь")
async def cmd_help(message: types.Message) -> None:
    await message.answer(f"Вот наши команды: {USER_COMMANDS}!")


@common_router.message(~F.text.startswith("/"))
async def unknown_text(message: types.Message) -> None:
    await message.answer("Я пока не умею разговаривать на свободные темы...")


@common_router.message(F.text)
async def unknown_command(message: types.Message) -> None:
    await message.answer("Не знаю такой команды... Введите /help для списка команд.")
