import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class LoggerMiddleware(BaseMiddleware):
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["logger"] = self.logger
        return await handler(event, data)
