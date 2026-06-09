import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from loguru import logger

from config import BOT_TOKEN
from db import close_db, init_db
from handlers import router
from utils import setup_logging


async def main() -> None:
    setup_logging()
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set — put it in .env")

    await init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    me = await bot.get_me()
    try:
        await bot.set_my_commands([
            BotCommand(command="new", description="Create a post"),
            BotCommand(command="list", description="My saved posts"),
            BotCommand(command="cancel", description="Cancel the current action"),
        ])
    except Exception as e:  # noqa: BLE001 — cosmetic, must not block startup
        logger.warning(f"set_my_commands failed: {e}")

    logger.info(f"Bot @{me.username} (id={me.id}) started")
    try:
        # resolve_used_update_types() makes sure my_chat_member updates are delivered
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await close_db()
        logger.info("Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
