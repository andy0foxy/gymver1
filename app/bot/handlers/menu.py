from __future__ import annotations

from datetime import date, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import Keyboards, MessageTemplates
from app.core.logging import configure_logging
from app.core.validation import normalize_phone
from app.db import get_supabase_client
from app.db.models import Business, SubscriptionStatus

router = Router(name="menu")
logger = configure_logging()


class QuickDialogStates(StatesGroup):
    """Quick dialog states for callbacks."""
    waiting_for_client = State()
    waiting_for_sub_choice = State()
    waiting_for_days = State()
    waiting_input = State()
    waiting_for_reminder_hour = State()
    waiting_for_reminder_days = State()


@router.message(QuickDialogStates.waiting_input)
async def handle_quick_dialog_input(message: Message, state: FSMContext, business: Business | None = None) -> None:
    """Handle text input during quick dialogs."""
    if not message.text:
        await message.answer("Отправь текст, пожалуйста.")
        return

    data = await state.get_data()
    action = data.get("action")

    if action == "add_client":
        # Handle add client - just save name and ask for phone
        await state.update_data(full_name=message.text.strip())
        await state.set_state(QuickDialogStates.waiting_input)
        await state.update_data(action="add_client_phone")
        await message.answer(
            "Теперь отправь <b>телефон клиента</b>.\n"
            "Формат: +79990000000 или 89990000000.",
            parse_mode="HTML",
        )

    elif action == "add_client_phone":
        # Handle phone for new client
        if business is None:
            await state.clear()
            await message.answer("Ошибка: заведение не определено.")
            return

        phone = normalize_phone(message.text or "")
        if phone is None:
            await message.answer("Телефон выглядит некорректно. Попробуй ещё раз в формате +79990000000.")
            return

        data_state = await state.get_data()
        full_name = data_state.get("full_name")
        if not full_name:
            await state.clear()
            await message.answer("Ошибка: имя клиента не найдено. Попробуй ещё раз.")
            return

        supabase = get_supabase_client()
        client = await supabase.create_client(
            business_id=business.id,
            full_name=full_name,
            phone=phone,
        )
        await state.clear()

        text = (
            f"✅ <b>Клиент добавлен</b>\n\n"
            f"📛 {client.full_name}\n"
            f"📞 {client.phone}"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=Keyboards.clients_menu())

    elif action == "search_client":
        # Handle search
        if business is None:
            await state.clear()
            await message.answer("Ошибка: заведение не определено.")
            return

        supabase = get_supabase_client()
        query = message.text.strip()
        clients = await supabase.search_clients_by_name(business.id, query)
        if not clients:
            clients = await supabase.search_clients_by_phone(business.id, query)

        await state.clear()

        if not clients:
            text = f"❌ Клиентов не найдено по запросу: {query}"
        else:
            lines = [f"🔍 <b>Результаты поиска</b> ({len(clients)})\n"]
            for client in clients[:10]:
                lines.append(f"  • {client.full_name} — {client.phone}")
            if len(clients) > 10:
                lines.append(f"\n  ... ещё {len(clients) - 10}")
            text = "\n".join(lines)

        await message.answer(text, parse_mode="HTML", reply_markup=Keyboards.clients_menu())

    elif action == "rename_business":
        # Handle business rename
        if business is None:
            await state.clear()
            await message.answer("Ошибка: заведение не определено.")
            return

        new_name = message.text.strip()
        supabase = get_supabase_client()
        await supabase.update_business_name(business.id, new_name)
        
        await state.clear()
        text = f"✅ <b>Название изменено на:</b> {new_name}"
        await message.answer(text, parse_mode="HTML", reply_markup=Keyboards.settings_menu())

    else:
        await message.answer("Неизвестная операция. Попробуй ещё раз.")
        await state.clear()


