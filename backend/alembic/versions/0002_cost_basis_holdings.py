"""add cost basis columns to holdings

Revision ID: 0002_cost_basis_holdings
Revises: 0001_initial
Create Date: 2025-03-12 13:50:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_cost_basis_holdings"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "holdings",
        sa.Column("cost_basis_usd", sa.Numeric(precision=30, scale=10), nullable=True),
    )
    op.add_column(
        "holdings",
        sa.Column("avg_unit_cost_usd", sa.Numeric(precision=30, scale=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("holdings", "avg_unit_cost_usd")
    op.drop_column("holdings", "cost_basis_usd")
