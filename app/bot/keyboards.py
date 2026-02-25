from __future__ import annotations

from typing import Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class Keyboards:
    """
    Centralized keyboard/button builder for consistent UI.
    """

    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Main menu buttons."""
        buttons = [
            [
                InlineKeyboardButton(text="👥 Клиенты", callback_data="menu_clients"),
                InlineKeyboardButton(text="💳 Абонементы", callback_data="menu_subscriptions"),
            ],
            [
                InlineKeyboardButton(text="💰 Платежи", callback_data="menu_payments"),
                InlineKeyboardButton(text="📊 Отчёты", callback_data="menu_reports"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings"),
                InlineKeyboardButton(text="❓ Справка", callback_data="menu_help"),
            ],
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def clients_menu() -> InlineKeyboardMarkup:
        """Clients submenu."""
        buttons = [
            [InlineKeyboardButton(text="➕ Добавить клиента", callback_data="add_client")],
            [InlineKeyboardButton(text="📋 Все клиенты", callback_data="list_clients")],
            [InlineKeyboardButton(text="🔍 Поиск клиента", callback_data="search_client")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def subscriptions_menu() -> InlineKeyboardMarkup:
        """Subscriptions submenu."""
        buttons = [
            [InlineKeyboardButton(text="➕ Новый абонемент", callback_data="add_subscription")],
            [InlineKeyboardButton(text="📋 Все абонементы", callback_data="list_subscriptions")],
            [InlineKeyboardButton(text="🔄 Продлить", callback_data="renew_subscription")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_subscription")],
            [InlineKeyboardButton(text="🧊 Заморозить", callback_data="freeze_subscription")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def payments_menu() -> InlineKeyboardMarkup:
        """Payments submenu."""
        buttons = [
            [InlineKeyboardButton(text="➕ Новый платёж", callback_data="add_payment")],
            [InlineKeyboardButton(text="📋 История платежей", callback_data="list_payments")],
            [InlineKeyboardButton(text="💹 Статистика", callback_data="revenue_stats")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def reports_menu() -> InlineKeyboardMarkup:
        """Reports submenu."""
        buttons = [
            [InlineKeyboardButton(text="📊 Полный отчёт", callback_data="full_report")],
            [InlineKeyboardButton(text="📈 Краткая сводка", callback_data="summary_report")],
            [InlineKeyboardButton(text="💰 Доходы", callback_data="revenue_report")],
            [InlineKeyboardButton(text="⏰ Скоро истекло", callback_data="expiring_report")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def settings_menu() -> InlineKeyboardMarkup:
        """Settings submenu."""
        buttons = [
            [InlineKeyboardButton(text="📝 Изменить название", callback_data="rename_business")],
            [InlineKeyboardButton(text="📥 Экспорт данных", callback_data="export_data")],
            [InlineKeyboardButton(text="🔔 Напоминания", callback_data="test_reminder")],
            [InlineKeyboardButton(text="ℹ️ О заведении", callback_data="business_info")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def export_menu() -> InlineKeyboardMarkup:
        """Export submenu."""
        buttons = [
            [InlineKeyboardButton(text="📄 Клиенты (CSV)", callback_data="export_clients")],
            [InlineKeyboardButton(text="📄 Абонементы (CSV)", callback_data="export_subscriptions")],
            [InlineKeyboardButton(text="📄 Платежи (CSV)", callback_data="export_payments")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_settings")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def confirm_button(action_text: str = "Подтвердить") -> InlineKeyboardMarkup:
        """Confirmation buttons."""
        buttons = [
            [
                InlineKeyboardButton(text=f"✅ {action_text}", callback_data="confirm_yes"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="confirm_no"),
            ],
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def back_button(callback_data: str = "menu_main") -> InlineKeyboardMarkup:
        """Simple back button."""
        buttons = [
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=callback_data)],
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)


class MessageTemplates:
    """
    Standardized message templates for consistent formatting.
    """

    @staticmethod
    def header(title: str, emoji: str = "📋") -> str:
        """Format a header."""
        return f"\n<b>{emoji} {title}</b>\n"

    @staticmethod
    def section(title: str, emoji: str = "•") -> str:
        """Format a section header."""
        return f"\n<b>{emoji} {title}</b>"

    @staticmethod
    def item(text: str, indent: int = 1) -> str:
        """Format an item in a list."""
        return "  " * indent + f"• {text}"

    @staticmethod
    def divider() -> str:
        """Divider line."""
        return "─" * 40

    @staticmethod
    def error(message: str) -> str:
        """Format an error message."""
        return f"❌ <b>Ошибка:</b> {message}"

    @staticmethod
    def success(message: str) -> str:
        """Format a success message."""
        return f"✅ <b>Готово!</b> {message}"

    @staticmethod
    def info(message: str) -> str:
        """Format an info message."""
        return f"ℹ️ {message}"

    @staticmethod
    def warning(message: str) -> str:
        """Format a warning message."""
        return f"⚠️ <b>Внимание:</b> {message}"

    @staticmethod
    def stat(label: str, value: str, unit: str = "") -> str:
        """Format a statistic item."""
        return f"  <b>{label}:</b> {value}{' ' + unit if unit else ''}"

    @staticmethod
    def format_date(date_obj) -> str:
        """Format date consistently."""
        return f"<code>{date_obj}</code>"
