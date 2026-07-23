import asyncio
from typing import Optional

from aiogram import Bot
from aiogram.utils.markdown import hbold


async def auto_delete(bot: Bot, chat_id: int, message_id: int, delay: int = 3) -> None:
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass


async def safe_delete_many(bot: Bot, chat_id: int, *message_ids: int):
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass


ACTION_TEMPLATES = {
    "add": ("➕", "Добавление ресурса"),
    "edit": ("✏️", "Редактирование ресурса"),
    "delete": ("🗑", "Удаление ресурса"),
    "error_add": ("⚠️", "Ошибка при добавлении ресурса"),
    "error_edit": ("⚠️", "Ошибка при редактировании ресурса"),
    "error_delete": ("⚠️", "Ошибка при удалении ресурса"),
    "error_fetch": ("⚠️", "Ошибка при получении ресурса"),
    "error_not_found": ("🔍", "Ресурс не найден"),
    "error_validate": ("❌", "Ошибка валидации"),
}


def with_action_label(action: str, text: str, title: Optional[str] = None) -> str:
    emoji, action_name = ACTION_TEMPLATES.get(action, ("⚙️", str(action)))

    label = f"{emoji} {action_name}"
    if title:
        label += f" «{title}»"

    return f"{hbold(label)}\n\n{text}"
