from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

from app.core import get_settings
from app.db import get_supabase_client
from app.db.models import SubscriptionStatus

logger = logging.getLogger(__name__)


class SubscriptionReminderScheduler:
    """
    APScheduler manager for subscription reminders.
    Sends periodic reminders about expiring subscriptions.
    """

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.scheduler: AsyncIOScheduler | None = None

    async def start(self) -> None:
        """
        Initialize and start the scheduler.
        Runs reminder check every hour to respect individual user settings.
        """
        self.scheduler = AsyncIOScheduler()

        # Run reminder check every hour so we can respect per-user time settings
        self.scheduler.add_job(
            self._send_hourly_reminders,
            CronTrigger(minute=0),  # Every hour at :00
            id="hourly_reminders",
            name="Hourly Subscription Reminders",
        )

        self.scheduler.start()
        logger.info("Subscription reminder scheduler started")

    async def stop(self) -> None:
        """
        Stop the scheduler gracefully.
        """
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("Subscription reminder scheduler stopped")

    async def _send_hourly_reminders(self) -> None:
        """
        Check all owners for reminders due at this hour.
        Respects each owner's individual reminder_hour and reminder_days_before settings.
        """
        settings = get_settings()
        current_hour = datetime.now().hour

        if settings.is_debug:
            logger.debug(f"Running hourly reminder check (hour={current_hour})")

        supabase = get_supabase_client()

        try:
            # Fetch all owners - note: Supabase schema should support this query
            # This example assumes a simple table scan is possible
            response = await supabase._rest.get(
                "/owner_profiles",
                params={
                    "select": "*",
                    "reminder_enabled": "eq.true",  # Only active reminders
                },
            )
            
            if response.status_code >= 400:
                logger.warning(f"Failed to fetch owner profiles: {response.text}")
                return

            owners = response.json()
            
            for owner_row in owners:
                # Check if this owner's reminder hour matches current hour
                reminder_hour = owner_row.get("reminder_hour", 10)
                if reminder_hour != current_hour:
                    continue  # Not this owner's reminder time
                
                telegram_user_id = owner_row.get("telegram_user_id")
                days_before = owner_row.get("reminder_days_before", 7)
                
                if not telegram_user_id:
                    continue
                
                # Get owner's business
                try:
                    owner_data = await supabase.get_owner_by_telegram(telegram_user_id)
                    if not owner_data:
                        continue
                    owner, business = owner_data
                    
                    # Send reminder for this business
                    await self.send_reminder_for_business(
                        business_id=business.id,
                        owner_telegram_id=telegram_user_id,
                        days_until=days_before,
                    )
                except Exception as exc:
                    logger.error(f"Error processing owner {telegram_user_id}: {exc}")
                    continue

            logger.info("Hourly reminder check completed")

        except Exception as exc:
            logger.exception("Error during hourly reminder check: %s", exc)

    async def send_reminder_for_business(
        self,
        business_id: str,
        owner_telegram_id: int,
        days_until: int = 3,
    ) -> None:
        """
        Send a reminder about subscriptions expiring in exactly days_until days.
        Only sends if reminder hasn't been sent yet for that subscription.
        Marks reminder as sent after sending message.
        """
        supabase = get_supabase_client()

        try:
            # Get all active subscriptions
            subs = await supabase.list_subscriptions_for_business(business_id)
            today = date.today()
            
            # Filter to only subscriptions expiring in exactly days_until days
            # and without a reminder already sent
            expiring_today = [
                s for s in subs
                if s.status == "active"
                and (s.end_date - today).days == days_until
                and s.reminder_sent_at is None
            ]

            if not expiring_today:
                # Silent - don't send messages for "no reminders today"
                logger.debug(f"No reminders due for business {business_id}")
                return

            # Get client info for better formatting
            clients = await supabase.list_clients_for_business(business_id)
            client_map = {c.id: c.full_name for c in clients}

            # Prepare message
            lines = [
                f"⏰ <b>Напоминание об истекающих абонементах</b>",
                f"Истекают через <b>{days_until} дней</b>:",
                "",
            ]

            for sub in expiring_today:
                client_name = client_map.get(sub.client_id, "Unknown")
                lines.append(
                    f"  • {client_name}: {sub.end_date.strftime('%d.%m.%Y')} "
                    f"({sub.amount} {sub.currency})"
                )

            lines.append("")
            lines.append("💳 Используй меню абонементов для управления.")

            # Send the reminder message
            await self.bot.send_message(
                chat_id=owner_telegram_id,
                text="\n".join(lines),
                parse_mode="HTML",
            )

            # Mark each subscription's reminder as sent
            for sub in expiring_today:
                try:
                    await supabase.mark_reminder_sent(sub.id)
                    logger.debug(f"Marked reminder sent for subscription {sub.id}")
                except Exception as exc:
                    logger.error(f"Failed to mark reminder for {sub.id}: {exc}")

        except Exception as exc:
            logger.exception("Error sending reminder: %s", exc)



# Global scheduler instance
_scheduler: SubscriptionReminderScheduler | None = None


def get_reminder_scheduler(bot: Bot | None = None) -> SubscriptionReminderScheduler:
    """
    Get or create the global reminder scheduler.
    """
    global _scheduler
    if _scheduler is None:
        if bot is None:
            raise RuntimeError("Bot instance required to initialize scheduler")
        _scheduler = SubscriptionReminderScheduler(bot)
    return _scheduler
