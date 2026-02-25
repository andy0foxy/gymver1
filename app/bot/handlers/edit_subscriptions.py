from __future__ import annotations

from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.core.logging import configure_logging
from app.db import get_supabase_client
from app.db.models import Business, SubscriptionStatus

router = Router(name="edit_subscriptions")
logger = configure_logging()


class RenewSubscriptionStates(StatesGroup):
    waiting_for_client = State()
    waiting_for_sub_choice = State()
    waiting_for_days = State()


class CancelSubscriptionStates(StatesGroup):
    waiting_for_client = State()
    waiting_for_sub_choice = State()
    waiting_for_confirmation = State()


class FreezeSubscriptionStates(StatesGroup):
    waiting_for_client = State()
    waiting_for_sub_choice = State()
    waiting_for_confirmation = State()


@router.message(Command("renew"))
async def cmd_renew(
    message: Message,
    state: FSMContext,
    business: Business | None = None,
) -> None:
    """
    Start renew subscription dialog.
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

    await state.update_data(clients=clients, business_id=business.id, action="renew")
    await state.set_state(RenewSubscriptionStates.waiting_for_client)

    lines = ["Выбери клиента (отправь номер):\n"]
    for idx, client in enumerate(clients, start=1):
        lines.append(f"{idx}. {client.full_name} ({client.phone})")
    lines.append("\nДля отмены напиши /cancel.")

    await message.answer("\n".join(lines))


@router.message(RenewSubscriptionStates.waiting_for_client, F.text.isdigit())
async def renew_select_client(message: Message, state: FSMContext) -> None:
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

    if not subs:
        await message.answer(f"У клиента {selected_client.full_name} нет абонементов.")
        await state.clear()
        return

    await state.update_data(client_id=selected_client.id, subscriptions=subs)
    await state.set_state(RenewSubscriptionStates.waiting_for_sub_choice)

    lines = [f"Абонементы {selected_client.full_name}:\n"]
    for idx, sub in enumerate(subs, start=1):
        lines.append(
            f"{idx}. {sub.amount} {sub.currency} (до {sub.end_date}) — {sub.status.value}"
        )
    lines.append("\nВыбери номер абонемента для продления.")

    await message.answer("\n".join(lines))


@router.message(RenewSubscriptionStates.waiting_for_sub_choice, F.text.isdigit())
async def renew_select_subscription(message: Message, state: FSMContext) -> None:
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
    await state.set_state(RenewSubscriptionStates.waiting_for_days)

    await message.answer(
        f"Абонемент: {selected_sub.amount} {selected_sub.currency}\n"
        f"Текущая дата окончания: {selected_sub.end_date}\n\n"
        "На сколько дней продлить? (например: 30)"
    )


@router.message(RenewSubscriptionStates.waiting_for_days)
async def renew_confirm(message: Message, state: FSMContext) -> None:
    try:
        days = int(message.text.strip())
        if days <= 0:
            await message.answer("Количество дней должно быть больше нуля.")
            return
    except Exception:
        await message.answer("Отправь число (например: 30).")
        return

    data = await state.get_data()
    subscription = data.get("subscription")
    sub_id = data.get("subscription_id")

    if not subscription or not sub_id:
        await state.clear()
        await message.answer("Ошибка данных. Попробуй ещё раз.")
        return

    supabase = get_supabase_client()
    new_end_date = subscription.end_date + timedelta(days=days)

    try:
        renewed = await supabase.renew_subscription(sub_id, new_end_date)
        await state.clear()
        await message.answer(
            f"✅ Абонемент продлён!\n\n"
            f"Новая дата окончания: <b>{renewed.end_date}</b>\n"
            f"Статус: {renewed.status.value}"
        )
    except Exception as exc:
        logger.exception("Failed to renew subscription: %s", exc)
        await state.clear()
        await message.answer("❌ Ошибка при продлении абонемента.")


@router.message(Command("cancel_sub"))
async def cmd_cancel_subscription(
    message: Message,
    state: FSMContext,
    business: Business | None = None,
) -> None:
    """
    Start cancel subscription dialog.
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

    await state.update_data(clients=clients, business_id=business.id, action="cancel")
    await state.set_state(CancelSubscriptionStates.waiting_for_client)

    lines = ["Выбери клиента (отправь номер):\n"]
    for idx, client in enumerate(clients, start=1):
        lines.append(f"{idx}. {client.full_name}")
    lines.append("\nДля отмены напиши /cancel.")

    await message.answer("\n".join(lines))


