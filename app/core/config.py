from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, HttpUrl, ValidationError


class Settings(BaseModel):
    bot_token: str
    supabase_url: HttpUrl
    supabase_service_key: str
    supabase_anon_key: str | None = None
    environment: Literal["local", "staging", "production"] = "local"

    @property
    def is_debug(self) -> bool:
        return self.environment == "local"


def _build_settings() -> Settings:
    # Load .env file once on first settings build (for local development)
    load_dotenv()

    try:
        return Settings(
            bot_token=os.environ["BOT_TOKEN"],
            supabase_url=os.environ["SUPABASE_URL"],
            supabase_service_key=os.environ["SUPABASE_SERVICE_KEY"],
            supabase_anon_key=os.getenv("SUPABASE_ANON_KEY"),
            environment=os.getenv("ENVIRONMENT", "local"),
        )
    except KeyError as exc:  # pragma: no cover - defensive branch
        required_keys = ("BOT_TOKEN", "SUPABASE_URL", "SUPABASE_SERVICE_KEY")
        missing = [key for key in required_keys if key not in os.environ]
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        ) from exc
    except ValidationError as exc:  # pragma: no cover - defensive branch
        raise RuntimeError(f"Invalid settings: {exc}") from exc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Cached accessor for application settings.

    Reads environment variables once and validates them with Pydantic.
    """

    return _build_settings()

