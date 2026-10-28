"""Application configuration loaded from environment variables.

Values come from the process environment and, when present, from ``backend/.env``.
Only non-secret development defaults are provided here so that the application can
start and expose its health check without any external credentials.
"""

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """Typed application settings.

    Every integration credential is optional so that importing the app never
    fails because a key is missing. Endpoints that need an integration raise a
    clear configuration error instead.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Database (Supabase PostgreSQL) -------------------------------------
    # Optional: analyses are persisted when set, and skipped when not.
    database_url: str | None = None

    # --- AI provider --------------------------------------------------------
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    # --- Demo client data ---------------------------------------------------
    # Defaults to app/data/client1_date.json, which ships in the Docker image.
    demo_data_path: Path | None = None
    # Overrides the data file's ``as_of_date`` ("today" for the projection).
    demo_today: date | None = None

    # --- Application --------------------------------------------------------
    # NoDecode keeps pydantic-settings from treating the JSON array as a
    # "complex" field that must be JSON-encoded again; the validator below
    # accepts either a JSON list or a comma separated string.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    auto_create_tables: bool = True
    app_env: str = "development"
    log_level: str = "INFO"

    # Validators -------------------------------------------------------------

    @field_validator(
        "database_url",
        "openai_api_key",
        "demo_data_path",
        "demo_today",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        """Treat empty or whitespace-only environment values as unset.

        A copied ``.env.example`` therefore behaves exactly like a missing
        variable instead of an empty string that would be used as a credential.
        """
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> Any:
        """Accept a JSON array, a comma separated string, or a real list."""
        if value is None or value == "":
            return ["http://localhost:3000"]
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                    raise ValueError(
                        "CORS_ORIGINS must be valid JSON or a comma separated list"
                    ) from exc
                if not isinstance(parsed, list):
                    raise ValueError("CORS_ORIGINS JSON value must be an array")
                return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in text.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance (cached for the app lifetime)."""
    return Settings()


settings = get_settings()
