from __future__ import annotations

import re


_PHONE_REGEX = re.compile(r"^\+?\d{7,15}$")


def normalize_phone(raw: str) -> str | None:
    """
    Basic phone normalization and validation.

    Accepts digits and an optional leading '+'. Returns normalized phone
    (digits with optional '+') or None if the value looks invalid.
    """

    value = raw.strip().replace(" ", "").replace("-", "")
    if not _PHONE_REGEX.match(value):
        return None
    return value

