"""create items table

Revision ID: 0001_create_items
Revises:
Create Date: 2026-09-01

Plain Postgres: `uuid` and `timestamptz` are core types, so this runs against a
stock image with no CREATE EXTENSION and no superuser. Identifiers come from
the application (uuid4), which is why there is no server-side default on `id`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_create_items"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_items"),
    )
    # Every list query orders by created_at desc; without this it is a seqscan
    # plus a sort as soon as the table is non-trivial.
    op.create_index("ix_items_created_at", "items", [sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_items_created_at", table_name="items")
    op.drop_table("items")
