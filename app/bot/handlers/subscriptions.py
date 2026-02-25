from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.core.logging import configure_logging
from app.db import get_supabase_client
from app.db.models import Business, SubscriptionStatus

router = Router(name="subscriptions")
logger = configure_logging()


class AddSubscriptionStates(StatesGroup):
    waiting_for_client = State()
    waiting_for_amount = State()
    waiting_for_duration = State()


@router.message(Command("add_subscription"))
async def cmd_add_subscription(
    message: Message,
    state: FSMContext,
    business: Business | None = None,
) -> None:
    """
    Start add-subscription dialog: ask which client.
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    supabase = get_supabase_client()
    clients = await supabase.list_clients_for_business(business.id)

    if not clients:
        await message.answer("Нет ни одного клиента. Сначала добавь клиента /add_client.")
        return

    # Store clients in state for later reference
    await state.update_data(clients=clients, business_id=business.id)
    await state.set_state(AddSubscriptionStates.waiting_for_client)

    lines = ["Выбери клиента (отправь номер):\n"]
    for idx, client in enumerate(clients, start=1):
        lines.append(f"{idx}. {client.full_name} ({client.phone})")

    lines.append("\nДля отмены напиши /cancel.")
    await message.answer("\n".join(lines))


@router.message(AddSubscriptionStates.waiting_for_client, F.text.isdigit())
async def add_subscription_client(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    clients = data.get("clients", [])

    try:
        client_idx = int(message.text) - 1
        if client_idx < 0 or client_idx >= len(clients):
            await message.answer("Неверный номер. Попробуй ещё раз.")
            return
    except (ValueError, IndexError):
        await message.answer("Отправь, пожалуйста, номер клиента.")
        return

    selected_client = clients[client_idx]
    await state.update_data(client_id=selected_client.id)
    await state.set_state(AddSubscriptionStates.waiting_for_amount)
    await message.answer(
        f"Отлично! Клиент: <b>{selected_client.full_name}</b>\n\n"
        "Теперь отправь <b>стоимость абонемента</b> (например: 5000).\n\n"
        "Для отмены напиши /cancel."
    )


@router.message(AddSubscriptionStates.waiting_for_amount)
async def add_subscription_amount(message: Message, state: FSMContext) -> None:
    try:
        amount = Decimal(message.text.strip())
        if amount <= 0:
            await message.answer("Сумма должна быть больше нуля.")
            return
    except Exception:
        await message.answer("Неверная сумма. Отправь число, например: 5000.")
        return

    await state.update_data(amount=amount)
    await state.set_state(AddSubscriptionStates.waiting_for_duration)
    await message.answer(
        f"Сумма: <b>{amount}</b> РУБ\n\n"
        "Теперь отправь <b>длительность абонемента в днях</b> (например: 30).\n\n"
        "Для отмены напиши /cancel."
    )


@router.message(AddSubscriptionStates.waiting_for_duration)
async def add_subscription_duration(
    message: Message,
    state: FSMContext,
    business: Business | None = None,
) -> None:
    if business is None:
        await state.clear()
        await message.answer("Ошибка: не удалось определить заведение.")
        return

    try:
        days = int(message.text.strip())
        if days <= 0:
            await message.answer("Количество дней должно быть больше нуля.")
            return
    except Exception:
        await message.answer("Неверное количество дней. Отправь число, например: 30.")
        return

    data = await state.get_data()
    client_id = data.get("client_id")
    amount = data.get("amount")

    if not client_id or amount is None:
        await state.clear()
        await message.answer("Ошибка данных. Попробуй ещё раз с команды /add_subscription.")
        return

    supabase = get_supabase_client()
    today = date.today()
    end_date = today + timedelta(days=days)

    try:
        subscription = await supabase.create_subscription(
            business_id=business.id,
            client_id=client_id,
            amount=amount,
            currency="RUB",
            start_date=today,
            end_date=end_date,
            status=SubscriptionStatus.ACTIVE,
        )

        await state.clear()
        await message.answer(
            "✅ Абонемент добавлен!\n\n"
            f"<b>Сумма:</b> {subscription.amount} {subscription.currency}\n"
            f"<b>Начало:</b> {subscription.start_date}\n"
            f"<b>Окончание:</b> {subscription.end_date}\n"
            f"<b>Статус:</b> {subscription.status.value}"
        )
    except Exception as exc:
        logger.exception("Failed to create subscription: %s", exc)
        await state.clear()
        await message.answer("❌ Ошибка при сохранении абонемента.")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """
    Cancel any active dialog.
    """

    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активной операции.")
        return

    await state.clear()
    await message.answer("Операция отменена.")


@router.message(Command("subscriptions"))
async def cmd_subscriptions(
    message: Message,
    business: Business | None = None,
) -> None:
    """
    List all subscriptions for the business with status summary.
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    supabase = get_supabase_client()
    subs = await supabase.list_subscriptions_for_business(business.id)

    if not subs:
        await message.answer("Пока нет ни одного абонемента.")
        return

    stats = await supabase.get_subscription_stats_for_business(business.id)
    clients_map = {c.id: c.full_name for c in await supabase.list_clients_for_business(business.id)}

    lines = [
        "<b>📊 Абонементы</b>\n",
        f"Активно: {stats.get(SubscriptionStatus.ACTIVE, 0)} | "
        f"Истекло: {stats.get(SubscriptionStatus.EXPIRED, 0)} | "
        f"Заморозили: {stats.get(SubscriptionStatus.FROZEN, 0)}\n",
    ]

    # Group by status
    by_status = {}
    for sub in subs:
        status = sub.status
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(sub)

    for status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED, SubscriptionStatus.FROZEN, SubscriptionStatus.CANCELLED]:
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
            client_name = clients_map.get(sub.client_id, "Unknown")
            lines.append(
                f"  • {client_name}: {sub.amount} {sub.currency} (до {sub.end_date})"
            )

    await message.answer("\n".join(lines))
