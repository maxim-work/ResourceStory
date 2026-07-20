import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters.command import CommandStart

from config import BOT_TOKEN, PROXY_URL

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

router = Router()


@router.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    user = message.from_user
    name = user.full_name or user.first_name if user else "Гость"
    await message.answer(f"Привет, {name}!")


@router.message(F.text)
async def unknown_command(message: types.Message) -> None:
    await message.answer("Не знаю такой команды...")


async def main():
    bot = None
    try:
        if not BOT_TOKEN:
            raise ValueError("BOT_TOKEN не указан!")

        if PROXY_URL:
            session = AiohttpSession(proxy=PROXY_URL)
            bot = Bot(
                token=BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
                session=session,
            )
            logging.info(f"Бот запущен через прокси: {PROXY_URL}")
        else:
            bot = Bot(
                token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            logging.info("Бот запущен без прокси")

        dp = Dispatcher()
        dp.include_router(router)
        logging.info("Роутеры подключены")

        logging.info("Запуск поллинга...")
        await dp.start_polling(bot)

    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logging.critical(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        if bot is not None:
            await bot.session.close()
            logging.info("Сессия закрыта")


def start_bot():
    asyncio.run(main())


if __name__ == "__main__":
    start_bot()
