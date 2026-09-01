"""Application factory and process lifespan.

The contract this has to satisfy comes from the Deployment in the infra repo:
listen on $PORT, answer /healthz without touching anything, run as uid 65532 on
a read-only root filesystem, and take all configuration from the environment.
Nothing here writes to disk.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from api.config import SERVICE_NAME, Settings
from api.config import settings as default_settings
from api.db import create_engine, create_session_factory
from api.logging import configure_logging
from api.middleware import RequestLogMiddleware
from api.routes import health, items

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import TracerProvider

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Own the engine and the tracer provider for the life of the process."""
    settings: Settings = app.state.settings
    app.state.engine = None
    app.state.session_factory = None

    database_url = settings.database_url
    if database_url is not None:
        # Constructing the engine does not connect; the first checkout does.
        # A database that is down therefore delays readiness, not startup.
        engine = create_engine(database_url)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        logger.info("database configured", extra={"event": "db_configured"})
    else:
        logger.warning(
            "DATABASE_URL is unset; item routes will answer 503",
            extra={"event": "db_not_configured"},
        )

    try:
        yield
    finally:
        if app.state.engine is not None:
            await app.state.engine.dispose()
        provider: TracerProvider | None = getattr(app.state, "tracer_provider", None)
        if provider is not None:
            # Flushes whatever the batch processor is still holding.
            provider.shutdown()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the ASGI application."""
    settings = settings or default_settings
    configure_logging(settings.log_level)

    app = FastAPI(
        title="api",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.tracer_provider = None

    app.add_middleware(RequestLogMiddleware)
    app.include_router(health.router)
    app.include_router(items.router)

    if settings.tracing_configured:
        # Imported lazily: the OTLP/grpc stack is heavy and pointless when no
        # collector is configured.
        from api.telemetry import configure_tracing

        app.state.tracer_provider = configure_tracing(app, settings)

    return app


app = create_app()


def main() -> None:
    """Run the service directly (`python -m api.main`), for local use."""
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",  # noqa: S104 - only ever bound inside a container
        port=default_settings.port,
        log_config=None,  # configure_logging() already owns the handlers
    )


if __name__ == "__main__":
    logger.info("starting", extra={"event": "starting", "service": SERVICE_NAME})
    main()