@router.message(QuickDialogStates.waiting_for_client)
async def handle_client_selection(message: Message, state: FSMContext, business: Business | None = None) -> None:
    """Handle client selection from list."""
    if not message.text or not message.text.isdigit():
        await message.answer("Отправь номер из списка, пожалуйста.")
        return

    data = await state.get_data()
    clients = data.get("clients", [])
    client_idx = int(message.text) - 1

    if client_idx < 0 or client_idx >= len(clients):
        await message.answer(f"Номер должен быть от 1 до {len(clients)}.")
        return

    selected_client = clients[client_idx]
    action = data.get("action")

    if action == "add_subscription":
        # Move to next step: ask for subscription type/days
        await state.update_data(selected_client_id=selected_client.id, selected_client=selected_client)
        await state.set_state(QuickDialogStates.waiting_for_days)
        await message.answer(
            f"Клиент: <b>{selected_client.full_name}</b>\n\n"
            "Отправь <b>срок абонемента (в днях)</b>:\n"
            "Например: 30, 60, 90",
            parse_mode="HTML",
        )
    else:
        await message.answer("Неизвестная операция.")
        await state.clear()


@router.message(QuickDialogStates.waiting_for_days)
async def handle_subscription_days(message: Message, state: FSMContext, business: Business | None = None) -> None:
    """Handle subscription days input."""
    if not message.text or not message.text.isdigit():
        await message.answer("Отправь количество дней (число), пожалуйста.")
        return

    if business is None:
        await state.clear()
        await message.answer("Ошибка: заведение не определено.")
        return

    days = int(message.text)
    if days <= 0 or days > 365:
        await message.answer("Срок должен быть от 1 до 365 дней.")
        return

    data = await state.get_data()
    client_id = data.get("selected_client_id")
    client = data.get("selected_client")

    if not client_id or not client:
        await state.clear()
        await message.answer("Ошибка: клиент не найден.")
        return

    supabase = get_supabase_client()
    end_date = date.today() + timedelta(days=days)

    subscription = await supabase.create_subscription(
        business_id=business.id,
        client_id=client_id,
        subscription_type="basic",
        start_date=date.today(),
        end_date=end_date,
    )

    await state.clear()
    text = (
        f"✅ <b>Абонемент добавлен</b>\n\n"
        f"📛 {client.full_name}\n"
        f"📅 {days} дней ({end_date.strftime('%d.%m.%Y')})"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=Keyboards.subscriptions_menu())
