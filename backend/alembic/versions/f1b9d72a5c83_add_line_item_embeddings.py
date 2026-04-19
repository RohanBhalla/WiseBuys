"""add line-item vector embeddings for semantic comparable matching

Revision ID: f1b9d72a5c83
Revises: e7c8d913a4f0
Create Date: 2026-04-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "f1b9d72a5c83"
down_revision = "e7c8d913a4f0"
branch_labels = None
depends_on = None

_EMB_DIM = 768


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    if is_pg:
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    op.add_column(
        "knot_line_items",
        sa.Column("embedding", Vector(_EMB_DIM), nullable=True),
    )
    op.add_column(
        "knot_line_items",
        sa.Column("embedding_signature", sa.Text(), nullable=True),
    )
    op.add_column(
        "knot_line_items",
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
    )

    if is_pg:
        # Per-user comparable picking is bounded (recent line items only) so a
        # plain ivfflat index is more than enough; cosine ops to match the
        # vendor_products index.
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_knot_line_items_embedding_ivfflat "
                "ON knot_line_items USING ivfflat (embedding vector_cosine_ops) "
                "WITH (lists = 100)"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    if is_pg:
        op.execute(sa.text("DROP INDEX IF EXISTS ix_knot_line_items_embedding_ivfflat"))

    op.drop_column("knot_line_items", "embedded_at")
    op.drop_column("knot_line_items", "embedding_signature")
    op.drop_column("knot_line_items", "embedding")
