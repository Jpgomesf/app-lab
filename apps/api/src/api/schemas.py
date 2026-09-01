"""Request and response bodies for the HTTP layer."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from api.repository import ItemRecord


class ItemCreate(BaseModel):
    """POST /v1/items body."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)


class ItemRead(BaseModel):
    """One item as returned to clients."""

    id: uuid.UUID
    name: str
    created_at: datetime

    @classmethod
    def from_record(cls, record: ItemRecord) -> ItemRead:
        return cls(id=record.id, name=record.name, created_at=record.created_at)


class HealthResponse(BaseModel):
    """Body of /healthz and /."""

    service: str
    status: str


class ReadinessResponse(BaseModel):
    """Body of /readyz."""

    service: str
    status: str
    database: str
