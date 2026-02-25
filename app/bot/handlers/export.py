from __future__ import annotations

import io
from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from app.core.logging import configure_logging
from app.db import get_supabase_client
from app.db.models import Business

router = Router(name="export")
logger = configure_logging()


@router.message(Command("export_clients"))
async def cmd_export_clients(message: Message, business: Business | None = None) -> None:
    """
    Export all clients to CSV file.
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    supabase = get_supabase_client()

    try:
        clients = await supabase.list_clients_for_business(business.id)

        if not clients:
            await message.answer("Нет клиентов для экспорта.")
            return

        # Generate CSV
        csv_content = "Имя,Телефон,Дата добавления\n"
        for client in clients:
            csv_content += f'"{client.full_name}","{client.phone}","{client.created_at.date()}"\n'

        # Create file
        csv_bytes = csv_content.encode("utf-8")
        file = BufferedInputFile(
            file=csv_bytes,
            filename=f"clients_{business.id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )

        await message.answer_document(
            document=file,
            caption=f"Экспорт клиентов: {len(clients)} клиентов",
        )

    except Exception as exc:
        logger.exception("Error exporting clients: %s", exc)
        await message.answer("❌ Ошибка при экспорте клиентов.")


@router.message(Command("export_subscriptions"))
async def cmd_export_subscriptions(
    message: Message,
    business: Business | None = None,
) -> None:
    """
    Export all subscriptions to CSV file.
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    supabase = get_supabase_client()

    try:
        subs = await supabase.list_subscriptions_for_business(business.id)
        clients = await supabase.list_clients_for_business(business.id)
        client_map = {c.id: c.full_name for c in clients}

        if not subs:
            await message.answer("Нет абонементов для экспорта.")
            return

        # Generate CSV
        csv_content = "Клиент,Сумма,Валюта,Начало,Окончание,Статус\n"
        for sub in subs:
            client_name = client_map.get(sub.client_id, "Unknown")
            csv_content += (
                f'"{client_name}","{sub.amount}","{sub.currency}",'
                f'"{sub.start_date}","{sub.end_date}","{sub.status.value}"\n'
            )

        # Create file
        csv_bytes = csv_content.encode("utf-8")
        file = BufferedInputFile(
            file=csv_bytes,
            filename=f"subscriptions_{business.id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )

        await message.answer_document(
            document=file,
            caption=f"Экспорт абонементов: {len(subs)} абонементов",
        )

    except Exception as exc:
        logger.exception("Error exporting subscriptions: %s", exc)
        await message.answer("❌ Ошибка при экспорте абонементов.")


@router.message(Command("export_payments"))
async def cmd_export_payments(
    message: Message,
    business: Business | None = None,
) -> None:
    """
    Export all payments to CSV file.
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    supabase = get_supabase_client()

    try:
        payments = await supabase.list_payments_for_business(business.id)

        if not payments:
            await message.answer("Нет платежей для экспорта.")
            return

        # Generate CSV
        csv_content = "Сумма,Валюта,Дата платежа,Примечание\n"
        for payment in payments:
            notes = payment.notes or ""
            csv_content += (
                f'"{payment.amount}","{payment.currency}",'
                f'"{payment.payment_date}","{notes}"\n'
            )

        # Create file
        csv_bytes = csv_content.encode("utf-8")
        file = BufferedInputFile(
            file=csv_bytes,
            filename=f"payments_{business.id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )

        await message.answer_document(
            document=file,
            caption=f"Экспорт платежей: {len(payments)} платежей",
        )

    except Exception as exc:
        logger.exception("Error exporting payments: %s", exc)
        await message.answer("❌ Ошибка при экспорте платежей.")
