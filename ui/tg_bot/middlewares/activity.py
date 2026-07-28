from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, Update


class ActivityMiddleware(BaseMiddleware):
    def __init__(self, user_db, resource_db):
        self.user_db = user_db
        self.resource_db = resource_db
        super().__init__()

    async def __call__(self, handler, event, data):
        if not isinstance(event, Update):
            return await handler(event, data)
        real_event = self._get_real_event(event)
        data["resource_db"] = self.resource_db
        if isinstance(real_event, (Message, CallbackQuery)) and real_event.from_user:
            self.user_db.update_last_active(real_event.from_user.id)
        return await handler(event, data)

    @staticmethod
    def _get_real_event(event: Update):
        return event.message or event.callback_query
