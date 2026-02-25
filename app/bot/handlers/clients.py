from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.db import get_supabase_client
from app.db.models import Business

router = Router(name="clients")


@router.message(Command("clients"))
async def cmd_clients(message: Message, business: Business | None = None) -> None:
    """
    List all clients for the current business.
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    supabase = get_supabase_client()
    clients = await supabase.list_clients_for_business(business.id)

    if not clients:
        await message.answer("Пока нет ни одного клиента. Скоро добавим /add_client.")
        return

    lines: list[str] = ["Список клиентов:", ""]
    for idx, client in enumerate(clients, start=1):
        lines.append(f"{idx}. {client.full_name} — {client.phone}")

    await message.answer("\n".join(lines))

