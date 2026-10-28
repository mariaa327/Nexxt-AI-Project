"""Application configuration loaded from environment variables.

Values come from the process environment and, when present, from ``backend/.env``.
Only non-secret development defaults are provided here so that the application can
start and expose its health check without any external credentials.
"""

import json
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
    database_url: str | None = None

    # --- Supabase Auth ------------------------------------------------------
    supabase_url: str | None = None
    supabase_jwks_url: str | None = None
    # Legacy HS256 shared secret. Only used when explicitly configured and the
    # token header says HS256. Modern projects use asymmetric signing keys.
    supabase_jwt_secret: str | None = None
    # Supabase access tokens use "authenticated" for signed-in users.
    supabase_jwt_audience: str = "authenticated"

    # --- AI provider --------------------------------------------------------
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

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
        "supabase_url",
        "supabase_jwks_url",
        "supabase_jwt_secret",
        "supabase_jwt_audience",
        "openai_api_key",
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

    # Derived helpers --------------------------------------------------------

    @property
    def supabase_issuer(self) -> str | None:
        """Expected ``iss`` claim for Supabase-issued access tokens."""
        if not self.supabase_url:
            return None
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def resolved_jwks_url(self) -> str | None:
        """JWKS endpoint used to fetch Supabase's asymmetric signing keys."""
        if self.supabase_jwks_url:
            return self.supabase_jwks_url
        if self.supabase_url:
            return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        return None


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance (cached for the app lifetime)."""
    return Settings()


settings = get_settings()
