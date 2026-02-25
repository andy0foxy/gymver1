from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import setup_routers
from app.bot.middlewares import BusinessContextMiddleware
from app.bot.scheduler import get_reminder_scheduler
from app.core import get_settings
from app.core.logging import configure_logging


async def _run_bot() -> None:
    settings = get_settings()
    logger = configure_logging()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(BusinessContextMiddleware())
    dp.callback_query.middleware(BusinessContextMiddleware())
    dp.include_router(setup_routers())

    logger.info("Starting bot in %s environment", settings.environment)

    # Initialize scheduler for reminders
    scheduler = get_reminder_scheduler(bot)
    await scheduler.start()

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # Graceful shutdown
        await scheduler.stop()
        await bot.session.close()


def main() -> None:
    asyncio.run(_run_bot())


if __name__ == "__main__":
    main()

