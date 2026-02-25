from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.bot.keyboards import Keyboards
from app.core import get_settings
from app.core.logging import configure_logging
from app.db import get_supabase_client
from app.db.supabase import SupabaseError

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """
    /start for owners.

    On first run:
    - creates owner profile and default business for this Telegram user.
    On subsequent runs:
    - loads existing owner and business and shows a short summary.
    """

    settings = get_settings()
    logger = configure_logging()
    supabase = get_supabase_client()

    telegram_user_id = message.from_user.id
    full_name = message.from_user.full_name

    try:
        existing = await supabase.get_owner_by_telegram(telegram_user_id)
        if existing is None:
            owner, business = await supabase.create_owner_skeleton(
                telegram_user_id=telegram_user_id,
                full_name=full_name,
            )
            is_new = True
        else:
            owner, business = existing
            is_new = False
    except SupabaseError as exc:
        logger.exception("Supabase error during /start: %s", exc)
        greeting_lines = [
            "👋 Привет! Я бот для управления абонементами и напоминаниями.",
            "",
            "Сейчас не удалось подключиться к базе данных. "
            "Попробуй, пожалуйста, ещё раз позже.",
        ]
        if settings.is_debug:
            greeting_lines.append("")
            detail = (exc.detail or "").strip().replace("<", "&lt;").replace(">", "&gt;")
            if len(detail) > 600:
                detail = detail[:600] + "..."
            greeting_lines.append(
                "Режим: <b>DEBUG</b> — проверь `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` и наличие таблиц."
            )
            if exc.status_code is not None:
                greeting_lines.append(f"<code>status={exc.status_code}</code>")
            if detail:
                greeting_lines.append("<code>" + detail + "</code>")

        await message.answer("\n".join(greeting_lines))
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error during /start: %s", exc)
        await message.answer(
            "Произошла непредвиденная ошибка. Попробуй ещё раз позже."
        )
        return

    if is_new:
        greeting_lines = [
            "👋 Привет! Я создал для тебя профиль владельца и новое заведение.",
            "",
            f"Владелец: <b>{owner.full_name or full_name}</b>",
            f"Заведение: <b>{business.name}</b>",
            "",
            "Скоро тут появятся команды для управления клиентами и абонементами.",
        ]
    else:
        greeting_lines = [
            "👋 С возвращением!",
            "",
            f"Владелец: <b>{owner.full_name or full_name}</b>",
            f"Текущее заведение: <b>{business.name}</b>",
            "",
            "Выбери действие ниже или используй /menu в любой момент.",
        ]

    if settings.is_debug:
        greeting_lines.append("")
        greeting_lines.append(
            f"Режим: <b>DEBUG</b> | owner_user_id={owner.user_id} | business_id={business.id}"
        )

    await message.answer(
        "\n".join(greeting_lines),
        reply_markup=Keyboards.main_menu(),
        parse_mode="HTML",
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    """
    Show main menu.
    """

    text = "🏋️ <b>Главное меню</b>\n\nВыбери, что хочешь сделать:"
    await message.answer(
        text=text,
        reply_markup=Keyboards.main_menu(),
        parse_mode="HTML",
    )



@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """
    Show help with available commands.
    """

    help_text = """
<b>📋 Доступные команды:</b>

<b>👤 Управление клиентами</b>
/add_client — добавить нового клиента
/clients — список всех клиентов
/client_info — информация о клиенте
/search <имя или телефон> — поиск клиента

<b>💳 Управление абонементами</b>
/add_subscription — добавить абонемент клиенту
/subscriptions — список всех абонементов
/renew — продлить (обновить) абонемент
/cancel_sub — отменить абонемент
/freeze — заморозить (приостановить) абонемент

<b>💰 Платежи</b>
/payment — записать платёж

<b>� Напоминания</b>
/remind — напоминание об абонементах (на 7 дней)
/remind3 — напоминание об абонементах (на 3 дня)

<b>📊 Отчёты</b>
/report — полный отчёт по заведению
/summary — краткая статистика
/revenue — сведения о доходах

<b>📥 Экспорт</b>
/export_clients — скачать клиентов (CSV)
/export_subscriptions — скачать абонементы (CSV)
/export_payments — скачать платежи (CSV)

<b>⚙️ Настройки</b>
/settings — настройки заведения
/rename_business — изменить название заведения

<b>❓ Справка</b>
/help — эта справка
/cancel — отменить текущую операцию

Начни с <b>/start</b> чтобы создать свой профиль.
    """.strip()

    await message.answer(help_text)


