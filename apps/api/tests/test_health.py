"""Probe endpoints.

The point of these: /healthz must stay dependency-free (it is what stops a
database blip from restarting every pod) and /readyz must be honest about the
database when there is one.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.dependencies import get_engine


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/healthz", "/"])
async def test_liveness_is_200_with_nothing_configured(bare_client: AsyncClient, path: str) -> None:
    response = await bare_client.get(path)
    assert response.status_code == 200
    assert response.json() == {"service": "api", "status": "ok"}


@pytest.mark.asyncio
async def test_readyz_is_200_without_a_database(bare_client: AsyncClient) -> None:
    response = await bare_client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"service": "api", "status": "ready", "database": "not_configured"}


@pytest.mark.asyncio
async def test_readyz_reports_ok_when_the_database_answers(
    bare_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    sentinel = object()
    bare_app.state.settings.database_url = "postgresql+asyncpg://u@h/db"
    bare_app.dependency_overrides[get_engine] = lambda: sentinel

    async def ok(engine: object, timeout: float = 1.0) -> None:
        assert engine is sentinel

    monkeypatch.setattr("api.routes.health.check_connection", ok)

    async with AsyncClient(transport=ASGITransport(app=bare_app), base_url="http://t") as client:
        response = await client.get("/readyz")

    assert response.status_code == 200
    assert response.json()["database"] == "ok"


@pytest.mark.asyncio
async def test_readyz_is_503_when_the_database_does_not_answer(
    bare_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    bare_app.state.settings.database_url = "postgresql+asyncpg://u@h/db"
    bare_app.dependency_overrides[get_engine] = lambda: object()

    async def timeout(engine: object, timeout: float = 1.0) -> None:
        raise TimeoutError

    monkeypatch.setattr("api.routes.health.check_connection", timeout)

    async with AsyncClient(transport=ASGITransport(app=bare_app), base_url="http://t") as client:
        response = await client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"service": "api", "status": "not_ready", "database": "unreachable"}


@pytest.mark.asyncio
async def test_healthz_still_200_while_readiness_fails(
    bare_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dead database must not take liveness down with it."""
    bare_app.state.settings.database_url = "postgresql+asyncpg://u@h/db"
    bare_app.dependency_overrides[get_engine] = lambda: object()

    async def down(engine: object, timeout: float = 1.0) -> None:
        raise ConnectionRefusedError

    monkeypatch.setattr("api.routes.health.check_connection", down)

    async with AsyncClient(transport=ASGITransport(app=bare_app), base_url="http://t") as client:
        assert (await client.get("/readyz")).status_code == 503
        assert (await client.get("/healthz")).status_code == 200
