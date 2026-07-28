from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message


class RegistrationMiddleware(BaseMiddleware):
    def __init__(self, user_db, user_service):
        self.user_db = user_db
        self.user_service = user_service
        super().__init__()

    async def __call__(self, handler, event, data):
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            if self.user_db.get(event.from_user.id) is None:
                user = self.user_service.create_user(
                    tg_id=event.from_user.id,
                    first_name=event.from_user.first_name,
                    username=event.from_user.username,
                    last_name=event.from_user.last_name,
                )
                self.user_db.insert(user)
        return await handler(event, data)
