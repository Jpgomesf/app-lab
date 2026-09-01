"""The items resource — one real domain slice, end to end.

Small on purpose: enough to prove the wiring (request validation, a
transaction, a migration, a real Postgres type) without inventing a domain the
platform does not have yet.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from api.dependencies import ItemRepositoryDep
from api.schemas import ItemCreate, ItemRead

router = APIRouter(prefix="/v1/items", tags=["items"])

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


LimitQuery = Annotated[int, Query(ge=1, le=MAX_LIMIT)]


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(payload: ItemCreate, repository: ItemRepositoryDep) -> ItemRead:
    record = await repository.add(payload.name)
    return ItemRead.from_record(record)


@router.get("", response_model=list[ItemRead])
async def list_items(
    repository: ItemRepositoryDep, limit: LimitQuery = DEFAULT_LIMIT
) -> list[ItemRead]:
    records = await repository.list(limit)
    return [ItemRead.from_record(record) for record in records]


@router.get("/{item_id}", response_model=ItemRead)
async def get_item(item_id: uuid.UUID, repository: ItemRepositoryDep) -> ItemRead:
    record = await repository.get(item_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
    return ItemRead.from_record(record)
