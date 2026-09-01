"""Async engine lifecycle.

The engine is created once per process, in the app lifespan, and only when
DATABASE_URL is set. Nothing here runs at import: a missing database must not
stop the process from starting and answering /healthz.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Readiness must answer well inside the kubelet's probe timeout, so the check
# is bounded rather than left to the driver's own connect timeout.
READINESS_TIMEOUT_SECONDS: Final[float] = 1.0


def create_engine(database_url: str) -> AsyncEngine:
    """Build the async engine.

    `pool_pre_ping` costs one round trip per checkout and removes the class of
    500s caused by connections killed underneath us (rollout, failover, idle
    timeout on a managed instance).
    """
    return create_async_engine(database_url, pool_size=5, max_overflow=5, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def engine_scope(database_url: str) -> AsyncIterator[AsyncEngine]:
    """Own an engine for the duration of a block, disposing it on exit."""
    engine = create_engine(database_url)
    try:
        yield engine
    finally:
        await engine.dispose()


async def check_connection(engine: AsyncEngine, timeout: float = READINESS_TIMEOUT_SECONDS) -> None:
    """Run `SELECT 1`, raising if it does not answer within `timeout`."""

    async def _ping() -> None:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    await asyncio.wait_for(_ping(), timeout=timeout)
