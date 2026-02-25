from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.db import get_supabase_client
from app.db.models import Business, SubscriptionStatus


router = Router(name="report")


@router.message(Command("report"))
async def cmd_report(message: Message, business: Business | None = None) -> None:
    """
    Show a simple subscriptions report for the current business.
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    supabase = get_supabase_client()
    stats = await supabase.get_subscription_stats_for_business(business.id)

    total = sum(stats.values())
    active = stats.get(SubscriptionStatus.ACTIVE, 0)
    expired = stats.get(SubscriptionStatus.EXPIRED, 0)
    cancelled = stats.get(SubscriptionStatus.CANCELLED, 0)
    frozen = stats.get(SubscriptionStatus.FROZEN, 0)

    lines: list[str] = [
        "📊 Статистика по абонементам:",
        "",
        f"Всего абонементов: <b>{total}</b>",
        f"Активные: <b>{active}</b>",
        f"Просроченные: <b>{expired}</b>",
    ]

    if cancelled:
        lines.append(f"Отменённые: <b>{cancelled}</b>")
    if frozen:
        lines.append(f"Замороженные: <b>{frozen}</b>")

    if total == 0:
        lines.append("")
        lines.append("Пока нет ни одного абонемента.")

    await message.answer("\n".join(lines))

