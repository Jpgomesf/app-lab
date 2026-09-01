"""FastAPI dependencies.

Everything request-scoped is resolved from `app.state`, which the lifespan
populates. Routes therefore never import the engine directly and tests can
build an app with different state — or override these outright.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from api.config import Settings
from api.repository import ItemRepository, SqlAlchemyItemRepository

DATABASE_UNAVAILABLE_DETAIL = "database is not configured; this endpoint requires DATABASE_URL"


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_engine(request: Request) -> AsyncEngine | None:
    engine: AsyncEngine | None = getattr(request.app.state, "engine", None)
    return engine


async def get_item_repository(request: Request) -> AsyncIterator[ItemRepository]:
    """Yield a repository bound to a transaction for this request.

    With no DATABASE_URL the answer is a plain 503 rather than a traceback: a
    process started without a database is a valid, degraded state — /healthz
    still passes — and only the endpoints that need storage should fail.
    """
    factory: async_sessionmaker[AsyncSession] | None = getattr(
        request.app.state, "session_factory", None
    )
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=DATABASE_UNAVAILABLE_DETAIL,
        )
    # `session.begin()` commits when the route returns and rolls back if it
    # raises, so no route has to remember to do either.
    async with factory() as session, session.begin():
        yield SqlAlchemyItemRepository(session)


# Aliases rather than `= Depends(...)` defaults: one place to change the wiring,
# and no function call sitting in a signature default (ruff B008).
SettingsDep = Annotated[Settings, Depends(get_settings)]
EngineDep = Annotated[AsyncEngine | None, Depends(get_engine)]
ItemRepositoryDep = Annotated[ItemRepository, Depends(get_item_repository)]
