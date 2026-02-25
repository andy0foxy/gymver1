from __future__ import annotations

import secrets
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict

import httpx

from app.core import Settings, get_settings
from app.db.models import (
    Business,
    Client,
    OwnerProfile,
    Payment,
    Subscription,
    SubscriptionStatus,
)


class SupabaseError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, detail: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class SupabaseClient:
    """
    Minimal async Supabase REST client for the Telegram bot.

    For now we keep only the methods required by the bot.
    Service role key is used, so RLS is bypassed; access is restricted in code.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        base_url = str(self._settings.supabase_url).rstrip("/")
        self._rest = httpx.AsyncClient(
            base_url=f"{base_url}/rest/v1",
            headers={
                "apikey": self._settings.supabase_service_key,
                "Authorization": f"Bearer {self._settings.supabase_service_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=10.0,
        )
        self._auth_admin = httpx.AsyncClient(
            base_url=f"{base_url}/auth/v1",
            headers={
                "apikey": self._settings.supabase_service_key,
                "Authorization": f"Bearer {self._settings.supabase_service_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=10.0,
        )

    @property
    def http(self) -> httpx.AsyncClient:
        # Backwards compatibility if used elsewhere; points to REST client.
        return self._rest

    async def close(self) -> None:
        await self._rest.aclose()
        await self._auth_admin.aclose()

    async def _get_single_row(
        self,
        table: str,
        params: dict[str, Any],
    ) -> dict[str, Any] | None:
        response = await self._rest.get(
            f"/{table}",
            params={**params, "select": "*", "limit": 1},
        )
        if response.status_code >= 400:
            raise SupabaseError(
                f"Supabase REST GET failed for '{table}'",
                status_code=response.status_code,
                detail=response.text,
            )
        items: list[dict[str, Any]] = response.json()
        if not items:
            return None
        return items[0]

    async def _insert_row(
        self,
        table: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._rest.post(
            f"/{table}",
            json=payload,
            headers={"Prefer": "return=representation"},
        )
        if response.status_code >= 400:
            raise SupabaseError(
                f"Supabase REST INSERT failed for '{table}'",
                status_code=response.status_code,
                detail=response.text,
            )
        items: list[dict[str, Any]] = response.json()
        if not items:
            raise RuntimeError(f"Empty insert response for table '{table}'")
        return items[0]

    async def _create_auth_user_for_telegram(
        self,
        telegram_user_id: int,
        full_name: str | None,
    ) -> str:
        """
        Create a Supabase Auth user using admin endpoint.

        We use a deterministic email to guarantee uniqueness per Telegram user.
        Password is random; in MVP the owner interacts via Telegram, later
        we can link Telegram WebApp login and/or magic links.
        """

        email = f"tg_{telegram_user_id}@telegram.local"
        password = secrets.token_urlsafe(18)

        response = await self._auth_admin.post(
            "/admin/users",
            json={
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {
                    "full_name": full_name,
                    "telegram_user_id": telegram_user_id,
                },
            },
        )
        if response.status_code >= 400:
            raise SupabaseError(
                "Supabase Auth admin user creation failed",
                status_code=response.status_code,
                detail=response.text,
            )

        data: dict[str, Any] = response.json()
        user_id = data.get("id")
        if not user_id:
            raise SupabaseError("Supabase Auth admin response missing 'id'", detail=response.text)
        return str(user_id)

    async def get_owner_by_telegram(
        self,
        telegram_user_id: int,
    ) -> tuple[OwnerProfile, Business] | None:
        """
        Fetch owner profile and their primary business by Telegram user id.

        Expected Supabase schema (minimum):
        - table `owner_profiles` with columns:
          id (uuid), telegram_user_id (bigint, unique), full_name, timezone, created_at
        - table `businesses` with columns:
          id (uuid), owner_id (uuid), name, created_at
        """

        owner_row = await self._get_single_row(
            "owner_profiles",
            params={"telegram_user_id": f"eq.{telegram_user_id}"},
        )
        if owner_row is None:
            return None

        owner_user_id = owner_row.get("user_id") or owner_row.get("id")
        if not owner_user_id:
            raise SupabaseError("owner_profiles row missing user_id/id", detail=str(owner_row))

        business_row = await self._get_single_row(
            "businesses",
            params={"owner_id": f"eq.{owner_user_id}"},
        )
        if business_row is None:
            raise RuntimeError("Owner has no business associated")

        # Normalize schema variants: accept `id` as `user_id` if needed
        if "user_id" not in owner_row and "id" in owner_row:
            owner_row = {**owner_row, "user_id": owner_row["id"]}

        owner = OwnerProfile.model_validate(owner_row)
        business = Business.model_validate(business_row)
        return owner, business

    async def update_reminder_settings(
        self,
        owner_id: str,
        reminder_enabled: bool | None = None,
        reminder_hour: int | None = None,
        reminder_days_before: int | None = None,
        timezone: str | None = None,
    ) -> OwnerProfile:
        """
        Update reminder notification settings for an owner.
        """
        payload: dict[str, Any] = {}
        
        if reminder_enabled is not None:
            payload["reminder_enabled"] = reminder_enabled
        if reminder_hour is not None:
            payload["reminder_hour"] = reminder_hour
        if reminder_days_before is not None:
            payload["reminder_days_before"] = reminder_days_before
        if timezone is not None:
            payload["timezone"] = timezone

        if not payload:
            raise ValueError("At least one setting must be provided to update")

        response = await self._rest.patch(
            "/owner_profiles",
            json=payload,
            params={"user_id": f"eq.{owner_id}"},
        )
        if response.status_code >= 400:
            raise SupabaseError(
                "Failed to update reminder settings",
                status_code=response.status_code,
                detail=response.text,
            )

        updated_rows = response.json()
        if not updated_rows:
            raise SupabaseError("No owner found to update")

        return OwnerProfile.model_validate(updated_rows[0])

    async def create_owner_skeleton(
        self,
        telegram_user_id: int,
        full_name: str | None = None,
    ) -> tuple[OwnerProfile, Business]:
        """
        Create minimal owner record and a default business for this Telegram user.
        """

        user_id = await self._create_auth_user_for_telegram(
            telegram_user_id=telegram_user_id,
            full_name=full_name,
        )

        owner_payload: dict[str, Any] = {
            "user_id": user_id,
            "telegram_user_id": telegram_user_id,
            "full_name": full_name,
        }
        owner_row = await self._insert_row("owner_profiles", owner_payload)

        default_business_name = full_name or f"Business {telegram_user_id}"
        business_payload: dict[str, Any] = {
            "owner_id": user_id,
            "name": default_business_name,
        }
        business_row = await self._insert_row("businesses", business_payload)

        if "user_id" not in owner_row and "id" in owner_row:
            owner_row = {**owner_row, "user_id": owner_row["id"]}

        owner = OwnerProfile.model_validate(owner_row)
        business = Business.model_validate(business_row)
        return owner, business

    async def list_clients_for_business(self, business_id: str) -> list[Client]:
        """
        Return all clients for the given business ordered by creation time.
        """

        response = await self._rest.get(
            "/clients",
            params={
                "business_id": f"eq.{business_id}",
                "select": "*",
                "order": "created_at.asc",
            },
        )
        if response.status_code >= 400:
            raise SupabaseError(
                "Supabase REST GET failed for 'clients'",
                status_code=response.status_code,
                detail=response.text,
            )
        items: list[dict[str, Any]] = response.json()
        return [Client.model_validate(item) for item in items]

    async def create_client(
        self,
        *,
        business_id: str,
        full_name: str,
        phone: str,
    ) -> Client:
        payload: dict[str, Any] = {
            "business_id": business_id,
            "full_name": full_name,
            "phone": phone,
        }
        row = await self._insert_row("clients", payload)
        return Client.model_validate(row)

    async def create_subscription(
        self,
        *,
        business_id: str,
        client_id: str,
        amount: Decimal,
        currency: str,
        start_date: Any,
        end_date: Any,
        status: SubscriptionStatus,
    ) -> Subscription:
        """
        Create a new subscription for a client.
        """
        payload: dict[str, Any] = {
            "business_id": business_id,
            "client_id": client_id,
            "amount": str(amount),  # Decimal to string for JSON
            "currency": currency,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "status": status.value,
        }
        row = await self._insert_row("subscriptions", payload)
        return Subscription.model_validate(row)

    async def list_subscriptions_for_business(
        self,
        business_id: str,
    ) -> list[Subscription]:
        response = await self._rest.get(
            "/subscriptions",
            params={
                "business_id": f"eq.{business_id}",
                "select": "*",
                "order": "end_date.asc",
            },
        )
        if response.status_code >= 400:
            raise SupabaseError(
                "Supabase REST GET failed for 'subscriptions'",
                status_code=response.status_code,
                detail=response.text,
            )
        items: list[dict[str, Any]] = response.json()
        return [Subscription.model_validate(item) for item in items]

    async def list_subscriptions_for_client(
        self,
        client_id: str,
    ) -> list[Subscription]:
        """
        Return all subscriptions for a specific client, ordered by end date.
        """
        response = await self._rest.get(
            "/subscriptions",
            params={
                "client_id": f"eq.{client_id}",
                "select": "*",
                "order": "end_date.desc",
            },
        )
        if response.status_code >= 400:
            raise SupabaseError(
                "Supabase REST GET failed for 'subscriptions'",
                status_code=response.status_code,
                detail=response.text,
            )
        items: list[dict[str, Any]] = response.json()
        return [Subscription.model_validate(item) for item in items]

    async def get_subscription_stats_for_business(
        self,
        business_id: str,
    ) -> Dict[SubscriptionStatus, int]:
        """
        Return simple stats: count of subscriptions per status.
        """

        subs = await self.list_subscriptions_for_business(business_id)
        counter: Counter[str] = Counter(s.status for s in subs)
        return {
            status: counter.get(status.value, 0)
            for status in SubscriptionStatus
        }

    async def update_subscription_status(
        self,
        subscription_id: str,
        new_status: SubscriptionStatus,
    ) -> Subscription:
        """
        Update subscription status (active, expired, cancelled, frozen).
        """
        response = await self._rest.patch(
            f"/subscriptions",
            params={"id": f"eq.{subscription_id}"},
            json={"status": new_status.value},
            headers={"Prefer": "return=representation"},
        )
        if response.status_code >= 400:
            raise SupabaseError(
                "Failed to update subscription status",
                status_code=response.status_code,
                detail=response.text,
            )
        items: list[dict[str, Any]] = response.json()
        if not items:
            raise SupabaseError("Subscription not found", status_code=404)
        return Subscription.model_validate(items[0])

    async def renew_subscription(
        self,
        subscription_id: str,
        new_end_date: Any,
    ) -> Subscription:
        """
        Renew a subscription by extending end_date and setting status to ACTIVE.
        """
        response = await self._rest.patch(
            f"/subscriptions",
            params={"id": f"eq.{subscription_id}"},
            json={
                "end_date": str(new_end_date),
                "status": SubscriptionStatus.ACTIVE.value,
            },
            headers={"Prefer": "return=representation"},
        )
        if response.status_code >= 400:
            raise SupabaseError(
                "Failed to renew subscription",
                status_code=response.status_code,
                detail=response.text,
            )
        items: list[dict[str, Any]] = response.json()
        if not items:
            raise SupabaseError("Subscription not found", status_code=404)
        return Subscription.model_validate(items[0])

    async def extend_subscription(
        self,
        subscription_id: str,
        additional_days: int,
    ) -> Subscription:
        """
        Extend subscription by given number of days.
        """
        # Get current subscription
        response = await self._rest.get(
            "/subscriptions",
            params={
                "id": f"eq.{subscription_id}",
                "select": "*",
                "limit": 1,
            },
        )
        if response.status_code >= 400 or not response.json():
            raise SupabaseError("Subscription not found", status_code=404)
        
        current_sub = response.json()[0]
        current_end = date.fromisoformat(current_sub["end_date"])
        new_end = current_end + timedelta(days=additional_days)
        
        return await self.renew_subscription(subscription_id, new_end)

    async def search_clients_by_name(
        self,
        business_id: str,
        name_query: str,
    ) -> list[Client]:
        """
        Search clients by name (case-insensitive partial match).
        """
        response = await self._rest.get(
            "/clients",
            params={
                "business_id": f"eq.{business_id}",
                "full_name": f"ilike.%{name_query}%",
                "select": "*",
                "order": "created_at.asc",
            },
        )
        if response.status_code >= 400:
            raise SupabaseError(
                "Failed to search clients by name",
                status_code=response.status_code,
                detail=response.text,
            )
        items: list[dict[str, Any]] = response.json()
        return [Client.model_validate(item) for item in items]

    async def search_clients_by_phone(
        self,
        business_id: str,
        phone_query: str,
    ) -> list[Client]:
        """
        Search clients by phone (case-insensitive partial match).
        """
        response = await self._rest.get(
            "/clients",
            params={
                "business_id": f"eq.{business_id}",
                "phone": f"ilike.%{phone_query}%",
                "select": "*",
                "order": "created_at.asc",
            },
        )
        if response.status_code >= 400:
            raise SupabaseError(
                "Failed to search clients by phone",
                status_code=response.status_code,
                detail=response.text,
            )
        items: list[dict[str, Any]] = response.json()
        return [Client.model_validate(item) for item in items]

    async def get_client_with_subscriptions(
        self,
        client_id: str,
    ) -> tuple[Client, list[Subscription]]:
        """
        Get client details along with all their subscriptions.
        """
        response = await self._rest.get(
            "/clients",
            params={
                "id": f"eq.{client_id}",
                "select": "*",
                "limit": 1,
            },
        )
        if response.status_code >= 400 or not response.json():
            raise SupabaseError("Client not found", status_code=404)
        
        client = Client.model_validate(response.json()[0])
        subs = await self.list_subscriptions_for_client(client_id)
        return client, subs

    async def list_expiring_subscriptions(
        self,
        business_id: str,
        days_until: int = 7,
    ) -> list[Subscription]:
        """
        Get subscriptions expiring within N days (for reminders).
        Only returns subscriptions that:
        - Are ACTIVE
        - Expire within days_until days
        - Have NOT had a reminder sent yet (reminder_sent_at IS NULL)
        """
        today = date.today()
        cutoff_date = today + timedelta(days=days_until)
        
        subs = await self.list_subscriptions_for_business(business_id)
        return [
            s for s in subs
            if s.status == SubscriptionStatus.ACTIVE
            and today <= s.end_date <= cutoff_date
            and s.reminder_sent_at is None  # Only if reminder not yet sent
        ]

    async def mark_reminder_sent(
        self,
        subscription_id: str,
    ) -> Subscription:
        """
        Mark that a reminder was sent for this subscription.
        Sets reminder_sent_at to current timestamp.
        """
        response = await self._rest.patch(
            "/subscriptions",
            json={"reminder_sent_at": datetime.now().isoformat()},
            params={"id": f"eq.{subscription_id}"},
        )
        if response.status_code >= 400:
            raise SupabaseError(
                "Failed to mark reminder as sent",
                status_code=response.status_code,
                detail=response.text,
            )
        
        updated_rows = response.json()
        if not updated_rows:
            raise SupabaseError("Subscription not found to update")
        
        return Subscription.model_validate(updated_rows[0])

    async def create_payment(
        self,
        *,
        business_id: str,
        subscription_id: str,
        amount: Decimal,
        currency: str,
        payment_date: Any,
        notes: str | None = None,
    ) -> Payment:
        """
        Record a payment for a subscription.
        """
        payload: dict[str, Any] = {
            "business_id": business_id,
            "subscription_id": subscription_id,
            "amount": str(amount),
            "currency": currency,
            "payment_date": str(payment_date),
        }
        if notes:
            payload["notes"] = notes
        
        row = await self._insert_row("payments", payload)
        return Payment.model_validate(row)

    async def list_payments_for_subscription(
        self,
        subscription_id: str,
    ) -> list[Payment]:
        """
        Get all payments for a subscription.
        """
        response = await self._rest.get(
            "/payments",
            params={
                "subscription_id": f"eq.{subscription_id}",
                "select": "*",
                "order": "payment_date.desc",
            },
        )
        if response.status_code >= 400:
            raise SupabaseError(
                "Failed to list payments",
                status_code=response.status_code,
                detail=response.text,
            )
        items: list[dict[str, Any]] = response.json()
        return [Payment.model_validate(item) for item in items]

    async def list_payments_for_business(
        self,
        business_id: str,
    ) -> list[Payment]:
        """
        Get all payments for a business.
        """
        response = await self._rest.get(
            "/payments",
            params={
                "business_id": f"eq.{business_id}",
                "select": "*",
                "order": "payment_date.desc",
            },
        )
        if response.status_code >= 400:
            raise SupabaseError(
                "Failed to list business payments",
                status_code=response.status_code,
                detail=response.text,
            )
        items: list[dict[str, Any]] = response.json()
        return [Payment.model_validate(item) for item in items]

    async def get_subscription_revenue_stats(
        self,
        business_id: str,
    ) -> Dict[str, Decimal]:
        """
        Get revenue stats: total, this month, monthly average.
        """
        payments = await self.list_payments_for_business(business_id)
        
        today = date.today()
        month_start = today.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        total_revenue = Decimal(0)
        month_revenue = Decimal(0)
        
        for payment in payments:
            total_revenue += payment.amount
            if month_start <= payment.payment_date <= month_end:
                month_revenue += payment.amount
        
        # Average per month
        if payments:
            first_payment = min(p.payment_date for p in payments)
            months_active = (today - first_payment).days / 30.44  # avg days per month
            avg_monthly = total_revenue / max(1, Decimal(str(months_active)))
        else:
            avg_monthly = Decimal(0)
        
        return {
            "total": total_revenue,
            "this_month": month_revenue,
            "avg_monthly": avg_monthly,
        }

    async def update_business_name(
        self,
        business_id: str,
        new_name: str,
    ) -> Business:
        """
        Update business name.
        """
        response = await self._rest.patch(
            f"/businesses",
            params={"id": f"eq.{business_id}"},
            json={"name": new_name},
            headers={"Prefer": "return=representation"},
        )
        if response.status_code >= 400:
            raise SupabaseError(
                "Failed to update business",
                status_code=response.status_code,
                detail=response.text,
            )
        items: list[dict[str, Any]] = response.json()
        if not items:
            raise SupabaseError("Business not found", status_code=404)
        return Business.model_validate(items[0])


_supabase_client: SupabaseClient | None = None


def get_supabase_client() -> SupabaseClient:
    """
    Lazy singleton for SupabaseClient.

    In async code we should eventually add proper startup/shutdown hooks
    to close the underlying HTTP client gracefully.
    """

    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient()
    return _supabase_client

