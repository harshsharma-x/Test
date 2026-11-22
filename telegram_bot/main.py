"""Main entry point for aiogram 3.x Telegram Shopping Bot."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env file
ENV_PATH = PROJECT_ROOT / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from backend.database.connection import init_db
from telegram_bot.handlers import accounts, auth, checkout, shopping, start

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("zepto_bot")


async def main():
    token = os.environ.get("BOT_TOKEN", "9164672350:AAEx6ndysyhXx6a2GPl23ZerHKVABh2qkOs")
    if not token:
        logger.warning("BOT_TOKEN not configured!")
        return

    # Initialize database
    init_db()

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Include routers
    dp.include_router(start.router)
    dp.include_router(auth.router)
    dp.include_router(accounts.router)
    dp.include_router(shopping.router)
    dp.include_router(checkout.router)

    logger.info("Zepto Telegram Bot starting polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
