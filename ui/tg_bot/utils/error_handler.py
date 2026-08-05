import logging
from typing import Any, Optional

from aiogram.types import CallbackQuery, Message

from core.exceptions import (
    APIResponseError,
    InvalidParamError,
    InvalidRatingError,
    InvalidUrlParamError,
    NetworkError,
    ProxyRequestError,
    ResourceNotFoundError,
)
from ui.tg_bot.utils.message import get_editable_message

USER_ERRORS = {
    InvalidUrlParamError: "Некорректная ссылка.",
    InvalidParamError: lambda e: f"Некорректный параметр: {e.param}",
    InvalidRatingError: "Некорректный рейтинг.",
}

SYSTEM_ERRORS = (
    ProxyRequestError,
    APIResponseError,
    NetworkError,
    ResourceNotFoundError,
)


async def handle_resource_error(
    error: Exception,
    context: dict[str, Any],
    logger: logging.Logger,
    with_action_label,
    action: str = "error_add",
    callback: Optional[CallbackQuery] = None,
    message: Optional[Message] = None,
) -> bool:
    if message is None and callback is not None:
        message = get_editable_message(callback)
    if message is None:
        return False

    if type(error) in USER_ERRORS:
        handler = USER_ERRORS.get(type(error))
        msg = handler(error) if callable(handler) else handler
        await message.edit_text(with_action_label(action, msg))
        return True

    if isinstance(error, SYSTEM_ERRORS):
        logger.error(
            f"Ошибка при создании ресурса: {type(error).__name__}",
            exc_info=True,
            extra=context,
        )
        await message.edit_text(
            with_action_label(action, "Ошибка сервиса. Мы уже работаем над этим.")
        )
        return True

    logger.error(
        f"Неизвестная ошибка: {type(error).__name__}",
        exc_info=True,
        extra=context,
    )
    await message.edit_text(
        with_action_label(action, "Ошибка сервиса. Мы уже работаем над этим.")
    )
    return True
