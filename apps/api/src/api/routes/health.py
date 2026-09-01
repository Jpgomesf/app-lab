"""Liveness and readiness.

Split deliberately: /healthz answers from the process alone, /readyz is allowed
to touch the database. Pointing a liveness probe at a dependency check turns a
database blip into a restart loop, which is the opposite of what it should do.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status

from api.config import SERVICE_NAME
from api.db import check_connection
from api.dependencies import EngineDep, SettingsDep
from api.schemas import HealthResponse, ReadinessResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

_OK = HealthResponse(service=SERVICE_NAME, status="ok")


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    """Liveness: the process is up. Touches nothing else, ever."""
    return _OK


@router.get("/", response_model=HealthResponse, include_in_schema=False)
def root() -> HealthResponse:
    """Same answer as /healthz.

    The Deployment in the infra repo still points its readiness probe at `/`
    (a leftover from the `traefik/whoami` stand-in), so keeping this route
    makes the image swap a one-line overlay change with no manifest edit.
    """
    return _OK


@router.get("/readyz", response_model=ReadinessResponse)
async def readyz(response: Response, settings: SettingsDep, engine: EngineDep) -> ReadinessResponse:
    """Readiness: can this replica serve real traffic?

    With no DATABASE_URL configured there is no dependency to be unready
    against, so the honest answer is 200.
    """
    if not settings.database_configured or engine is None:
        return ReadinessResponse(service=SERVICE_NAME, status="ready", database="not_configured")

    try:
        await check_connection(engine)
    except Exception:
        logger.warning("readiness check failed", exc_info=True, extra={"event": "readyz_failed"})
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(service=SERVICE_NAME, status="not_ready", database="unreachable")

    return ReadinessResponse(service=SERVICE_NAME, status="ready", database="ok")