@router.callback_query(F.data == "menu_main")
async def show_main_menu(query: CallbackQuery, business: Business | None = None) -> None:
    """Show main menu."""
    if business is None:
        await query.answer("Сначала используй /start", show_alert=True)
        return

    text = (
        f"<b>🏋️ {business.name}</b>\n\n"
        "Выбери, что хочешь сделать:"
    )

    await query.message.edit_text(
        text=text,
        reply_markup=Keyboards.main_menu(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "menu_clients")
async def show_clients_menu(query: CallbackQuery) -> None:
    """Show clients submenu."""
    text = (
        f"{MessageTemplates.header('Управление клиентами', '👥')}\n"
        "Что ты хочешь сделать?"
    )

    await query.message.edit_text(
        text=text,
        reply_markup=Keyboards.clients_menu(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "menu_subscriptions")
async def show_subscriptions_menu(query: CallbackQuery) -> None:
    """Show subscriptions submenu."""
    text = (
        f"{MessageTemplates.header('Управление абонементами', '💳')}\n"
        "Выбери действие:"
    )

    await query.message.edit_text(
        text=text,
        reply_markup=Keyboards.subscriptions_menu(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "menu_payments")
async def show_payments_menu(query: CallbackQuery) -> None:
    """Show payments submenu."""
    text = (
        f"{MessageTemplates.header('Управление платежами', '💰')}\n"
        "Что ты хочешь?"
    )

    await query.message.edit_text(
        text=text,
        reply_markup=Keyboards.payments_menu(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "add_payment")
async def callback_add_payment(query: CallbackQuery, state: FSMContext) -> None:
    """Start add payment dialog."""
    await state.set_state(QuickDialogStates.waiting_input)
    await state.update_data(action="add_payment")
    
    await query.message.edit_text(
        "Функция в разработке 🔄",
        parse_mode="HTML",
        reply_markup=Keyboards.back_button("menu_payments"),
    )
    await query.answer()


@router.callback_query(F.data == "list_payments")
async def callback_list_payments(query: CallbackQuery, business: Business | None = None) -> None:
    """Show payment history."""
    if business is None:
        await query.answer("Ошибка: заведение не определено", show_alert=True)
        return

    supabase = get_supabase_client()
    payments = await supabase.list_payments_for_business(business.id)

    if not payments:
        text = "💰 <b>История платежей</b>\n\nПлатежей не найдено."
    else:
        lines = [f"💰 <b>История платежей</b> ({len(payments)})\n"]
        for payment in payments[:10]:
            lines.append(f"  • {payment.amount} РУБ - {payment.created_at.date()}")
        if len(payments) > 10:
            lines.append(f"\n  ... ещё {len(payments) - 10}")
        text = "\n".join(lines)

    await query.message.edit_text(
        text=text,
        reply_markup=Keyboards.payments_menu(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "revenue_stats")
async def callback_revenue_stats(query: CallbackQuery, business: Business | None = None) -> None:
    """Show revenue statistics."""
    if business is None:
        await query.answer("Ошибка: заведение не определено", show_alert=True)
        return

    supabase = get_supabase_client()
    revenue = await supabase.get_subscription_revenue_stats(business.id)

    lines = [
        "<b>💹 Статистика доходов</b>",
        "",
        f"Всего: <b>{revenue['total']} РУБ</b>",
        f"Этот месяц: <b>{revenue['this_month']} РУБ</b>",
        f"В среднем/месяц: {revenue['avg_monthly']} РУБ",
    ]

    await query.message.edit_text(
        text="\n".join(lines),
        reply_markup=Keyboards.payments_menu(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "menu_reports")
async def show_reports_menu(query: CallbackQuery) -> None:
    """Show reports submenu."""
    text = (
        f"{MessageTemplates.header('Отчёты', '📊')}\n"
        "Выбери тип отчёта:"
    )

    await query.message.edit_text(
        text=text,
        reply_markup=Keyboards.reports_menu(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "menu_settings")
async def show_settings_menu(query: CallbackQuery) -> None:
    """Show settings submenu."""
    text = (
        f"{MessageTemplates.header('Настройки', '⚙️')}\n"
        "Управление заведением:"
    )

    await query.message.edit_text(
        text=text,
        reply_markup=Keyboards.settings_menu(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "menu_help")
async def show_help_menu(query: CallbackQuery) -> None:
    """Show help."""
    help_text = """
<b>📋 Справка и команды</b>

<b>Навигация:</b> Используй кнопки в нижней части экрана для быстрого доступа к функциям.

<b>Главное меню:</b>
  • 👥 Клиенты — управление список клиентов
  • 💳 Абонементы — просмотр и управление абонементами
  • 💰 Платежи — запись платежей и доходов
  • 📊 Отчёты — аналитика и статистика
  • ⚙️ Настройки — параметры заведения

<b>Быстрые команды:</b>
  • /start — инициализация
  • /menu — главное меню
  • /help — эта справка

<b>Советы:</b>
  ✓ Используй кнопки для навигации
  ✓ Команда /cancel отменяет любую операцию
  ✓ Все данные сохраняются автоматически
    """.strip()

    await query.message.edit_text(
        text=help_text,
        reply_markup=Keyboards.back_button("menu_main"),
        parse_mode="HTML",
    )
    await query.answer()


# ============= CLIENT ACTIONS =============

@router.callback_query(F.data == "list_clients")
async def callback_list_clients(query: CallbackQuery, business: Business | None = None) -> None:
    """List all clients."""
    if business is None:
        await query.answer("Ошибка: заведение не определено", show_alert=True)
        return

    supabase = get_supabase_client()
    clients = await supabase.list_clients_for_business(business.id)

    if not clients:
        text = "📋 Клиентов не найдено."
    else:
        lines = [f"📋 <b>Клиенты ({len(clients)})</b>\n"]
        for idx, client in enumerate(clients[:20], start=1):
            lines.append(f"{idx}. {client.full_name} — {client.phone}")
        if len(clients) > 20:
            lines.append(f"\n... ещё {len(clients) - 20}")
        text = "\n".join(lines)

    await query.message.edit_text(
        text=text,
        reply_markup=Keyboards.clients_menu(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "add_client")
async def callback_add_client(query: CallbackQuery, state: FSMContext) -> None:
    """Start add client dialog."""
    await state.set_state(QuickDialogStates.waiting_input)
    await state.update_data(action="add_client")
    
    await query.message.edit_text(
        "Отправь <b>имя клиента</b>:",
        parse_mode="HTML",
        reply_markup=Keyboards.back_button("menu_clients"),
    )
    await query.answer()


@router.callback_query(F.data == "search_client")
async def callback_search_client(query: CallbackQuery, state: FSMContext) -> None:
    """Start search client dialog."""
    await state.set_state(QuickDialogStates.waiting_input)
    await state.update_data(action="search_client")
    
    await query.message.edit_text(
        "Отправь <b>имя или телефон</b> для поиска:",
        parse_mode="HTML",
        reply_markup=Keyboards.back_button("menu_clients"),
    )
    await query.answer()


# ============= SUBSCRIPTION ACTIONS =============

@router.callback_query(F.data == "list_subscriptions")
async def callback_list_subscriptions(query: CallbackQuery, business: Business | None = None) -> None:
    """List all subscriptions."""
    if business is None:
        await query.answer("Ошибка: заведение не определено", show_alert=True)
        return

    supabase = get_supabase_client()
    subs = await supabase.list_subscriptions_for_business(business.id)
    stats = await supabase.get_subscription_stats_for_business(business.id)

    if not subs:
        text = "💳 Абонементов не найдено."
    else:
        lines = [
            f"💳 <b>Абонементы</b>",
            f"✅ Активно: {stats.get(SubscriptionStatus.ACTIVE, 0)}",
            f"❌ Истекло: {stats.get(SubscriptionStatus.EXPIRED, 0)}",
            f"🧊 Заморозлено: {stats.get(SubscriptionStatus.FROZEN, 0)}",
            "",
            f"Всего: {len(subs)} абонементов",
        ]
        text = "\n".join(lines)

    await query.message.edit_text(
        text=text,
        reply_markup=Keyboards.subscriptions_menu(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "add_subscription")
async def callback_add_subscription(query: CallbackQuery, state: FSMContext, business: Business | None = None) -> None:
    """Start add subscription dialog."""
    if business is None:
        await query.answer("Ошибка: заведение не определено", show_alert=True)
        return

    supabase = get_supabase_client()
    clients = await supabase.list_clients_for_business(business.id)

    if not clients:
        await query.message.edit_text(
            "⚠️ Нет клиентов. Добавь клиента сначала.",
            reply_markup=Keyboards.subscriptions_menu(),
        )
        await query.answer()
        return

    await state.set_state(QuickDialogStates.waiting_for_client)
    await state.update_data(clients=clients, business_id=business.id, action="add_subscription")

    lines = ["Выбери клиента:\n"]
    for idx, client in enumerate(clients[:10], start=1):
        lines.append(f"{idx}. {client.full_name}")
    lines.append("\nОтправь номер:")

    await query.message.edit_text(
        text="\n".join(lines),
        reply_markup=Keyboards.back_button("menu_subscriptions"),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "renew_subscription")
async def callback_renew_subscription(query: CallbackQuery, business: Business | None = None) -> None:
    """Start renew subscription dialog."""
    if business is None:
        await query.answer("Ошибка: заведение не определено", show_alert=True)
        return

    supabase = get_supabase_client()
    subs = await supabase.list_subscriptions_for_business(business.id)
    
    if not subs:
        await query.message.edit_text(
            "⚠️ Нет абонементов для продления.",
            reply_markup=Keyboards.subscriptions_menu(),
        )
        await query.answer()
        return

    await query.message.edit_text(
        "Выбери абонемент для продления (функция в разработке)",
        reply_markup=Keyboards.subscriptions_menu(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "cancel_subscription")
async def callback_cancel_subscription(query: CallbackQuery, business: Business | None = None) -> None:
    """Start cancel subscription dialog."""
    if business is None:
        await query.answer("Ошибка: заведение не определено", show_alert=True)
        return

    supabase = get_supabase_client()
    subs = await supabase.list_subscriptions_for_business(business.id)
    
    if not subs:
        await query.message.edit_text(
            "⚠️ Нет абонементов для отмены.",
            reply_markup=Keyboards.subscriptions_menu(),
        )
        await query.answer()
        return

    await query.message.edit_text(
        "Выбери абонемент для отмены (функция в разработке)",
        reply_markup=Keyboards.subscriptions_menu(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "freeze_subscription")
async def callback_freeze_subscription(query: CallbackQuery, business: Business | None = None) -> None:
    """Start freeze subscription dialog."""
    if business is None:
        await query.answer("Ошибка: заведение не определено", show_alert=True)
        return

    supabase = get_supabase_client()
    subs = await supabase.list_subscriptions_for_business(business.id)
    
    if not subs:
        await query.message.edit_text(
            "⚠️ Нет абонементов для заморозки.",
            reply_markup=Keyboards.subscriptions_menu(),
        )
        await query.answer()
        return

    await query.message.edit_text(
        "Выбери абонемент для заморозки (функция в разработке)",
        reply_markup=Keyboards.subscriptions_menu(),
        parse_mode="HTML",
    )
    await query.answer()


# ============= REPORT ACTIONS =============

@router.callback_query(F.data == "full_report")
async def callback_full_report(query: CallbackQuery, business: Business | None = None) -> None:
    """Show full report."""
    if business is None:
        await query.answer("Ошибка: заведение не определено", show_alert=True)
        return

    supabase = get_supabase_client()
    subs = await supabase.list_subscriptions_for_business(business.id)
    clients = await supabase.list_clients_for_business(business.id)
    stats = await supabase.get_subscription_stats_for_business(business.id)
    revenue = await supabase.get_subscription_revenue_stats(business.id)

    lines = [
        f"<b>📊 {business.name}</b>",
        "",
        f"👥 Клиентов: {len(clients)}",
        f"💳 Активные: {stats.get(SubscriptionStatus.ACTIVE, 0)} из {len(subs)}",
        f"💰 Доход месяца: {revenue['this_month']} РУБ",
        "",
        f"<i>Обновлено: {date.today()}</i>",
    ]

    await query.message.edit_text(
        text="\n".join(lines),
        reply_markup=Keyboards.reports_menu(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "summary_report")
async def callback_summary_report(query: CallbackQuery, business: Business | None = None) -> None:
    """Show summary report."""
    if business is None:
        await query.answer("Ошибка: заведение не определено", show_alert=True)
        return

    supabase = get_supabase_client()
    subs = await supabase.list_subscriptions_for_business(business.id)
    stats = await supabase.get_subscription_stats_for_business(business.id)
    revenue = await supabase.get_subscription_revenue_stats(business.id)

    active = stats.get(SubscriptionStatus.ACTIVE, 0)
    total = len(subs)
    percent = int((active / total * 100) if total > 0 else 0)

    lines = [
        f"<b>📈 {business.name}</b>",
        "",
        f"💳 {active}/{total} активно ({percent}%)",
        f"💰 {revenue['this_month']} РУБ этот месяц",
    ]

    await query.message.edit_text(
        text="\n".join(lines),
        reply_markup=Keyboards.reports_menu(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "revenue_report")
async def callback_revenue_report(query: CallbackQuery, business: Business | None = None) -> None:
    """Show revenue report."""
    if business is None:
        await query.answer("Ошибка: заведение не определено", show_alert=True)
        return

    supabase = get_supabase_client()
    revenue = await supabase.get_subscription_revenue_stats(business.id)
    payments = await supabase.list_payments_for_business(business.id)

    lines = [
        "<b>💰 Доходы</b>",
        "",
        f"Всего: <b>{revenue['total']} РУБ</b>",
        f"Месяц: <b>{revenue['this_month']} РУБ</b>",
        f"Среднем: {revenue['avg_monthly']} РУБ",
        "",
        f"Платежи: {len(payments)}",
    ]

    await query.message.edit_text(
        text="\n".join(lines),
        reply_markup=Keyboards.reports_menu(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "expiring_report")
async def callback_expiring_report(query: CallbackQuery, business: Business | None = None) -> None:
    """Show expiring subscriptions report."""
    if business is None:
        await query.answer("Ошибка: заведение не определено", show_alert=True)
        return

    supabase = get_supabase_client()
    expiring = await supabase.list_expiring_subscriptions(business.id, days_until=7)
    clients = await supabase.list_clients_for_business(business.id)
    client_map = {c.id: c.full_name for c in clients}

    if not expiring:
        text = "✅ Нет абонементов, истекающих в течение 7 дней."
    else:
        lines = [f"⏰ <b>Истекают скоро ({len(expiring)})</b>\n"]
        today = date.today()
        for sub in expiring:
            name = client_map.get(sub.client_id, "Unknown")
            days = (sub.end_date - today).days
            lines.append(f"  • {name}: {days} дней")
        text = "\n".join(lines)

    await query.message.edit_text(
        text=text,
        reply_markup=Keyboards.reports_menu(),
        parse_mode="HTML",
    )
    await query.answer()


# ============= SETTINGS ACTIONS =============

@router.callback_query(F.data == "business_info")
async def callback_business_info(query: CallbackQuery, business: Business | None = None) -> None:
    """Show business info."""
    if business is None:
        await query.answer("Ошибка: заведение не определено", show_alert=True)
        return

    lines = [
        f"ℹ️ <b>О заведении</b>",
        "",
        f"<b>Название:</b> {business.name}",
        f"<b>ID:</b> <code>{business.id[:8]}...</code>",
        f"<b>Создано:</b> {business.created_at.date()}",
    ]

    await query.message.edit_text(
        text="\n".join(lines),
        reply_markup=Keyboards.settings_menu(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "rename_business")
async def callback_rename_business(query: CallbackQuery, state: FSMContext) -> None:
    """Start rename business dialog."""
    await state.set_state(QuickDialogStates.waiting_input)
    await state.update_data(action="rename_business")
    
    await query.message.edit_text(
        "Отправь <b>новое название</b> заведения:",
        parse_mode="HTML",
        reply_markup=Keyboards.back_button("menu_settings"),
    )
    await query.answer()


@router.callback_query(F.data == "export_data")
async def callback_export_data(query: CallbackQuery) -> None:
    """Show export menu."""
    text = "<b>📥 Экспорт данных</b>\n\nВыбери что экспортировать:"

    await query.message.edit_text(
        text=text,
        reply_markup=Keyboards.export_menu(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "test_reminder")
async def callback_configure_reminders(query: CallbackQuery, state: FSMContext) -> None:
    """Show reminder configuration."""
    await state.set_state(QuickDialogStates.waiting_for_reminder_hour)
    
    text = (
        "🔔 <b>Настройка напоминаний</b>\n\n"
        "Во сколько часов отправлять напоминания?\n"
        "Отправь час (0-23):\n"
        "Например: 10 (для 10:00)"
    )
    
    await query.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=Keyboards.back_button("menu_settings"),
    )
    await query.answer()


@router.message(QuickDialogStates.waiting_for_reminder_hour)
async def handle_reminder_hour_input(message: Message, state: FSMContext) -> None:
    """Handle reminder hour input."""
    if not message.text or not message.text.isdigit():
        await message.answer("Отправь число от 0 до 23, пожалуйста.")
        return

    hour = int(message.text)
    if hour < 0 or hour > 23:
        await message.answer("Час должен быть от 0 до 23.")
        return

    await state.update_data(reminder_hour=hour)
    await state.set_state(QuickDialogStates.waiting_for_reminder_days)
    
    text = (
        "За сколько дней <b>до истечения абонемента</b> отправлять напоминание?\n"
        "Отправь число (1-30):\n"
        "Например: 7 (напоминать за неделю)"
    )
    
    await message.answer(text, parse_mode="HTML")


@router.message(QuickDialogStates.waiting_for_reminder_days)
async def handle_reminder_days_input(
    message: Message,
    state: FSMContext,
    business: Business | None = None,
) -> None:
    """Handle reminder days input and save settings."""
    if not message.text or not message.text.isdigit():
        await message.answer("Отправь число от 1 до 30, пожалуйста.")
        return

    days = int(message.text)
    if days < 1 or days > 30:
        await message.answer("Дни должны быть от 1 до 30.")
        return

    data = await state.get_data()
    reminder_hour = data.get("reminder_hour")

    if business is None:
        await state.clear()
        await message.answer("Ошибка: заведение не определено.")
        return

    supabase = get_supabase_client()
    
    try:
        owner = await supabase.update_reminder_settings(
            owner_id=business.owner_id,
            reminder_enabled=True,
            reminder_hour=reminder_hour,
            reminder_days_before=days,
        )

        await state.clear()

        text = (
            f"✅ <b>Напоминания настроены</b>\n\n"
            f"⏰ <b>Время:</b> {reminder_hour}:00\n"
            f"📅 <b>За дней:</b> {days} дней до истечения\n\n"
            "Ты будешь получать напоминания о скоро истекающих абонементах."
        )
        await message.answer(text, parse_mode="HTML", reply_markup=Keyboards.settings_menu())
    except Exception as e:
        logger.error(f"Failed to update reminder settings: {e}")
        await state.clear()
        await message.answer(f"❌ Ошибка при сохранении: {str(e)[:100]}")


# ============= EXPORT ACTIONS =============

@router.callback_query(F.data == "export_clients")
async def callback_export_clients_forward(query: CallbackQuery) -> None:
    """Forward to export handler."""
    await query.answer("Экспорт запущен...")
    # The actual export handler in export.py will handle this
    await query.answer()


@router.callback_query(F.data == "export_subscriptions")
async def callback_export_subscriptions_forward(query: CallbackQuery) -> None:
    """Forward to export handler."""
    await query.answer("Экспорт запущен...")


@router.callback_query(F.data == "export_payments")
async def callback_export_payments_forward(query: CallbackQuery) -> None:
    """Forward to export handler."""
    await query.answer("Экспорт запущен...")


# ============= CONFIRMATION ACTIONS =============

@router.callback_query(F.data == "confirm_yes")
async def callback_confirm_yes(query: CallbackQuery, state: FSMContext) -> None:
    """Handle confirmation yes."""
    data = await state.get_data()
    action = data.get("pending_action")
    
    if action == "delete_client":
        await query.answer("Удаление в разработке")
    elif action == "delete_subscription":
        await query.answer("Удаление в разработке")
    else:
        await query.answer("Действие подтверждено")
    
    await state.clear()


@router.callback_query(F.data == "confirm_no")
async def callback_confirm_no(query: CallbackQuery, state: FSMContext) -> None:
    """Handle confirmation no."""
    await query.message.edit_text(
        "Операция отменена.",
        reply_markup=Keyboards.main_menu(),
    )
    await state.clear()
    await query.answer()
