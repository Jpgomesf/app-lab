"""The data-access boundary.

Routes depend on the `ItemRepository` protocol, never on a Session. That is
what lets the route tests run with no Postgres and no network: they bind an
in-memory implementation instead. `ItemRecord` is the type that crosses the
boundary, so ORM instances never reach the HTTP layer or the tests.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Item


@dataclass(frozen=True, slots=True)
class ItemRecord:
    """One item, detached from whatever stored it."""

    id: uuid.UUID
    name: str
    created_at: datetime


class ItemRepository(Protocol):
    """Storage operations the item routes need."""

    async def add(self, name: str) -> ItemRecord: ...

    async def list(self, limit: int) -> Sequence[ItemRecord]: ...

    async def get(self, item_id: uuid.UUID) -> ItemRecord | None: ...


def _to_record(item: Item) -> ItemRecord:
    return ItemRecord(id=item.id, name=item.name, created_at=item.created_at)


class SqlAlchemyItemRepository:
    """`ItemRepository` backed by Postgres."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, name: str) -> ItemRecord:
        item = Item(name=name)
        self._session.add(item)
        # Flush then refresh: `created_at` is a server default, so its value
        # only exists once the row has been written.
        await self._session.flush()
        await self._session.refresh(item)
        return _to_record(item)

    async def list(self, limit: int) -> Sequence[ItemRecord]:
        statement = select(Item).order_by(Item.created_at.desc(), Item.id).limit(limit)
        result = await self._session.execute(statement)
        return [_to_record(item) for item in result.scalars()]

    async def get(self, item_id: uuid.UUID) -> ItemRecord | None:
        item = await self._session.get(Item, item_id)
        return None if item is None else _to_record(item)