@router.message(CancelSubscriptionStates.waiting_for_client, F.text.isdigit())
async def cancel_select_client(message: Message, state: FSMContext) -> None:
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
    await state.set_state(CancelSubscriptionStates.waiting_for_sub_choice)

    lines = [f"Активные абонементы {selected_client.full_name}:\n"]
    for idx, sub in enumerate(active_subs, start=1):
        lines.append(f"{idx}. {sub.amount} {sub.currency} (до {sub.end_date})")
    lines.append("\nВыбери номер для отмены.")

    await message.answer("\n".join(lines))


@router.message(CancelSubscriptionStates.waiting_for_sub_choice, F.text.isdigit())
async def cancel_confirm(message: Message, state: FSMContext) -> None:
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
    await state.set_state(CancelSubscriptionStates.waiting_for_confirmation)

    await message.answer(
        f"❌ Отменить абонемент?\n"
        f"Сумма: {selected_sub.amount} {selected_sub.currency}\n"
        f"Окончание: {selected_sub.end_date}\n\n"
        "Напиши YES для подтверждения или /cancel для отмены."
    )


@router.message(CancelSubscriptionStates.waiting_for_confirmation, F.text.upper() == "YES")
async def cancel_confirm_yes(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    sub_id = data.get("subscription_id")

    if not sub_id:
        await state.clear()
        await message.answer("Ошибка данных.")
        return

    supabase = get_supabase_client()

    try:
        cancelled = await supabase.update_subscription_status(
            sub_id, SubscriptionStatus.CANCELLED
        )
        await state.clear()
        await message.answer(
            f"✅ Абонемент отменён.\n"
            f"Статус: {cancelled.status.value}"
        )
    except Exception as exc:
        logger.exception("Failed to cancel subscription: %s", exc)
        await state.clear()
        await message.answer("❌ Ошибка при отмене абонемента.")


@router.message(Command("freeze"))
async def cmd_freeze_subscription(
    message: Message,
    state: FSMContext,
    business: Business | None = None,
) -> None:
    """
    Start freeze subscription dialog (pause without canceling).
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

    await state.update_data(clients=clients, business_id=business.id, action="freeze")
    await state.set_state(FreezeSubscriptionStates.waiting_for_client)

    lines = ["Выбери клиента (отправь номер):\n"]
    for idx, client in enumerate(clients, start=1):
        lines.append(f"{idx}. {client.full_name}")
    lines.append("\nДля отмены напиши /cancel.")

    await message.answer("\n".join(lines))


@router.message(FreezeSubscriptionStates.waiting_for_client, F.text.isdigit())
async def freeze_select_client(message: Message, state: FSMContext) -> None:
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
    await state.set_state(FreezeSubscriptionStates.waiting_for_sub_choice)

    lines = [f"Активные абонементы {selected_client.full_name}:\n"]
    for idx, sub in enumerate(active_subs, start=1):
        lines.append(f"{idx}. {sub.amount} {sub.currency} (до {sub.end_date})")
    lines.append("\nВыбери номер для заморозки.")

    await message.answer("\n".join(lines))


@router.message(FreezeSubscriptionStates.waiting_for_sub_choice, F.text.isdigit())
async def freeze_confirm(message: Message, state: FSMContext) -> None:
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
    await state.set_state(FreezeSubscriptionStates.waiting_for_confirmation)

    await message.answer(
        f"🧊 Заморозить абонемент?\n"
        f"Сумма: {selected_sub.amount} {selected_sub.currency}\n"
        f"Окончание: {selected_sub.end_date}\n\n"
        "Напиши YES для подтверждения или /cancel для отмены."
    )


@router.message(FreezeSubscriptionStates.waiting_for_confirmation, F.text.upper() == "YES")
async def freeze_confirm_yes(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    sub_id = data.get("subscription_id")

    if not sub_id:
        await state.clear()
        await message.answer("Ошибка данных.")
        return

    supabase = get_supabase_client()

    try:
        frozen = await supabase.update_subscription_status(
            sub_id, SubscriptionStatus.FROZEN
        )
        await state.clear()
        await message.answer(
            f"✅ Абонемент заморозлен.\n"
            f"Статус: {frozen.status.value}"
        )
    except Exception as exc:
        logger.exception("Failed to freeze subscription: %s", exc)
        await state.clear()
        await message.answer("❌ Ошибка при заморозке абонемента.")
