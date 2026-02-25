# GymCRM - Telegram Bot Documentation

**Complete reference guide for the GymCRM Telegram Bot** - A comprehensive CRM system for gym/fitness business management via Telegram.

**Last Updated:** February 25, 2026  
**Version:** 1.0.0

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Technology Stack](#technology-stack)
4. [Project Structure](#project-structure)
5. [Database](#database)
6. [Core Components](#core-components)
7. [Handlers & Commands](#handlers--commands)
8. [UI Components](#ui-components)
9. [Configuration](#configuration)
10. [Deployment](#deployment)
11. [Features](#features)
12. [API Reference](#api-reference)

---

## Project Overview

**GymCRM** is a Telegram-based CRM application designed for gym and fitness business owners to manage:

- **Clients** - Add, search, and view detailed client information
- **Subscriptions** - Create, renew, cancel, and freeze subscriptions with automatic reminders
- **Payments** - Record and track payments with revenue statistics
- **Reports** - View analytics, revenue data, and expiring subscriptions
- **Business Settings** - Manage business information and reminder preferences
- **Exports** - Export clients, subscriptions, and payments to CSV

### Key Features

✅ **Multi-user Support** - Each gym owner maintains their own business profile  
✅ **Automatic Reminders** - Configurable hourly reminders for expiring subscriptions  
✅ **One-time Reminder Tracking** - Reminders sent exactly once per subscription  
✅ **Button-based UI** - Intuitive inline keyboard navigation  
✅ **Database Persistence** - Supabase PostgreSQL backend  
✅ **Async Processing** - Full async/await support with APScheduler for background tasks  

---

## Architecture

### System Design

```
┌─────────────────────────────────────────────────────────┐
│                  Telegram User                          │
└─────────────────────────────────────────────────────────┘
                           │
                    Message/Callback
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              aiogram 3.x Dispatcher                      │
│  ┌──────────────────────────────────────────────────┐   │
│  │  BusinessContextMiddleware                       │   │
│  │  - Injects owner & business context             │   │
│  │  - Runs for Message & CallbackQuery events      │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Handlers      FSM States    Message Routers
         (Commands)    (Dialogs)     (Callbacks)
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────▼──────┐
                    │ Supabase DB │
                    │ PostgreSQL  │
                    └─────────────┘

Background:
┌─────────────────────────────────────────────────────────┐
│        APScheduler (Subscription Reminders)             │
│  - Runs hourly reminder checks                         │
│  - Respects individual user settings                   │
│  - Tracks sent reminders in database                   │
└─────────────────────────────────────────────────────────┘
```

### Request Flow

1. User sends message or taps button → Telegram API
2. Dispatcher receives event
3. **Middleware** extracts user context, fetches owner/business from DB
4. **Handler** receives request with business context injected
5. Handler queries database, formats response
6. Bot sends message/edit with optional keyboard
7. For long-running tasks: **Scheduler** handles in background

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Bot Framework** | aiogram 3.x | Telegram bot API wrapper |
| **Database** | Supabase (PostgreSQL) | Persistent data storage |
| **HTTP Client** | httpx | Async REST calls to Supabase |
| **Scheduler** | APScheduler | Hourly reminder jobs |
| **Models** | Pydantic v2 | Data validation & serialization |
| **Logging** | Python logging | Application logging |
| **Settings** | python-dotenv | Configuration management |

### Python Version

- **Python 3.9+** required
- **aiogram 3.x** (async/await support)

---

## Project Structure

```
gymver1/
├── README.md
├── requirements.txt
├── DOCUMENTATION.md              ← You are here
│
├── app/
│   ├── __init__.py
│   │
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── main.py              # Bot entry point, dispatcher setup
│   │   ├── keyboards.py         # UI components (buttons, formatters)
│   │   ├── scheduler.py         # APScheduler for reminders
│   │   │
│   │   ├── handlers/            # Message/command handlers
│   │   │   ├── __init__.py
│   │   │   ├── start.py         # /start, /menu, /help
│   │   │   ├── menu.py          # All callback button handlers
│   │   │   ├── add_client.py    # /add_client, client creation dialogs
│   │   │   ├── clients.py       # /clients command
│   │   │   ├── client_details.py # /client_info, /search, /view_client
│   │   │   ├── subscriptions.py # /add_subscription, /subscriptions
│   │   │   ├── edit_subscriptions.py # /renew, /cancel_sub, /freeze
│   │   │   ├── payments.py      # /payment, payment recording
│   │   │   ├── report.py        # /report, /revenue, /summary, /statistics
│   │   │   ├── reports.py       # Extended reporting commands
│   │   │   ├── business_settings.py # /settings, /rename_business
│   │   │   ├── reminders.py     # /remind, /remind3 commands
│   │   │   └── export.py        # /export_clients, /export_subscriptions, etc
│   │   │
│   │   └── middlewares/          # Request processing middleware
│   │       ├── __init__.py
│   │       └── business_context.py # Injects owner/business context
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # Settings & configuration
│   │   ├── logging.py           # Logging setup
│   │   └── validation.py        # Input validation helpers
│   │
│   └── db/
│       ├── __init__.py
│       ├── models.py            # Pydantic data models
│       └── supabase.py          # Database client & methods
│
└── .env                         # Environment variables (not in repo)
    SUPABASE_URL=...
    SUPABASE_SERVICE_KEY=...
    BOT_TOKEN=...
```

---

## Database

### Supabase Schema

The application expects the following PostgreSQL tables in Supabase:

#### 1. `owner_profiles` Table

Stores gym owner/user profiles and reminder preferences.

```sql
CREATE TABLE owner_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE,           -- Auth user ID
    telegram_user_id BIGINT NOT NULL UNIQUE, -- Telegram user ID
    full_name TEXT,                         -- Owner's name
    reminder_enabled BOOLEAN DEFAULT TRUE,  -- Reminders on/off
    reminder_hour INT DEFAULT 10,           -- Hour to send (0-23)
    reminder_days_before INT DEFAULT 7,     -- Days before expiration
    timezone TEXT DEFAULT 'Europe/Moscow',  -- User's timezone
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Fields:**
- `id` - UUID primary key
- `user_id` - Links to auth.users
- `telegram_user_id` - Unique Telegram identifier
- `full_name` - Owner's display name
- `reminder_enabled` - Boolean to enable/disable automated reminders
- `reminder_hour` - Hour (0-23) when to send reminders
- `reminder_days_before` - Days before subscription expiration to remind
- `timezone` - Owner's timezone for scheduling
- `created_at` - Account creation timestamp

#### 2. `businesses` Table

Stores gym/business information under each owner.

```sql
CREATE TABLE businesses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL REFERENCES owner_profiles(user_id) ON DELETE CASCADE,
    name TEXT NOT NULL,                     -- Business name (gym name)
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Fields:**
- `id` - UUID primary key
- `owner_id` - Foreign key to owner_profiles
- `name` - Business name (e.g., "PowerGym", "FitBox")
- `created_at` - Business creation timestamp

#### 3. `clients` Table

Stores individual gym members/clients.

```sql
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,                -- Client's name
    phone TEXT,                             -- Contact phone
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Fields:**
- `id` - UUID primary key
- `business_id` - Which business this client belongs to
- `full_name` - Client's name
- `phone` - Contact phone number
- `created_at` - Account creation timestamp

#### 4. `subscriptions` Table

Stores gym memberships with status tracking and reminder history.

```sql
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    amount DECIMAL(10,2) NOT NULL,          -- Subscription cost
    currency TEXT DEFAULT 'RUB',            -- Currency code
    subscription_type TEXT DEFAULT 'basic', -- Membership type
    start_date DATE NOT NULL,               -- Membership start date
    end_date DATE NOT NULL,                 -- Membership expiration date
    status TEXT DEFAULT 'active',           -- active|expired|cancelled|frozen
    reminder_sent_at TIMESTAMP,             -- When expiration reminder was sent
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Fields:**
- `id` - UUID primary key
- `business_id` - Which business this subscription belongs to
- `client_id` - Which client this subscription is for
- `amount` - Price (e.g., 5000.00)
- `currency` - Currency code (e.g., 'RUB')
- `subscription_type` - Type of membership (basic, premium, etc)
- `start_date` - When membership started
- `end_date` - When membership expires
- `status` - Current status (active/expired/cancelled/frozen)
- `reminder_sent_at` - Timestamp when expiration reminder was sent (NULL = not sent yet)
- `created_at` - Subscription creation timestamp

#### 5. `payments` Table

Records financial transactions.

```sql
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,
    amount DECIMAL(10,2) NOT NULL,          -- Payment amount
    currency TEXT DEFAULT 'RUB',
    payment_date DATE NOT NULL,             -- When payment was made
    notes TEXT,                             -- Payment notes/description
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Fields:**
- `id` - UUID primary key
- `business_id` - Which business received payment
- `subscription_id` - Which subscription this payment is for (nullable)
- `amount` - Payment amount (e.g., 5000.00)
- `currency` - Currency code
- `payment_date` - Date of payment
- `notes` - Optional notes (e.g., "Late payment", "Partial payment")
- `created_at` - Record creation timestamp

### Subscription Status Enum

```python
class SubscriptionStatus(str, Enum):
    ACTIVE = "active"          # Current, not yet expired
    EXPIRED = "expired"        # Past end_date, not renewed
    CANCELLED = "cancelled"    # Actively terminated by owner
    FROZEN = "frozen"          # Paused, can be resumed
```

---

## Core Components

### 1. Middleware: BusinessContextMiddleware

**File:** `app/bot/middlewares/business_context.py`

Injects the current owner and business context into every handler.

```python
class BusinessContextMiddleware(BaseMiddleware):
    """
    Injects owner and business context from Supabase.
    Runs for both Message and CallbackQuery events.
    """
```

**How it works:**

1. Intercepts every Message and CallbackQuery event
2. Extracts `telegram_user_id` from `message.from_user` or `callback_query.from_user`
3. Calls `supabase.get_owner_by_telegram(telegram_user_id)`
4. Injects `owner: OwnerProfile` and `business: Business` into handler data
5. Handler receives as: `async def handler(message: Message, business: Business | None = None)`

**Example:**
```python
@router.message(Command("clients"))
async def cmd_clients(message: Message, business: Business | None = None) -> None:
    if business is None:
        await message.answer("Please run /start first")
        return
    # business is now available and injected by middleware
```

**Registration in main.py:**
```python
dp.message.middleware(BusinessContextMiddleware())  # For text messages
dp.callback_query.middleware(BusinessContextMiddleware())  # For button clicks
```

---

### 2. Scheduler: SubscriptionReminderScheduler

**File:** `app/bot/scheduler.py`

Background job scheduler for sending subscription expiration reminders using APScheduler.

```python
class SubscriptionReminderScheduler:
    """
    APScheduler manager for subscription reminders.
    Sends hourly reminder checks respecting individual user settings.
    """
```

**How it works:**

1. **Hourly Job**: Runs every hour at `:00` (e.g., 10:00, 11:00, etc)
2. **User Filtering**: Fetches all owners with `reminder_enabled = true`
3. **Time Matching**: Checks if current hour matches owner's `reminder_hour` setting
4. **Expiration Check**: Gets subscriptions expiring in exactly `reminder_days_before` days
5. **One-time Tracking**: Only sends if `reminder_sent_at IS NULL`
6. **Mark as Sent**: Updates `reminder_sent_at` with current timestamp after sending

**Example Timeline:**

User sets: "Remind at 10:00 AM, 7 days before"
Subscription end date: Feb 25, 2026

```
Feb 18, 10:00 AM (7 days before)  → ✅ Reminder sent, reminder_sent_at = "2026-02-18 10:00:00"
Feb 18, 11:00 AM                  → ❌ Already sent (reminder_sent_at != NULL)
Feb 19, 10:00 AM                  → ❌ Already sent
Feb 25, 10:00 AM                  → ❌ Status changed to "expired" or not within range
```

**Key Methods:**

- `start()` - Initializes and starts the scheduler
- `stop()` - Gracefully shuts down the scheduler
- `_send_hourly_reminders()` - Hourly job that checks for due reminders
- `send_reminder_for_business()` - Sends reminder message and tracks it

**Usage in main.py:**
```python
scheduler = get_reminder_scheduler(bot)
await scheduler.start()
# ... bot runs ...
await scheduler.stop()  # On shutdown
```

---

## Handlers & Commands

### Handler Organization

Handlers are organized into router modules, each handling specific features:

| Module | Purpose | RouteR | Commands |
|--------|---------|--------|----------|
| `start.py` | Initialization & help | start | /start, /menu, /help |
| `menu.py` | Button navigation | menu | Callback handlers for all buttons |
| `add_client.py` | Add new client dialog | add_client | /add_client |
| `clients.py` | List clients | clients | /clients |
| `client_details.py` | Client information | client_details | /client_info, /search, /view_client |
| `subscriptions.py` | Add subscriptions | subscriptions | /add_subscription |
| `edit_subscriptions.py` | Manage subscriptions | edit_subscriptions | /renew, /cancel_sub, /freeze |
| `payments.py` | Record payments | payments | /payment |
| `report.py` | Basic statistics | report | /report |
| `reports.py` | Advanced analytics | reports | /revenue, /summary |
| `business_settings.py` | Business management | business_settings | /settings, /rename_business |
| `reminders.py` | Manual reminders | reminders | /remind, /remind3 |
| `export.py` | Data export | export | /export_clients, /export_subscriptions, /export_payments |

All routers are combined in `app/bot/handlers/__init__.py`:

```python
def setup_routers() -> Router:
    router = Router(name="root")
    router.include_router(start.router)
    router.include_router(menu.router)
    # ... all other routers
    return router
```

---

### Command Reference

#### 🔧 Account & Help

**`/start`**  
Initializes user profile and creates default business.
- **New users**: Creates owner_profiles and businesses entries
- **Returning users**: Shows welcome message with business info
- **Output**: Main menu with button navigation

**`/menu`**  
Shows main menu with button buttons.
- Same as first message after /start
- **Buttons**: Clients, Subscriptions, Payments, Reports, Settings, Help

**`/help`**  
Shows complete command reference and usage guide.

---

#### 👥 Client Management

**`/add_client`**  
Start adding a new client (3-step process):
1. Bot asks for full name → user types name
2. Bot asks for phone → user types phone number
3. Confirmation → client created in database

**`/clients`**  
List all clients for current business.
- Shows first 20 clients with names and phone numbers
- Updates automatically

**`/client_info`**  
Get detailed info about a specific client.
- Shows client name, phone, all subscriptions

**`/search [query]`**  
Search clients by name or phone.
- Usage: `/search John` or `/search +79990000000`

---

#### 💳 Subscription Management

**`/add_subscription`** (via button)  
Add subscription to client (4-step process):
1. Tap "➕ Новый абонемент" button
2. Select client from list (type number)
3. Enter subscription days (type number)
4. Confirmation → subscription created

**`/subscriptions`** (via button)  
List all subscriptions with status summary.
- Shows counts: Active, Expired, Frozen, Cancelled

**`/renew`** (via button)  
Renew an existing subscription.

**`/cancel_sub`** (via button)  
Cancel a subscription (sets status = "cancelled").

**`/freeze`** (via button)  
Freeze/pause a subscription (sets status = "frozen").

---

#### 💰 Payment Management

**`/payment`** (via button)  
Record a payment (2-step process):
1. Select client number
2. Select subscription for payment
3. Confirmation → payment recorded

---

#### 📊 Reports & Analytics

**`/report`** (via button)  
Full business report:
- Total clients count
- Subscriptions by status (active/expired/cancelled/frozen)
- Revenue this month
- Updated timestamp

**`/summary`** (via button)  
Quick dashboard:
- Active subscriptions percentage
- Current month revenue

**`/revenue`** (via button)  
Detailed revenue report:
- Total revenue (all-time)
- This month's revenue
- Average monthly revenue
- Payment count

**`/expiring_report`** (via button)  
Subscriptions expiring in next 7 days.
- Client names with days remaining
- Used for manual reminder checks

---

#### 📥 Export & Backup

**`/export_clients`**  
Download all clients as CSV file.
- Columns: ID, Name, Phone, Created Date

**`/export_subscriptions`**  
Download all subscriptions as CSV file.
- Columns: ID, Client, Status, Start Date, End Date, Amount

**`/export_payments`**  
Download all payments as CSV file.
- Columns: ID, Amount, Date, Notes

---

#### ⚙️ Settings & Configuration

**`/settings`**  
Show current business settings.
- Business name, ID, creation date

**`/rename_business`** (via button)  
Change business name (1-step dialog):
1. Tap "📝 Изменить название" button
2. Type new name
3. Confirmation → name updated in database

**🔔 Reminder Setup** (via button)  
Configure automatic reminders (2-step dialog):
1. Tap "🔔 Напоминания" button
2. Type hour (0-23) → "10" for 10:00 AM
3. Type days before (1-30) → "7" for one week before
4. Settings saved, scheduler will use them

---

#### 🔔 Manual Reminders

**`/remind`**  
Immediately send reminder for subscriptions expiring in 7 days.
- Same as scheduled reminder but sent on-demand

**`/remind3`**  
Immediately send reminder for subscriptions expiring in 3 days.
- Used for more urgent reminders

---

#### ❌ Other

**`/cancel`**  
Cancel current dialog/operation.
- Works in any active conversation

---

## UI Components

### File: `app/bot/keyboards.py`

Centralized UI component builder providing consistent, professional-looking buttons and formatting.

#### Keyboards Class

Provides static methods returning `InlineKeyboardMarkup` objects with button layouts.

**Methods:**

```python
@staticmethod
def main_menu() -> InlineKeyboardMarkup:
    """
    Main menu with 6 buttons:
    ┌─────────────────────────────────┐
    │ 👥 Клиенты │ 💳 Абонементы     │
    │ 💰 Платежи │ 📊 Отчёты         │
    │ ⚙️ Настройки │ ❓ Справка       │
    └─────────────────────────────────┘
    """
```

```python
@staticmethod
def clients_menu() -> InlineKeyboardMarkup:
    """
    Clients submenu:
    ┌─────────────────────────────────┐
    │ ➕ Добавить клиента             │
    │ 📋 Все клиенты                  │
    │ 🔍 Поиск клиента                │
    │ ⬅️ Назад                        │
    └─────────────────────────────────┘
    """
```

```python
@staticmethod
def subscriptions_menu() -> InlineKeyboardMarkup:
    """
    Subscriptions submenu:
    ┌─────────────────────────────────┐
    │ ➕ Новый абонемент              │
    │ 📋 Все абонементы               │
    │ 🔄 Продлить                     │
    │ ❌ Отменить                     │
    │ 🧊 Заморозить                   │
    │ ⬅️ Назад                        │
    └─────────────────────────────────┘
    """
```

```python
@staticmethod
def payments_menu() -> InlineKeyboardMarkup:
    """
    Payments submenu:
    ┌─────────────────────────────────┐
    │ ➕ Новый платёж                 │
    │ 📋 История платежей             │
    │ 💹 Статистика                   │
    │ ⬅️ Назад                        │
    └─────────────────────────────────┘
    """
```

```python
@staticmethod
def reports_menu() -> InlineKeyboardMarkup:
    """
    Reports submenu:
    ┌─────────────────────────────────┐
    │ 📊 Полный отчёт                │
    │ 📈 Краткая сводка               │
    │ 💰 Доходы                       │
    │ ⏰ Скоро истекло                │
    │ ⬅️ Назад                        │
    └─────────────────────────────────┘
    """
```

```python
@staticmethod
def settings_menu() -> InlineKeyboardMarkup:
    """
    Settings submenu:
    ┌─────────────────────────────────┐
    │ 📝 Изменить название            │
    │ 📥 Экспорт данных               │
    │ 🔔 Напоминания                  │
    │ ℹ️ О заведении                  │
    │ ⬅️ Назад                        │
    └─────────────────────────────────┘
    """
```

```python
@staticmethod
def export_menu() -> InlineKeyboardMarkup:
    """
    Export submenu:
    ┌─────────────────────────────────┐
    │ 📄 Клиенты (CSV)               │
    │ 📄 Абонементы (CSV)            │
    │ 📄 Платежи (CSV)               │
    │ ⬅️ Назад                        │
    └─────────────────────────────────┘
    """
```

```python
@staticmethod
def back_button(callback_data: str = "menu_main") -> InlineKeyboardMarkup:
    """Single back button that goes to specified menu."""
```

```python
@staticmethod
def confirm_button(action_text: str = "Подтвердить") -> InlineKeyboardMarkup:
    """Confirmation buttons: ✅ Yes | ❌ Cancel"""
```

#### MessageTemplates Class

Provides static methods for consistent message formatting.

**Methods:**

```python
@staticmethod
def header(title: str, emoji: str = "📋") -> str:
    """Format a header: "\n<b>📋 Title</b>\n" """

@staticmethod
def section(title: str, emoji: str = "•") -> str:
    """Format a section: "\n<b>• Section</b>" """

@staticmethod
def item(text: str, indent: int = 1) -> str:
    """Format list item: "  • text" """

@staticmethod
def divider() -> str:
    """Return separator: "────────────────────────────────────" """

@staticmethod
def error(message: str) -> str:
    """Format error: "❌ <b>Ошибка:</b> message" """

@staticmethod
def success(message: str) -> str:
    """Format success: "✅ <b>Готово!</b> message" """

@staticmethod
def info(message: str) -> str:
    """Format info: "ℹ️ message" """

@staticmethod
def warning(message: str) -> str:
    """Format warning: "⚠️ <b>Внимание:</b> message" """

@staticmethod
def stat(label: str, value: str, unit: str = "") -> str:
    """Format statistic: "  <b>Label:</b> value unit" """

@staticmethod
def format_date(date_obj) -> str:
    """Format date as code: "<code>2026-02-25</code>" """
```

**Usage Examples:**

```python
# In a handler:
text = (
    f"{MessageTemplates.header('Клиенты', '👥')}\n"
    f"{MessageTemplates.item('Alice - +79990000001')}\n"
    f"{MessageTemplates.item('Bob - +79990000002')}\n"
)
await message.answer(text, parse_mode="HTML")

# Produces:
# 👥 Клиенты
# • Alice - +79990000001
# • Bob - +79990000002
```

---

## Configuration

### Environment Variables

Create a `.env` file in project root:

```env
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGc...  # Service role key (not anon key!)

# Bot Token
BOT_TOKEN=123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefg

# Environment (development|production)
ENVIRONMENT=development
IS_DEBUG=true
```

### Settings Class

**File:** `app/core/config.py`

```python
class Settings:
    bot_token: str              # Telegram bot token
    supabase_url: str          # Supabase project URL
    supabase_service_key: str  # Supabase service role key
    environment: str           # "development" or "production"
    is_debug: bool             # Debug mode (logging)
```

Access settings globally:
```python
from app.core import get_settings
settings = get_settings()
print(settings.bot_token)
print(settings.is_debug)
```

---

## Deployment

### Local Development

1. **Clone repository**
```bash
cd gymver1
```

2. **Create virtual environment**
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Create `.env` file** with your credentials

5. **Run bot**
```bash
python -m app.bot.main
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "app.bot.main"]
```

### Production Considerations

- Use webhook instead of polling for scalability
- Run multiple scheduler instances with distributed locking
- Implement monitoring/alerting for bot health
- Add database backups with Supabase replication
- Use secrets manager for sensitive config
- Implement rate limiting per user
- Add audit logging for data modifications

---

## Features

### 1. Client Management

**Overview**: Full CRUD operations for gym members.

**Features:**
- Add new clients with name and phone
- List all clients with pagination
- Search by name or phone number
- View detailed client profile with subscription history
- Automatic phone number validation

**Database**: Stored in `clients` table

---

### 2. Subscription Management

**Overview**: Create and manage gym memberships.

**Features:**
- Create subscriptions with start/end dates
- Set subscription amount and currency
- Track subscription status (active/expired/cancelled/frozen)
- Renew expiring subscriptions
- Freeze/unfreeze subscriptions temporarily
- Cancel subscriptions permanently
- Automatic expiration detection

**Statuses:**
- `ACTIVE` - Current, not expired
- `EXPIRED` - Past end date
- `CANCELLED` - Terminated
- `FROZEN` - Paused

**Database**: Stored in `subscriptions` table

---

### 3. Automatic Reminders

**Overview**: Intelligent reminder system respecting user preferences.

**How it works:**
1. Users set reminder time (e.g., "10:00 AM") and advance notice (e.g., "7 days")
2. APScheduler checks hourly for due reminders
3. Only sends to users whose reminder_hour matches current hour
4. Only reminds for subscriptions expiring in exactly N days
5. Marks reminder as sent to prevent duplicates

**Features:**
- Configurable reminder time (hourly granularity)
- Configurable advance notice (1-30 days)
- One-time reminder per subscription
- Per-user settings
- Manual reminder commands for immediate testing
- Graceful shutdown and background job management

**Database**: 
- Settings in `owner_profiles.reminder_*` fields
- Tracking in `subscriptions.reminder_sent_at` field

---

### 4. Payment Tracking

**Overview**: Record and track gym revenue.

**Features:**
- Record payments against subscriptions
- Add payment notes/descriptions
- Track payment date and amount
- Generate revenue reports
- Filter payments by period (monthly reports)

**Database**: Stored in `payments` table

---

### 5. Analytics & Reports

**Overview**: Business intelligence and insights.

**Available Reports:**
- **Full Report**: Total clients, subscriptions by status, monthly revenue
- **Summary**: Quick dashboard (active % and revenue)
- **Revenue**: Total revenue, monthly revenue, average monthly
- **Expiring**: List subscriptions expiring within 7 days
- **Statistics**: Client count, subscription count, status breakdown

**Database Queries:**
- Efficient SQL filtering for status summaries
- DATE arithmetic for monthly calculations
- COUNT aggregations for statistics

---

### 6. Data Export

**Overview**: Backup and export business data.

**Formats:** CSV

**Exports:**
- All clients with details
- All subscriptions with dates/amounts
- All payments with dates/notes

**Usage:**
```
/export_clients     → Downloads CSV with all clients
/export_subscriptions → Downloads CSV with all subscriptions
/export_payments    → Downloads CSV with all payments
```

---

### 7. Business Settings

**Overview**: Manage business profile and preferences.

**Features:**
- View business name and ID
- Rename business
- Configure reminder settings (time + advance notice)
- View business creation date
- See current owner profile

---

## API Reference

### Data Models

All models use Pydantic v2 for validation and serialization.

#### OwnerProfile

```python
class OwnerProfile(BaseModel):
    user_id: str
    telegram_user_id: int
    full_name: Optional[str] = None
    reminder_enabled: bool = True
    reminder_hour: int = 10
    reminder_days_before: int = 7
    timezone: str = "Europe/Moscow"
    created_at: datetime
```

#### Business

```python
class Business(BaseModel):
    id: str
    owner_id: str
    name: str
    created_at: datetime
```

#### Client

```python
class Client(BaseModel):
    id: str
    business_id: str
    full_name: str
    phone: str
    created_at: datetime
```

#### Subscription

```python
class Subscription(BaseModel):
    id: str
    business_id: str
    client_id: str
    amount: Decimal
    currency: str
    start_date: date
    end_date: date
    status: SubscriptionStatus
    reminder_sent_at: Optional[datetime] = None
    created_at: datetime
```

#### Payment

```python
class Payment(BaseModel):
    id: str
    business_id: str
    subscription_id: str
    amount: Decimal
    currency: str
    payment_date: date
    notes: Optional[str] = None
    created_at: datetime
```

---

### Supabase Client Methods

**File:** `app/db/supabase.py`

#### Authentication

```python
async def get_owner_by_telegram(telegram_user_id: int) 
    -> tuple[OwnerProfile, Business] | None
    """Fetch owner and business by Telegram user ID."""

async def create_owner_skeleton(
    telegram_user_id: int,
    full_name: str | None = None,
) -> tuple[OwnerProfile, Business]
    """Create new owner profile with default business."""
```

#### Owner Management

```python
async def update_reminder_settings(
    owner_id: str,
    reminder_enabled: bool | None = None,
    reminder_hour: int | None = None,
    reminder_days_before: int | None = None,
    timezone: str | None = None,
) -> OwnerProfile
    """Update owner's reminder preferences."""

async def get_owner_by_user_id(user_id: str) -> OwnerProfile
    """Get owner profile by user ID."""
```

#### Client Operations

```python
async def list_clients_for_business(business_id: str) -> list[Client]
    """Get all clients for a business."""

async def create_client(
    business_id: str,
    full_name: str,
    phone: str,
) -> Client
    """Create new client."""

async def search_clients_by_name(
    business_id: str,
    name_query: str,
) -> list[Client]
    """Search clients by name (case-insensitive)."""

async def search_clients_by_phone(
    business_id: str,
    phone_query: str,
) -> list[Client]
    """Search clients by phone number."""

async def get_client_with_subscriptions(
    client_id: str,
) -> tuple[Client, list[Subscription]]
    """Get client and all their subscriptions."""
```

#### Subscription Operations

```python
async def create_subscription(
    business_id: str,
    client_id: str,
    subscription_type: str,
    start_date: date,
    end_date: date,
    amount: Decimal = Decimal("0"),
    currency: str = "RUB",
) -> Subscription
    """Create new subscription."""

async def list_subscriptions_for_business(
    business_id: str,
) -> list[Subscription]
    """Get all subscriptions for a business."""

async def list_expiring_subscriptions(
    business_id: str,
    days_until: int = 7,
) -> list[Subscription]
    """Get subscriptions expiring within N days and not yet reminded."""

async def update_subscription_status(
    subscription_id: str,
    new_status: SubscriptionStatus,
) -> Subscription
    """Change subscription status."""

async def renew_subscription(
    subscription_id: str,
    additional_days: int,
) -> Subscription
    """Extend subscription end date by N days."""

async def extend_subscription(
    subscription_id: str,
    additional_days: int,
) -> Subscription
    """Extend subscription duration and reset reminder."""

async def mark_reminder_sent(subscription_id: str) -> Subscription
    """Mark that expiration reminder was sent for this subscription."""

async def get_subscription_stats_for_business(
    business_id: str,
) -> dict[str, int]
    """Get count by status: {ACTIVE: 5, EXPIRED: 2, ...}"""
```

#### Payment Operations

```python
async def create_payment(
    business_id: str,
    subscription_id: str,
    amount: Decimal,
    currency: str,
    payment_date: date,
    notes: str | None = None,
) -> Payment
    """Record a payment."""

async def list_payments_for_business(
    business_id: str,
) -> list[Payment]
    """Get all payments for a business."""

async def list_payments_for_subscription(
    subscription_id: str,
) -> list[Payment]
    """Get all payments for a subscription."""

async def list_payments_for_date_range(
    business_id: str,
    start_date: date,
    end_date: date,
) -> list[Payment]
    """Get payments within date range (for monthly reports)."""

async def get_subscription_revenue_stats(
    business_id: str,
) -> dict[str, Decimal | float]
    """Get revenue statistics:
    {
        'total': Decimal,
        'this_month': Decimal,
        'avg_monthly': float,
    }
    """
```

#### Business Operations

```python
async def update_business_name(
    business_id: str,
    new_name: str,
) -> Business
    """Change business name."""

async def get_business(business_id: str) -> Business
    """Get business by ID."""
```

---

## Troubleshooting

### Common Issues

**1. "заведение не определено" (Business undefined)**
- Cause: Middleware not injecting business context
- Solution: Ensure `/start` was run first to create owner profile

**2. "Ошибка: заведение не определено" (Not found)**
- Cause: No business record for owner in Supabase
- Solution: Delete user from Telegram and run `/start` again

**3. Reminders not sending**
- Check: `owner_profiles.reminder_enabled = true`
- Check: Current hour matches `reminder_hour` setting
- Check: Subscription `reminder_sent_at` is NULL
- Check: Subscription status = "active"
- Check: `end_date - today = reminder_days_before`

**4. Can't add subscription**
- Must have at least one client first
- Client must exist in database
- Both start_date and end_date required

**5. Database query timeout**
- Too many records in subscriptions table
- Add database indexes on `business_id` and `status`
- Implement pagination for large result sets

---

## Development Notes

### Code Style

- Python 3.9+ features (type hints, walrus operators)
- PEP 8 compliant
- Type hints on all function signatures
- Docstrings on classes and public methods
- Async/await throughout (no sync I/O)

### Testing

Current version has no automated tests. To add:

```bash
pip install pytest pytest-asyncio httpx
```

Example test:

```python
@pytest.mark.asyncio
async def test_create_client():
    supabase = get_supabase_client()
    client = await supabase.create_client(
        business_id="...",
        full_name="Test Client",
        phone="+79990000000"
    )
    assert client.full_name == "Test Client"
```

### Performance

- Database queries use indexes on `business_id`, `client_id`, `status`
- Supabase connection pooled
- Reminder checks run hourly (not per-user)
- Message storage in-memory (consider persistent storage in production)

---

## Support & Maintenance

### Regular Tasks

1. **Weekly**: Check bot logs for errors
2. **Monthly**: Review Supabase usage and query performance
3. **Quarterly**: Update dependencies (`pip install --upgrade`)
4. **Annually**: Review and optimize database indexes

### Updating

```bash
git pull origin main
pip install -r requirements.txt --upgrade
# Restart bot
python -m app.bot.main
```

### Backup

Export all data via:
```
/export_clients
/export_subscriptions
/export_payments
```

Or use Supabase backup feature.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | Feb 25, 2026 | Initial release with all core features |

---

**Documentation maintained by:** GymCRM Development Team  
**Last updated:** February 25, 2026

For issues or feature requests, please refer to the project repository.
