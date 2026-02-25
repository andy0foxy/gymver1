from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class OwnerProfile(BaseModel):
    # In the intended Supabase schema this is auth.users.id
    user_id: str
    telegram_user_id: int
    full_name: Optional[str] = None
    # Reminder settings
    reminder_enabled: bool = True
    reminder_hour: int = 10  # Hour of day (0-23) to send reminders
    reminder_days_before: int = 7  # How many days before expiration to remind
    timezone: str = "Europe/Moscow"  # User's timezone
    created_at: datetime


class Business(BaseModel):
    id: str
    owner_id: str
    name: str
    created_at: datetime


class Client(BaseModel):
    id: str
    business_id: str
    full_name: str
    phone: str
    created_at: datetime


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    FROZEN = "frozen"


class Subscription(BaseModel):
    id: str
    business_id: str
    client_id: str
    amount: Decimal
    currency: str
    start_date: date
    end_date: date
    status: SubscriptionStatus
    reminder_sent_at: Optional[datetime] = None  # Tracks when expiration reminder was sent
    created_at: datetime


class Payment(BaseModel):
    id: str
    business_id: str
    subscription_id: str
    amount: Decimal
    currency: str
    payment_date: date
    notes: Optional[str] = None
    created_at: datetime
