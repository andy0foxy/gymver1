from aiogram import Router

from . import (
    add_client,
    business_settings,
    client_details,
    clients,
    edit_subscriptions,
    export,
    menu,
    payments,
    reminders,
    report,
    start,
    subscriptions,
)


def setup_routers() -> Router:
    """
    Aggregate and return root router for the bot.
    """

    router = Router(name="root")
    router.include_router(start.router)
    router.include_router(menu.router)
    router.include_router(add_client.router)
    router.include_router(clients.router)
    router.include_router(subscriptions.router)
    router.include_router(edit_subscriptions.router)
    router.include_router(client_details.router)
    router.include_router(payments.router)
    router.include_router(reminders.router)
    router.include_router(export.router)
    router.include_router(report.router)
    router.include_router(business_settings.router)
    return router

