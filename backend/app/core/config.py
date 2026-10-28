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

    # --- Databases (PostgreSQL) -----------------------------------------------
    # Server connection with rights to create databases. The directory database
    # and one database per client are derived from it by swapping the name.
    database_admin_url: str = "postgresql://bank:bank@localhost:5432/postgres"
    directory_database: str = "bank_directory"
    # Create and seed missing databases on startup (development convenience).
    provision_on_startup: bool = True

    # --- Sessions ---------------------------------------------------------------
    # Signs login tokens. When unset a random secret is generated per process,
    # so restarting the backend logs everyone out.
    session_secret: str | None = None
    session_hours: float = 8.0

    # --- AI provider: Amazon Bedrock -----------------------------------------
    # Standard AWS variable names. Left empty, boto3 falls back to its default
    # credential chain (instance role, ~/.aws, ...).
    aws_default_region: str = "us-west-2"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    bedrock_model_id: str = "us.anthropic.claude-sonnet-5-5"
    # A slow provider falls back to rules wording instead of blocking the page.
    ai_timeout_seconds: float = 20.0

    # --- Demo ------------------------------------------------------------------
    # Overrides the data file's ``as_of_date`` ("today" for the projection).
    demo_today: date | None = None
    # Simulated "approve in your banking app" delay for payment verification.
    demo_approval_seconds: float = 3.0

    # --- Application --------------------------------------------------------
    # NoDecode keeps pydantic-settings from treating the JSON array as a
    # "complex" field that must be JSON-encoded again; the validator below
    # accepts either a JSON list or a comma separated string.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    app_env: str = "development"
    log_level: str = "INFO"

    # Validators -------------------------------------------------------------

    @field_validator(
        "session_secret",
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
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
