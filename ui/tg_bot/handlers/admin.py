from aiogram import F, Router, types
from aiogram.filters.command import Command, CommandStart

from config import ADMIN_COMMANDS
from ui.tg_bot.keyboards.reply import get_admin_start_keyboard
from ui.tg_bot.middlewares.admin import AdminMiddleware

admin_router = Router()
admin_router.message.middleware(AdminMiddleware())
admin_router.callback_query.middleware(AdminMiddleware())


@admin_router.message(CommandStart())
async def cmd_start(message: types.Message):
    if message.from_user is None:
        return
    user = message.from_user
    name = user.full_name or user.first_name if user else ""
    await message.answer(
        f"Привет админ {name}", reply_markup=get_admin_start_keyboard()
    )


@admin_router.message(Command("help"))
@admin_router.message(F.text == "Помощь")
async def cmd_help(message: types.Message) -> None:
    await message.answer(f"Вот наши команды: {ADMIN_COMMANDS}!")
