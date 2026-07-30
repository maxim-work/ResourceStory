from aiogram.filters.callback_data import CallbackData


class ResourceCallback(CallbackData, prefix="res"):
    action: str
    resource_id: int | None = None
    page: int | None = None
