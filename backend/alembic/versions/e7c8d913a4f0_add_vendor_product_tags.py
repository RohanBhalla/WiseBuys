"""add vendor_product_tags table

Revision ID: e7c8d913a4f0
Revises: d4a17b9c2e51
Create Date: 2026-04-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e7c8d913a4f0"
down_revision = "d4a17b9c2e51"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vendor_product_tags",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("vendor_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tag_id",
            sa.Integer(),
            sa.ForeignKey("value_tags.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("product_id", "tag_id", name="uq_vendor_product_tag"),
    )
    op.create_index("ix_vendor_product_tags_product_id", "vendor_product_tags", ["product_id"])
    op.create_index("ix_vendor_product_tags_tag_id", "vendor_product_tags", ["tag_id"])


def downgrade() -> None:
    op.drop_index("ix_vendor_product_tags_tag_id", table_name="vendor_product_tags")
    op.drop_index("ix_vendor_product_tags_product_id", table_name="vendor_product_tags")
    op.drop_table("vendor_product_tags")
