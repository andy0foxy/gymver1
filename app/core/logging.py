from __future__ import annotations

import logging
from logging import Logger

from .config import get_settings


def configure_logging() -> Logger:
    """
    Configure root logger for the application.

    Uses a simple format suitable for both local development and production logs.
    """

    settings = get_settings()

    log_level = logging.DEBUG if settings.is_debug else logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    logger = logging.getLogger("gym_crm_bot")
    logger.setLevel(log_level)
    return logger

