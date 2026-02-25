from __future__ import annotations

from datetime import date, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.core.logging import configure_logging
from app.db import get_supabase_client
from app.db.models import Business, SubscriptionStatus

router = Router(name="reports")
logger = configure_logging()


@router.message(Command("report"))
async def cmd_report(message: Message, business: Business | None = None) -> None:
    """
    Show business analytics and statistics.
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    supabase = get_supabase_client()

    try:
        # Get subscriptions and clients
        subs = await supabase.list_subscriptions_for_business(business.id)
        clients = await supabase.list_clients_for_business(business.id)
        stats = await supabase.get_subscription_stats_for_business(business.id)
        revenue = await supabase.get_subscription_revenue_stats(business.id)

        lines = [
            f"<b>📊 Отчёт: {business.name}</b>",
            "",
            "<b>👥 Клиенты</b>",
            f"  Всего: <b>{len(clients)}</b>",
        ]

        # Count unique active clients
        active_client_ids = set()
        for sub in subs:
            if sub.status == SubscriptionStatus.ACTIVE:
                active_client_ids.add(sub.client_id)
        lines.append(f"  С активными абонементами: <b>{len(active_client_ids)}</b>")
        lines.append("")

        # Subscription stats
        lines.append("<b>💳 Абонементы</b>")
        lines.append(f"  Активно: <b>{stats.get(SubscriptionStatus.ACTIVE, 0)}</b>")
        lines.append(f"  Истекло: <b>{stats.get(SubscriptionStatus.EXPIRED, 0)}</b>")
        lines.append(f"  Заморозлено: <b>{stats.get(SubscriptionStatus.FROZEN, 0)}</b>")
        lines.append(f"  Отменено: <b>{stats.get(SubscriptionStatus.CANCELLED, 0)}</b>")
        lines.append(f"  Всего: <b>{len(subs)}</b>")
        lines.append("")

        # Revenue stats
        lines.append("<b>💰 Доход</b>")
        lines.append(f"  Общий: <b>{revenue['total']} РУБ</b>")
        lines.append(f"  Этот месяц: <b>{revenue['this_month']} РУБ</b>")
        lines.append(f"  Средний в месяц: <b>{revenue['avg_monthly']} РУБ</b>")
        lines.append("")

        # Expiring subscriptions
        today = date.today()
        expiring_7 = await supabase.list_expiring_subscriptions(business.id, days_until=7)
        expiring_30 = await supabase.list_expiring_subscriptions(business.id, days_until=30)

        lines.append("<b>⏰ Сроки истечения</b>")
        lines.append(f"  В течение 7 дней: <b>{len(expiring_7)}</b>")
        lines.append(f"  В течение 30 дней: <b>{len(expiring_30)}</b>")

        if expiring_7:
            lines.append("")
            lines.append("  <b>Истекают в течение недели:</b>")
            client_map = {c.id: c.full_name for c in clients}
            for sub in expiring_7:
                client_name = client_map.get(sub.client_id, "Unknown")
                days_left = (sub.end_date - today).days
                lines.append(f"    • {client_name}: {days_left} дней")

        await message.answer("\n".join(lines))

    except Exception as exc:
        logger.exception("Error generating report: %s", exc)
        await message.answer("❌ Ошибка при создании отчёта.")


@router.message(Command("revenue"))
async def cmd_revenue(message: Message, business: Business | None = None) -> None:
    """
    Show detailed revenue information.
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    supabase = get_supabase_client()

    try:
        revenue = await supabase.get_subscription_revenue_stats(business.id)
        payments = await supabase.list_payments_for_business(business.id)

        lines = [
            f"<b>💰 Доход {business.name}</b>",
            "",
            f"Всего получено: <b>{revenue['total']} РУБ</b>",
            f"Этот месяц: <b>{revenue['this_month']} РУБ</b>",
            f"Среднее в месяц: <b>{revenue['avg_monthly']} РУБ</b>",
            "",
        ]

        if not payments:
            lines.append("Платежей не записано.")
        else:
            lines.append(f"<b>Последние платежи ({min(10, len(payments))})</b>")
            lines.append("")

            for payment in payments[:10]:
                lines.append(
                    f"  • {payment.amount} {payment.currency} ({payment.payment_date})"
                )
                if payment.notes:
                    lines.append(f"    Примечание: {payment.notes}")

            if len(payments) > 10:
                lines.append(f"\n... всего {len(payments)} платежей")

        await message.answer("\n".join(lines))

    except Exception as exc:
        logger.exception("Error generating revenue report: %s", exc)
        await message.answer("❌ Ошибка при загрузке доходов.")


@router.message(Command("summary"))
async def cmd_summary(message: Message, business: Business | None = None) -> None:
    """
    Show quick summary/dashboard.
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    supabase = get_supabase_client()

    try:
        subs = await supabase.list_subscriptions_for_business(business.id)
        stats = await supabase.get_subscription_stats_for_business(business.id)
        revenue = await supabase.get_subscription_revenue_stats(business.id)

        # Quick metrics
        active = stats.get(SubscriptionStatus.ACTIVE, 0)
        expired = stats.get(SubscriptionStatus.EXPIRED, 0)
        total = len(subs)
        percent_active = int((active / total * 100) if total > 0 else 0)

        lines = [
            f"<b>📈 {business.name}</b>",
            "",
            f"💳 Абонементы: <b>{active}/{total}</b> ({percent_active}% активно)",
            f"❌ Истекло: <b>{expired}</b>",
            f"💰 Доход месяца: <b>{revenue['this_month']} РУБ</b>",
            "",
            "Подробнее: /report",
        ]

        await message.answer("\n".join(lines))

    except Exception as exc:
        logger.exception("Error generating summary: %s", exc)
        await message.answer("❌ Ошибка при создании краткой статистики.")
