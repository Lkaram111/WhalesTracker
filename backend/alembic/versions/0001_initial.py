"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2025-03-12 11:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    whale_type = sa.Enum("holder", "trader", "holder_trader", name="whaletype")
    trade_source = sa.Enum("onchain", "hyperliquid", "exchange_flow", name="tradesource")
    trade_direction = sa.Enum(
        "buy",
        "sell",
        "deposit",
        "withdraw",
        "long",
        "short",
        "close_long",
        "close_short",
        name="tradedirection",
    )
    event_type = sa.Enum(
        "large_swap",
        "large_transfer",
        "exchange_flow",
        "perp_trade",
        name="eventtype",
    )

    op.create_table(
        "chains",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "whales",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("address", sa.String(length=256), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("type", whale_type, nullable=False),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.Column("external_explorer_url", sa.Text(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["chain_id"], ["chains.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("address", "chain_id", name="uq_whales_address_chain"),
    )
    op.create_index(
        "ix_whales_last_active_at", "whales", ["last_active_at"], unique=False
    )

    op.create_table(
        "current_wallet_metrics",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("whale_id", sa.String(length=36), nullable=False),
        sa.Column("roi_percent", sa.Float(), nullable=True),
        sa.Column("portfolio_value_usd", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("realized_pnl_usd", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("unrealized_pnl_usd", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("volume_30d_usd", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("trades_30d", sa.Integer(), nullable=True),
        sa.Column("win_rate_percent", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["whale_id"], ["whales.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("whale_id"),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=True),
        sa.Column("type", event_type, nullable=False),
        sa.Column("whale_id", sa.String(length=36), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("value_usd", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("tx_hash", sa.String(length=256), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["chain_id"], ["chains.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["whale_id"], ["whales.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_timestamp", "events", ["timestamp"], unique=False)

    op.create_table(
        "holdings",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("whale_id", sa.String(length=36), nullable=False),
        sa.Column("asset_symbol", sa.String(length=64), nullable=False),
        sa.Column("asset_name", sa.String(length=256), nullable=True),
        sa.Column("chain_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("value_usd", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("portfolio_percent", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["chain_id"], ["chains.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["whale_id"], ["whales.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_holdings_whale_updated", "holdings", ["whale_id", "updated_at"], unique=False
    )

    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("asset_symbol", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_usd", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_price_history_asset_ts",
        "price_history",
        ["asset_symbol", "timestamp"],
        unique=False,
    )

    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("whale_id", sa.String(length=36), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=True),
        sa.Column("source", trade_source, nullable=False),
        sa.Column("platform", sa.String(length=128), nullable=True),
        sa.Column("direction", trade_direction, nullable=False),
        sa.Column("base_asset", sa.String(length=128), nullable=True),
        sa.Column("quote_asset", sa.String(length=128), nullable=True),
        sa.Column("amount_base", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("amount_quote", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("value_usd", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("pnl_usd", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("pnl_percent", sa.Float(), nullable=True),
        sa.Column("tx_hash", sa.String(length=256), nullable=True),
        sa.Column("external_url", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["chain_id"], ["chains.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["whale_id"], ["whales.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_trades_chain_timestamp", "trades", ["chain_id", "timestamp"], unique=False
    )
    op.create_index(
        "ix_trades_whale_timestamp", "trades", ["whale_id", "timestamp"], unique=False
    )

    op.create_table(
        "wallet_metrics_daily",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("whale_id", sa.String(length=36), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("roi_percent", sa.Float(), nullable=True),
        sa.Column("portfolio_value_usd", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("realized_pnl_usd", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("unrealized_pnl_usd", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("volume_1d_usd", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("trades_1d", sa.Integer(), nullable=True),
        sa.Column("win_rate_percent", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["whale_id"], ["whales.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("whale_id", "date", name="uq_wallet_metrics_daily"),
    )


def downgrade() -> None:
    op.drop_table("wallet_metrics_daily")
    op.drop_index("ix_trades_whale_timestamp", table_name="trades")
    op.drop_index("ix_trades_chain_timestamp", table_name="trades")
    op.drop_table("trades")
    op.drop_index("ix_price_history_asset_ts", table_name="price_history")
    op.drop_table("price_history")
    op.drop_index("ix_holdings_whale_updated", table_name="holdings")
    op.drop_table("holdings")
    op.drop_index("ix_events_timestamp", table_name="events")
    op.drop_table("events")
    op.drop_table("current_wallet_metrics")
    op.drop_index("ix_whales_last_active_at", table_name="whales")
    op.drop_table("whales")
    op.drop_table("chains")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS whaletype"))
        op.execute(sa.text("DROP TYPE IF EXISTS tradesource"))
        op.execute(sa.text("DROP TYPE IF EXISTS tradedirection"))
        op.execute(sa.text("DROP TYPE IF EXISTS eventtype"))
