from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.core.logging import configure_logging
from app.db import get_supabase_client
from app.db.models import Business, SubscriptionStatus

router = Router(name="client_details")
logger = configure_logging()


@router.message(Command("client_info"))
async def cmd_client_info(message: Message, business: Business | None = None) -> None:
    """
    View detailed info about a specific client and their subscriptions.
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    # Ask user which client
    supabase = get_supabase_client()
    clients = await supabase.list_clients_for_business(business.id)

    if not clients:
        await message.answer("Нет ни одного клиента.")
        return

    # For simplicity in this MVP, we'll show first 10 clients as a list
    lines = ["Выбери клиента (отправь номер):\n"]
    for idx, client in enumerate(clients[:20], start=1):
        lines.append(f"{idx}. {client.full_name} ({client.phone})")

    if len(clients) > 20:
        lines.append(f"\n... ещё {len(clients) - 20} клиентов")

    lines.append("\nОтправь номер или поиск по имени: /search <имя>")

    await message.answer("\n".join(lines))


@router.message(Command("search"))
async def cmd_search_client(message: Message, business: Business | None = None) -> None:
    """
    Search client by name or phone.
    Usage: /search Ivanov or /search 79990000000
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    # Parse command: /search <query>
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Используй: /search <имя или телефон>")
        return

    query = parts[1].strip()
    supabase = get_supabase_client()

    # Try both name and phone search
    by_name = await supabase.search_clients_by_name(business.id, query)
    by_phone = await supabase.search_clients_by_phone(business.id, query)

    # Combine and dedupe
    seen = {c.id for c in by_name}
    combined = by_name + [c for c in by_phone if c.id not in seen]

    if not combined:
        await message.answer(f"Клиентов с \"<b>{query}</b>\" не найденα.")
        return

    lines = [f"Найденные клиенты:\n"]
    for idx, client in enumerate(combined, start=1):
        lines.append(f"{idx}. {client.full_name} — {client.phone}")

    lines.append("\nОтправь номер для просмотра деталей.")

    await message.answer("\n".join(lines))


@router.message(Command("view_client"))
async def cmd_view_client(message: Message, business: Business | None = None) -> None:
    """
    View detailed client subscription info.
    Usage: /view_client <client_id> or just send client number from /client_info
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    # Extract client ID from command arguments
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Используй: /view_client <номер клиента>")
        return

    try:
        client_number = int(parts[1])
    except ValueError:
        await message.answer("Отправь номер клиента (число).")
        return

    # Get all clients to map number to ID
    supabase = get_supabase_client()
    all_clients = await supabase.list_clients_for_business(business.id)

    if client_number < 1 or client_number > len(all_clients):
        await message.answer(f"Неверный номер. Всього {len(all_clients)} клиентов.")
        return

    selected_client = all_clients[client_number - 1]

    try:
        client, subs = await supabase.get_client_with_subscriptions(selected_client.id)
    except Exception as exc:
        logger.exception("Error getting client details: %s", exc)
        await message.answer("❌ Ошибка при загрузке деталей клиента.")
        return

    # Format output
    lines = [
        f"<b>👤 {client.full_name}</b>",
        f"📞 {client.phone}",
        f"📅 Добавлен: {client.created_at.date()}",
        "",
    ]

    if not subs:
        lines.append("Абонементов: <b>нет</b>")
    else:
        lines.append(f"<b>Абонементы ({len(subs)})</b>")
        lines.append("")

        # Group by status
        by_status = {}
        for sub in subs:
            if sub.status not in by_status:
                by_status[sub.status] = []
            by_status[sub.status].append(sub)

        for status in [
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.EXPIRED,
            SubscriptionStatus.FROZEN,
            SubscriptionStatus.CANCELLED,
        ]:
            subs_for_status = by_status.get(status, [])
            if not subs_for_status:
                continue

            if status == SubscriptionStatus.ACTIVE:
                lines.append("<b>✅ Активные</b>")
            elif status == SubscriptionStatus.EXPIRED:
                lines.append("<b>❌ Истекшие</b>")
            elif status == SubscriptionStatus.FROZEN:
                lines.append("<b>🧊 Заморозленные</b>")
            else:
                lines.append(f"<b>{status.value.upper()}</b>")

            for sub in subs_for_status:
                lines.append(
                    f"  • {sub.amount} {sub.currency} "
                    f"(с {sub.start_date} по {sub.end_date})"
                )

            lines.append("")

    await message.answer("\n".join(lines))
