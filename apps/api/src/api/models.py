"""SQLAlchemy ORM models.

Vanilla Postgres only: no extensions, so identifiers are generated in Python
(`uuid4`) rather than by `gen_random_uuid()`. That keeps the migration runnable
against a stock image and against a managed instance where CREATE EXTENSION
may need privileges the app role does not have.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base; also the metadata Alembic autogenerates against."""


class Item(Base):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Text, not String: matches the migration and Postgres treats them alike.
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
