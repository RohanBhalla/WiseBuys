"""add vector embeddings for hybrid recommendations

Revision ID: b2f8e9a1c3d4
Revises: c91d23c96bb7
Create Date: 2026-04-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "b2f8e9a1c3d4"
down_revision = "c91d23c96bb7"
branch_labels = None
depends_on = None

_EMB_DIM = 768


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    if is_pg:
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    op.add_column(
        "vendor_products",
        sa.Column("embedding", Vector(_EMB_DIM), nullable=True),
    )
    op.add_column("vendor_products", sa.Column("embedding_signature", sa.Text(), nullable=True))
    op.add_column(
        "vendor_products",
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "customer_profiles",
        sa.Column("embedding", Vector(_EMB_DIM), nullable=True),
    )
    op.add_column("customer_profiles", sa.Column("embedding_signature", sa.Text(), nullable=True))
    op.add_column(
        "customer_profiles",
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
    )

    if is_pg:
        # Cosine-distance ANN index (lists tuned for small/medium catalogs).
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_vendor_products_embedding_ivfflat "
                "ON vendor_products USING ivfflat (embedding vector_cosine_ops) "
                "WITH (lists = 100)"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    if is_pg:
        op.execute(sa.text("DROP INDEX IF EXISTS ix_vendor_products_embedding_ivfflat"))

    op.drop_column("customer_profiles", "embedded_at")
    op.drop_column("customer_profiles", "embedding_signature")
    op.drop_column("customer_profiles", "embedding")

    op.drop_column("vendor_products", "embedded_at")
    op.drop_column("vendor_products", "embedding_signature")
    op.drop_column("vendor_products", "embedding")
