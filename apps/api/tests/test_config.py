"""Configuration is the one thing that must fail loudly and early."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.config import Settings


@pytest.mark.usefixtures("clean_env")
def test_defaults_are_a_runnable_process() -> None:
    settings = Settings()
    assert settings.port == 8080
    assert settings.log_level == "INFO"
    assert settings.database_url is None
    assert settings.otel_exporter_otlp_endpoint is None
    assert settings.database_configured is False
    assert settings.tracing_configured is False


@pytest.mark.usefixtures("clean_env")
def test_port_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "9090")
    assert Settings().port == 9090


@pytest.mark.usefixtures("clean_env")
@pytest.mark.parametrize("value", ["http", "0", "70000", "-1"])
def test_invalid_port_rejected(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("PORT", value)
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.usefixtures("clean_env")
@pytest.mark.parametrize(
    "given",
    [
        # The cluster Secret ships the libpq form; both bare schemes must work.
        "postgres://app:localdev@postgres:5432/app",
        "postgresql://app:localdev@postgres:5432/app",
        "postgresql+asyncpg://app:localdev@postgres:5432/app",
    ],
)
def test_database_url_normalised_to_async_driver(
    monkeypatch: pytest.MonkeyPatch, given: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", given)
    assert Settings().database_url == "postgresql+asyncpg://app:localdev@postgres:5432/app"


@pytest.mark.usefixtures("clean_env")
@pytest.mark.parametrize("given", ["mysql://host/db", "not-a-url", "sqlite+aiosqlite:///x.db"])
def test_non_postgres_database_url_rejected(monkeypatch: pytest.MonkeyPatch, given: str) -> None:
    monkeypatch.setenv("DATABASE_URL", given)
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.usefixtures("clean_env")
@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_optional_values_read_as_unset(monkeypatch: pytest.MonkeyPatch, blank: str) -> None:
    monkeypatch.setenv("DATABASE_URL", blank)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", blank)
    settings = Settings()
    assert settings.database_url is None
    assert settings.otel_exporter_otlp_endpoint is None


@pytest.mark.usefixtures("clean_env")
def test_log_level_is_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "debug")
    assert Settings().log_level == "DEBUG"


@pytest.mark.usefixtures("clean_env")
def test_unknown_log_level_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "chatty")
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.usefixtures("clean_env")
def test_tracing_flag_follows_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-lgtm:4317")
    settings = Settings()
    assert settings.tracing_configured is True
    assert settings.otel_service_name == "api"
