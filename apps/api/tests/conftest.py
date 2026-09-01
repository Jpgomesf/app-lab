"""Shared fixtures.

Every test in this directory runs with no database and no network. The route
tests get there by binding the in-memory repository below to the same
dependency the Postgres one is bound to in production.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.config import Settings
from api.dependencies import get_item_repository
from api.main import create_app
from api.repository import ItemRecord

# Settings pydantic would otherwise pick up from the developer's own shell.
_ENV_KEYS = (
    "PORT",
    "LOG_LEVEL",
    "DATABASE_URL",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_SERVICE_NAME",
)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop the service's env vars so tests see the documented defaults."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


class InMemoryItemRepository:
    """`ItemRepository` over a list. Same contract, no Postgres."""

    def __init__(self, records: Sequence[ItemRecord] | None = None) -> None:
        self.records: list[ItemRecord] = list(records or [])

    async def add(self, name: str) -> ItemRecord:
        record = ItemRecord(id=uuid.uuid4(), name=name, created_at=datetime.now(UTC))
        self.records.append(record)
        return record

    async def list(self, limit: int) -> Sequence[ItemRecord]:
        # Mirrors the SQL ordering: newest first.
        ordered = sorted(self.records, key=lambda r: (r.created_at, r.id), reverse=True)
        return ordered[:limit]

    async def get(self, item_id: uuid.UUID) -> ItemRecord | None:
        return next((r for r in self.records if r.id == item_id), None)


@pytest.fixture
def settings(clean_env: None) -> Settings:
    """Settings for a process started with nothing configured."""
    return Settings()


@pytest.fixture
def repository() -> InMemoryItemRepository:
    return InMemoryItemRepository()


@pytest.fixture
def app(settings: Settings, repository: InMemoryItemRepository) -> FastAPI:
    """App with storage swapped for the in-memory repository."""
    application = create_app(settings)

    async def override() -> AsyncIterator[InMemoryItemRepository]:
        yield repository

    application.dependency_overrides[get_item_repository] = override
    return application


@pytest.fixture
def bare_app(settings: Settings) -> FastAPI:
    """App with nothing overridden: what a process with no DATABASE_URL is."""
    return create_app(settings)


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


@pytest_asyncio.fixture
async def bare_client(bare_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=bare_app), base_url="http://test") as http:
        yield http
