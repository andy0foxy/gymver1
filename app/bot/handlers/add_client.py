from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.core.validation import normalize_phone
from app.db import get_supabase_client
from app.db.models import Business


router = Router(name="add_client")


class AddClientStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()


@router.message(Command("add_client"))
async def cmd_add_client(message: Message, state: FSMContext, business: Business | None = None) -> None:
    """
    Start add-client dialog: ask for client name.
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    await state.set_state(AddClientStates.waiting_for_name)
    await message.answer(
        "Давай добавим клиента.\n"
        "Отправь, пожалуйста, <b>имя клиента</b>.\n\n"
        "Для отмены напиши /cancel."
    )


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


@router.message(AddClientStates.waiting_for_name, F.text.len() > 0)
async def add_client_name(message: Message, state: FSMContext) -> None:
    await state.update_data(full_name=message.text.strip())
    await state.set_state(AddClientStates.waiting_for_phone)
    await message.answer(
        "Теперь отправь, пожалуйста, <b>телефон клиента</b>.\n"
        "Формат: +79990000000 или 89990000000.\n\n"
        "Для отмены напиши /cancel."
    )


@router.message(AddClientStates.waiting_for_phone)
async def add_client_phone(
    message: Message,
    state: FSMContext,
    business: Business | None = None,
) -> None:
    if business is None:
        await state.clear()
        await message.answer(
            "Не удалось определить заведение. Попробуй ещё раз с команды /add_client."
        )
        return

    phone = normalize_phone(message.text or "")
    if phone is None:
        await message.answer(
            "Телефон выглядит некорректно. Попробуй ещё раз в формате +79990000000."
        )
        return

    data = await state.get_data()
    full_name = data.get("full_name")
    if not full_name:
        await state.clear()
        await message.answer("Что-то пошло не так, попробуй ещё раз с команды /add_client.")
        return

    supabase = get_supabase_client()
    client = await supabase.create_client(
        business_id=business.id,
        full_name=full_name,
        phone=phone,
    )

    await state.clear()
    await message.answer(
        "Клиент сохранён:\n"
        f"<b>{client.full_name}</b>\n"
        f"Телефон: <code>{client.phone}</code>"
    )

