"""Environment-driven configuration.

The pod gives this process nothing but environment variables — no config file,
no writable filesystem — so every knob lives here and is validated once, at
import. A bad value crashes the container on startup instead of surfacing as a
confusing 500 on the first request that happens to need it.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_NAME: Final[str] = "api"

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# The cluster Secret holds a libpq-style URL (`postgres://…`). SQLAlchemy needs
# an explicit driver in the scheme to pick the async driver, so both of the
# bare forms are rewritten rather than rejected — the Secret is shared with
# psql and other tools that would not understand `+asyncpg`.
_ASYNC_DRIVER: Final[str] = "postgresql+asyncpg://"
_BARE_SCHEMES: Final[tuple[str, ...]] = ("postgres://", "postgresql://")


class Settings(BaseSettings):
    """Runtime configuration, read from the process environment."""

    model_config = SettingsConfigDict(
        # Env only: no .env file, so a stray file in a working directory can
        # never change how the deployed service behaves.
        env_file=None,
        extra="ignore",
        case_sensitive=False,
    )

    port: int = Field(default=8080, ge=1, le=65535)
    log_level: LogLevel = "INFO"

    # Optional: the service must start and serve /healthz with neither of
    # these set, which is what makes the liveness probe dependency-free.
    database_url: str | None = None
    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str = SERVICE_NAME

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("database_url", "otel_exporter_otlp_endpoint", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        # Kubernetes and shell wrappers both love to inject empty strings;
        # treat them as "not configured" rather than as a malformed URL.
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("database_url")
    @classmethod
    def _require_async_driver(cls, value: str | None) -> str | None:
        if value is None:
            return None
        for scheme in _BARE_SCHEMES:
            if value.startswith(scheme):
                return _ASYNC_DRIVER + value[len(scheme) :]
        if not value.startswith(_ASYNC_DRIVER):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL URL "
                "(postgres://, postgresql:// or postgresql+asyncpg://)"
            )
        return value

    @property
    def database_configured(self) -> bool:
        return self.database_url is not None

    @property
    def tracing_configured(self) -> bool:
        return self.otel_exporter_otlp_endpoint is not None


# Instantiated at import: fail fast, before anything binds a socket.
settings: Final[Settings] = Settings()
