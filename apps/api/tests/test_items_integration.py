"""The same item flow against a real Postgres.

Skipped unless TEST_DATABASE_URL is set, so the default `make test` needs no
container. Point it at the lab database to run these:

    TEST_DATABASE_URL=postgresql+asyncpg://app:localdev@localhost:5432/app \
        uv run pytest -m integration

They exercise what the in-memory repository cannot: the migration, the real
uuid/timestamptz columns, and transaction behaviour.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from api.config import Settings
from api.db import create_engine, create_session_factory
from api.main import create_app
from api.migrate import build_config
from api.repository import SqlAlchemyItemRepository
from api.seed import seed_session

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set"),
]


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """A migrated database, emptied between tests."""
    from alembic import command

    command.upgrade(build_config(TEST_DATABASE_URL), "head")

    eng = create_engine(TEST_DATABASE_URL)
    async with eng.begin() as connection:
        await connection.execute(text("TRUNCATE TABLE items"))
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def http(engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    settings = Settings(database_url=TEST_DATABASE_URL)
    app = create_app(settings)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_create_then_read_round_trips_through_postgres(http: AsyncClient) -> None:
    created = await http.post("/v1/items", json={"name": "widget"})
    assert created.status_code == 201
    item_id = created.json()["id"]

    fetched = await http.get(f"/v1/items/{item_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "widget"
    # created_at came from the server default, so it must be tz-aware.
    assert fetched.json()["created_at"].endswith(("Z", "+00:00"))


@pytest.mark.asyncio
async def test_readyz_reports_ok_against_a_live_database(http: AsyncClient) -> None:
    response = await http.get("/readyz")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


@pytest.mark.asyncio
async def test_unknown_id_is_404_not_a_driver_error(http: AsyncClient) -> None:
    assert (await http.get(f"/v1/items/{uuid.uuid4()}")).status_code == 404


@pytest.mark.asyncio
async def test_seed_is_idempotent(engine: AsyncEngine) -> None:
    factory = create_session_factory(engine)

    async with factory() as session, session.begin():
        first = await seed_session(session)
    async with factory() as session, session.begin():
        second = await seed_session(session)

    assert first == 3
    assert second == 0

    async with factory() as session:
        repository = SqlAlchemyItemRepository(session)
        assert len(await repository.list(limit=50)) == 3
