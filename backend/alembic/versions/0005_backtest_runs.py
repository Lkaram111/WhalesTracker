"""add backtest runs table

Revision ID: 0005_backtest_runs
Revises: 0004_trades_unique_tx
Create Date: 2025-12-04 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0005_backtest_runs"
down_revision = "0004_trades_unique_tx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "whale_id",
            sa.String(length=36),
            sa.ForeignKey("whales.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("leverage", sa.Numeric(20, 10), nullable=True),
        sa.Column("position_size_pct", sa.Float(), nullable=True),
        sa.Column("asset_symbols", sa.JSON(), nullable=True),
        sa.Column("win_rate_percent", sa.Float(), nullable=True),
        sa.Column("trades_copied", sa.Integer(), nullable=True),
        sa.Column("max_drawdown_percent", sa.Float(), nullable=True),
        sa.Column("max_drawdown_usd", sa.Numeric(30, 10), nullable=True),
        sa.Column("initial_deposit_usd", sa.Numeric(30, 10), nullable=True),
        sa.Column("net_pnl_usd", sa.Numeric(30, 10), nullable=True),
        sa.Column("roi_percent", sa.Float(), nullable=True),
    )
    op.create_index("ix_backtest_runs_whale", "backtest_runs", ["whale_id"])


def downgrade() -> None:
    op.drop_index("ix_backtest_runs_whale", table_name="backtest_runs")
    op.drop_table("backtest_runs")
