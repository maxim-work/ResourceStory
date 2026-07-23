import logging
from typing import Any

from aiogram.types import CallbackQuery

from core.exceptions import (
    APIResponseError,
    InvalidParamError,
    InvalidRatingError,
    InvalidUrlParamError,
    NetworkError,
    ProxyRequestError,
    ResourceNotFoundError,
)

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
    callback: CallbackQuery,
    error: Exception,
    context: dict[str, Any],
    logger: logging.Logger,
    with_action_label,
    action: str = "error_add",
) -> bool:
    if type(error) in USER_ERRORS:
        handler = USER_ERRORS.get(type(error))
        msg = handler(error) if callable(handler) else handler
        await callback.message.edit_text(with_action_label(action, msg))
        return True

    if isinstance(error, SYSTEM_ERRORS):
        logger.error(
            f"Ошибка при создании ресурса: {type(error).__name__}",
            exc_info=True,
            extra=context,
        )
        await callback.message.edit_text(
            with_action_label(action, "Ошибка сервиса. Мы уже работаем над этим.")
        )
        return True

    return False
