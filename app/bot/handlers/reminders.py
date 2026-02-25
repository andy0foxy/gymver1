from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.scheduler import get_reminder_scheduler
from app.core.logging import configure_logging
from app.db.models import Business

router = Router(name="reminders")
logger = configure_logging()


@router.message(Command("remind"))
async def cmd_remind(
    message: Message,
    business: Business | None = None,
) -> None:
    """
    Send immediate reminder about expiring subscriptions.
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    if message.from_user is None:
        await message.answer("Ошибка: не удалось определить вас.")
        return

    try:
        scheduler = get_reminder_scheduler()
        await scheduler.send_reminder_for_business(
            business_id=business.id,
            owner_telegram_id=message.from_user.id,
            days_until=7,
        )
    except Exception as exc:
        logger.exception("Error sending reminder: %s", exc)
        await message.answer("❌ Ошибка при отправке напоминания.")


@router.message(Command("remind3"))
async def cmd_remind_3_days(
    message: Message,
    business: Business | None = None,
) -> None:
    """
    Send reminder about subscriptions expiring in 3 days.
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    if message.from_user is None:
        await message.answer("Ошибка: не удалось определить вас.")
        return

    try:
        scheduler = get_reminder_scheduler()
        await scheduler.send_reminder_for_business(
            business_id=business.id,
            owner_telegram_id=message.from_user.id,
            days_until=3,
        )
    except Exception as exc:
        logger.exception("Error sending 3-day reminder: %s", exc)
        await message.answer("❌ Ошибка при отправке напоминания.")
