# Gym CRM Telegram Bot

MVP Telegram bot for small offline businesses (gyms, yoga studios, beauty salons, etc.) to track clients, subscriptions and send automated reminders.

## Tech stack

- Python 3.12+
- aiogram 3.x (Telegram bot with inline buttons UI)
- Supabase (Postgres + Auth + RLS + Storage)
- APScheduler (scheduler for reminders)
- httpx (async HTTP client)

## Features

### 👥 Client Management
- Add clients with name and phone
- Search clients by name or phone (fuzzy matching)
- View detailed client profiles with full subscription history
- List all clients organized by creation date

### 💳 Subscription Management
- Create subscriptions with status tracking (ACTIVE, EXPIRED, CANCELLED, FROZEN)
- Renew/extend subscriptions automatically
- Cancel subscriptions with confirmation
- Freeze subscriptions temporarily
- Track subscription timeline per client

### 💰 Payment Tracking
- Record payments for subscriptions
- View payment history
- Calculate revenue statistics (total, monthly, average)
- Optional payment notes

### 📊 Analytics & Reports
- Full business dashboard with key metrics
- Subscription status breakdown
- Revenue analysis (monthly, average, total)
- Expiring subscription alerts
- Quick summary view

### 🔔 Reminders
- Automated daily reminder checks (scheduled)
- Manual reminder commands for expiring subscriptions (3 & 7 days)
- Scheduled reminder infrastructure with APScheduler

### 📥 Data Export
- Export clients to CSV
- Export subscriptions to CSV
- Export payments to CSV
- All exports include timestamps

### ⚙️ Business Settings
- Update business name
- View business information and stats
- Settings management interface

### 🎨 User Experience
- **Button-based navigation** – No need to type commands
- Organized menu system with sub-menus
- Consistent message formatting templates
- Clear success/error messages
- Confirmation dialogs for destructive actions

## Quick start (local)

1. Create and activate a virtual environment:

```bash
python -m venv .venv
.\.venv\Scripts\activate  # Windows
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set environment variables (for local development you can use a `.env` file):

- `BOT_TOKEN` – Telegram bot token from BotFather
- `SUPABASE_URL` – Supabase project URL, e.g. `https://xxx.supabase.co`
- `SUPABASE_SERVICE_KEY` – Supabase service role key
- (optional) `SUPABASE_ANON_KEY`
- (optional) `ENVIRONMENT` – `local` | `staging` | `production` (default: `local`)

4. Run the bot in polling mode:

```bash
python -m app.bot.main
```

Later we will add a FastAPI service (for web panel and webhooks) and deployment configs for Railway/Render.

