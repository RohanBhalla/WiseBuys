"""add recommendation_clicks table

Revision ID: d4a17b9c2e51
Revises: b2f8e9a1c3d4
Create Date: 2026-04-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d4a17b9c2e51"
down_revision = "b2f8e9a1c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendation_clicks",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("vendor_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "vendor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="dashboard"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_recommendation_clicks_user_id", "recommendation_clicks", ["user_id"])
    op.create_index("ix_recommendation_clicks_product_id", "recommendation_clicks", ["product_id"])
    op.create_index(
        "ix_recommendation_clicks_vendor_user_id", "recommendation_clicks", ["vendor_user_id"]
    )
    op.create_index("ix_recommendation_clicks_created_at", "recommendation_clicks", ["created_at"])
    op.create_index(
        "ix_rec_clicks_vendor_created",
        "recommendation_clicks",
        ["vendor_user_id", "created_at"],
    )
    op.create_index(
        "ix_rec_clicks_product_created",
        "recommendation_clicks",
        ["product_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_rec_clicks_product_created", table_name="recommendation_clicks")
    op.drop_index("ix_rec_clicks_vendor_created", table_name="recommendation_clicks")
    op.drop_index("ix_recommendation_clicks_created_at", table_name="recommendation_clicks")
    op.drop_index("ix_recommendation_clicks_vendor_user_id", table_name="recommendation_clicks")
    op.drop_index("ix_recommendation_clicks_product_id", table_name="recommendation_clicks")
    op.drop_index("ix_recommendation_clicks_user_id", table_name="recommendation_clicks")
    op.drop_table("recommendation_clicks")
