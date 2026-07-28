from datetime import datetime, timedelta

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, Update

from config import USER_UPDATE_INTERVAL_HOURS


class UserUpdateMiddleware(BaseMiddleware):
    def __init__(self, user_db, user_service):
        self.user_db = user_db
        self.user_service = user_service
        self.dict_update: dict[int, datetime] = {}
        super().__init__()

    async def __call__(self, handler, event, data):
        if not isinstance(event, Update):
            return await handler(event, data)
        real_event = self._get_real_event(event)
        if isinstance(real_event, (Message, CallbackQuery)) and real_event.from_user:
            tg_id = real_event.from_user.id
            last_update = self.dict_update.get(tg_id)

            if last_update is None or datetime.now() > last_update + timedelta(
                hours=USER_UPDATE_INTERVAL_HOURS
            ):
                user = self.user_service.create_user(
                    real_event.from_user.id,
                    real_event.from_user.first_name,
                    real_event.from_user.username,
                    real_event.from_user.last_name,
                )
                self.user_db.update(user)
                self.dict_update[tg_id] = datetime.now()

        return await handler(event, data)

    @staticmethod
    def _get_real_event(event: Update):
        return event.message or event.callback_query
