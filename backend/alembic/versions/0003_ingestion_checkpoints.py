"""add ingestion checkpoints table

Revision ID: 0003_ingestion_checkpoints
Revises: 0002_cost_basis_holdings
Create Date: 2025-12-04 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_ingestion_checkpoints"
down_revision = "0002_cost_basis_holdings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_checkpoints",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("whale_id", sa.String(length=36), nullable=False),
        sa.Column("chain_slug", sa.String(length=64), nullable=False),
        sa.Column("last_fill_time", sa.BigInteger(), nullable=True),
        sa.Column("last_position_time", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["whale_id"], ["whales.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("whale_id"),
        sa.UniqueConstraint("whale_id", name="uq_ingestion_checkpoint_whale"),
    )


def downgrade() -> None:
    op.drop_table("ingestion_checkpoints")
