from __future__ import annotations

from datetime import date
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.core.logging import configure_logging
from app.db import get_supabase_client
from app.db.models import Business, SubscriptionStatus

router = Router(name="payments")
logger = configure_logging()


class RecordPaymentStates(StatesGroup):
    waiting_for_client = State()
    waiting_for_sub_choice = State()
    waiting_for_amount = State()
    waiting_for_notes = State()


@router.message(Command("payment"))
async def cmd_record_payment(
    message: Message,
    state: FSMContext,
    business: Business | None = None,
) -> None:
    """
    Start record payment dialog.
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    supabase = get_supabase_client()
    clients = await supabase.list_clients_for_business(business.id)

    if not clients:
        await message.answer("Нет ни одного клиента.")
        return

    await state.update_data(clients=clients, business_id=business.id)
    await state.set_state(RecordPaymentStates.waiting_for_client)

    lines = ["Выбери клиента (отправь номер):\n"]
    for idx, client in enumerate(clients, start=1):
        lines.append(f"{idx}. {client.full_name} ({client.phone})")
    lines.append("\nДля отмены напиши /cancel.")

    await message.answer("\n".join(lines))


@router.message(RecordPaymentStates.waiting_for_client, F.text.isdigit())
async def payment_select_client(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    clients = data.get("clients", [])

    try:
        client_idx = int(message.text) - 1
        if client_idx < 0 or client_idx >= len(clients):
            await message.answer("Неверный номер. Попробуй ещё раз.")
            return
    except (ValueError, IndexError):
        await message.answer("Отправь номер клиента.")
        return

    selected_client = clients[client_idx]
    supabase = get_supabase_client()
    subs = await supabase.list_subscriptions_for_client(selected_client.id)

    active_subs = [s for s in subs if s.status == SubscriptionStatus.ACTIVE]

    if not active_subs:
        await message.answer(f"У клиента {selected_client.full_name} нет активных абонементов.")
        await state.clear()
        return

    await state.update_data(client_id=selected_client.id, subscriptions=active_subs)
    await state.set_state(RecordPaymentStates.waiting_for_sub_choice)

    lines = [f"Активные абонементы {selected_client.full_name}:\n"]
    for idx, sub in enumerate(active_subs, start=1):
        lines.append(f"{idx}. {sub.amount} {sub.currency} (до {sub.end_date})")
    lines.append("\nВыбери номер абонемента.")

    await message.answer("\n".join(lines))


@router.message(RecordPaymentStates.waiting_for_sub_choice, F.text.isdigit())
async def payment_select_subscription(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    subs = data.get("subscriptions", [])

    try:
        sub_idx = int(message.text) - 1
        if sub_idx < 0 or sub_idx >= len(subs):
            await message.answer("Неверный номер. Попробуй ещё раз.")
            return
    except (ValueError, IndexError):
        await message.answer("Отправь номер абонемента.")
        return

    selected_sub = subs[sub_idx]
    await state.update_data(subscription_id=selected_sub.id, subscription=selected_sub)
    await state.set_state(RecordPaymentStates.waiting_for_amount)

    await message.answer(
        f"<b>Абонемент:</b> {selected_sub.amount} {selected_sub.currency}\n\n"
        "Отправь <b>сумму платежа</b> (например: 5000)."
    )


@router.message(RecordPaymentStates.waiting_for_amount)
async def payment_enter_amount(message: Message, state: FSMContext) -> None:
    try:
        amount = Decimal(message.text.strip())
        if amount <= 0:
            await message.answer("Сумма должна быть больше нуля.")
            return
    except Exception:
        await message.answer("Неверная сумма. Отправь число, например: 5000.")
        return

    await state.update_data(amount=amount)
    await state.set_state(RecordPaymentStates.waiting_for_notes)

    await message.answer(
        f"Сумма: <b>{amount} РУБ</b>\n\n"
        "Отправь примечание (опционально) или пропусти (/cancel)."
    )


@router.message(RecordPaymentStates.waiting_for_notes)
async def payment_enter_notes(message: Message, state: FSMContext) -> None:
    notes = message.text.strip() if message.text else None

    data = await state.get_data()
    business_id = data.get("business_id")
    sub_id = data.get("subscription_id")
    amount = data.get("amount")

    if not all([business_id, sub_id, amount]):
        await state.clear()
        await message.answer("Ошибка данных. Попробуй ещё раз.")
        return

    supabase = get_supabase_client()

    try:
        payment = await supabase.create_payment(
            business_id=business_id,
            subscription_id=sub_id,
            amount=amount,
            currency="RUB",
            payment_date=date.today(),
            notes=notes,
        )

        await state.clear()
        await message.answer(
            f"✅ Платёж записан!\n\n"
            f"<b>Сумма:</b> {payment.amount} {payment.currency}\n"
            f"<b>Дата:</b> {payment.payment_date}"
            + (f"\n<b>Примечание:</b> {payment.notes}" if payment.notes else "")
        )
    except Exception as exc:
        logger.exception("Failed to record payment: %s", exc)
        await state.clear()
        await message.answer("❌ Ошибка при сохранении платежа.")
