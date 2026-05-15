import asyncio
import logging
import os

from aiogram import Bot, Dispatcher

from handlers.work import router


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    token = os.getenv("BOT_TOKEN", "8629709773:AAHy0eWPrwh9voQ-I4Ez1JBOYHcnuPVVi8w")
    if token == "TOKEN":
        logging.warning("BOT_TOKEN not set. Replace TOKEN or export BOT_TOKEN before запуск.")

    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
