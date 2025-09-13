from aiogram import Bot
import asyncio
from app.utils.config import settings
from app.utils.logging import get_logger
from .dispatcher import setup_dispatcher

logger = get_logger(__name__)
bot: Bot | None = None

async def start_bot_polling() -> None:
    global bot
    logger.info("Starting Telegram bot (polling)...")
    bot = Bot(token=settings.TELEGRAM.TELEGRAM_BOT_TOKEN)
    dp = setup_dispatcher()
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
