from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.core.logging import configure_logging
from app.db import get_supabase_client
from app.db.models import Business, OwnerProfile


logger = configure_logging()


class BusinessContextMiddleware(BaseMiddleware):
    """
    Middleware that attaches current owner and business to handler data.

    Resolution is based on Telegram user id and Supabase lookup.
    Works for both Message and CallbackQuery events.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Handle both Message and CallbackQuery
        from_user = None
        if isinstance(event, Message):
            from_user = event.from_user
        elif isinstance(event, CallbackQuery):
            from_user = event.from_user

        if from_user:
            telegram_user_id = from_user.id
            supabase = get_supabase_client()
            try:
                owner_business = await supabase.get_owner_by_telegram(telegram_user_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to resolve business context: %s", exc)
                owner_business = None

            owner: OwnerProfile | None
            business: Business | None
            if owner_business is None:
                owner, business = None, None
            else:
                owner, business = owner_business

            data["owner"] = owner
            data["business"] = business

        return await handler(event, data)

