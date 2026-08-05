from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, Update

from config import ADMIN_IDS
from ui.tg_bot.middlewares.utils import get_real_event


class AdminMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()

    async def __call__(self, handler, event, data):
        if not isinstance(event, Update):
            return await handler(event, data)
        real_event = get_real_event(event)
        if isinstance(real_event, (Message, CallbackQuery)) and real_event.from_user:
            if real_event.from_user.id not in ADMIN_IDS:
                if isinstance(real_event, CallbackQuery):
                    await real_event.answer(
                        "У вас нет доступа к этой функции", show_alert=True
                    )
                elif isinstance(real_event, Message):
                    await real_event.answer("У вас нет доступа к этой функции")
        return await handler(event, data)
