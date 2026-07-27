from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message


class ActivityMiddleware(BaseMiddleware):
    def __init__(self, user_db, resource_db):
        self.user_db = user_db
        self.resource_db = resource_db
        super().__init__()

    async def __call__(self, handler, event, data):
        data["resource_db"] = self.resource_db
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            self.user_db.update_last_active(event.from_user.id)
        return await handler(event, data)
