from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.core.logging import configure_logging
from app.db import get_supabase_client
from app.db.models import Business

router = Router(name="business_settings")
logger = configure_logging()


class UpdateBusinessNameStates(StatesGroup):
    waiting_for_new_name = State()


@router.message(Command("settings"))
async def cmd_settings(message: Message, business: Business | None = None) -> None:
    """
    Show business settings.
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    lines = [
        "<b>⚙️ Настройки заведения</b>",
        "",
        f"<b>Название:</b> {business.name}",
        f"<b>ID:</b> <code>{business.id}</code>",
        f"<b>Создано:</b> {business.created_at.date()}",
        "",
        "<b>Доступные команды:</b>",
        "/rename_business — изменить название",
        "",
        "Более расширенные настройки добавляются позже.",
    ]

    await message.answer("\n".join(lines))


@router.message(Command("rename_business"))
async def cmd_rename_business(
    message: Message,
    state: FSMContext,
    business: Business | None = None,
) -> None:
    """
    Start rename business dialog.
    """

    if business is None:
        await message.answer(
            "Сначала отправь команду /start, чтобы я привязал твой профиль к заведению."
        )
        return

    await state.update_data(business_id=business.id)
    await state.set_state(UpdateBusinessNameStates.waiting_for_new_name)

    await message.answer(
        f"<b>Текущее название:</b> {business.name}\n\n"
        "Отправь <b>новое название</b> для заведения.\n\n"
        "Для отмены напиши /cancel."
    )


@router.message(UpdateBusinessNameStates.waiting_for_new_name, F.text.len() > 0)
async def rename_business_confirm(message: Message, state: FSMContext) -> None:
    new_name = message.text.strip()

    if len(new_name) < 2:
        await message.answer("Название должно быть длиной минимум 2 символа.")
        return

    if len(new_name) > 100:
        await message.answer("Название слишком длинное (максимум 100 символов).")
        return

    data = await state.get_data()
    business_id = data.get("business_id")

    if not business_id:
        await state.clear()
        await message.answer("Ошибка данных. Попробуй ещё раз.")
        return

    supabase = get_supabase_client()

    try:
        updated_business = await supabase.update_business_name(business_id, new_name)
        await state.clear()
        await message.answer(
            f"✅ Название обновлено!\n\n"
            f"<b>Новое название:</b> {updated_business.name}"
        )
    except Exception as exc:
        logger.exception("Failed to rename business: %s", exc)
        await state.clear()
        await message.answer("❌ Ошибка при обновлении названия.")


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
