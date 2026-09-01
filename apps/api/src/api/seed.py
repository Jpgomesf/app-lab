"""Idempotent seed: `python -m api.seed`.

Safe to run on every deploy. There is no unique constraint on `items.name` —
the domain does not want one — so the seed selects before it inserts rather
than leaning on ON CONFLICT.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.db import create_session_factory, engine_scope
from api.logging import configure_logging
from api.models import Item

logger = logging.getLogger(__name__)

SEED_NAMES: Final[tuple[str, ...]] = ("first-item", "second-item", "third-item")


async def seed_session(session: AsyncSession, names: tuple[str, ...] = SEED_NAMES) -> int:
    """Insert any missing seed rows. Returns how many were created."""
    existing = set(
        (await session.execute(select(Item.name).where(Item.name.in_(names)))).scalars().all()
    )
    missing = [name for name in names if name not in existing]
    session.add_all([Item(name=name) for name in missing])
    return len(missing)


async def run() -> int:
    if settings.database_url is None:
        raise SystemExit("DATABASE_URL is required to seed")
    async with engine_scope(settings.database_url) as engine:
        factory = create_session_factory(engine)
        async with factory() as session, session.begin():
            created = await seed_session(session)
    logger.info("seed complete", extra={"event": "seed_done", "created": created})
    return created


def main() -> None:
    configure_logging(settings.log_level)
    asyncio.run(run())


if __name__ == "__main__":
    main()
