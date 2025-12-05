from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
    BigInteger,
)
from sqlalchemy.orm import declarative_mixin, declared_attr

from app.db.session import Base


class WhaleType(str, Enum):
    HOLDER = "holder"
    TRADER = "trader"
    HOLDER_TRADER = "holder_trader"


class TradeSource(str, Enum):
    ONCHAIN = "onchain"
    HYPERLIQUID = "hyperliquid"
    EXCHANGE_FLOW = "exchange_flow"


class TradeDirection(str, Enum):
    BUY = "buy"
    SELL = "sell"
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    LONG = "long"
    SHORT = "short"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"


class EventType(str, Enum):
    LARGE_SWAP = "large_swap"
    LARGE_TRANSFER = "large_transfer"
    EXCHANGE_FLOW = "exchange_flow"
    PERP_TRADE = "perp_trade"


# Use explicit Enum instances so Postgres uses the lowercase values (not names) for binds.
_enum_kwargs = {"native_enum": True, "values_callable": lambda obj: [e.value for e in obj]}
whale_type_enum = SqlEnum(WhaleType, name="whaletype", **_enum_kwargs)
trade_source_enum = SqlEnum(TradeSource, name="tradesource", **_enum_kwargs)
trade_direction_enum = SqlEnum(TradeDirection, name="tradedirection", **_enum_kwargs)
event_type_enum = SqlEnum(EventType, name="eventtype", **_enum_kwargs)


@declarative_mixin
class TimestampMixin:
    @declared_attr
    def created_at(cls):
        return Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime(timezone=True),
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False,
        )


class Chain(Base):
    __tablename__ = "chains"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(64), unique=True, nullable=False)
    name = Column(String(128), nullable=False)


class Whale(Base, TimestampMixin):
    __tablename__ = "whales"
    __table_args__ = (
        UniqueConstraint("address", "chain_id", name="uq_whales_address_chain"),
        Index("ix_whales_last_active_at", "last_active_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    address = Column(String(256), nullable=False)
    chain_id = Column(Integer, ForeignKey("chains.id", ondelete="CASCADE"), nullable=False)
    type = Column(whale_type_enum, nullable=False, default=WhaleType.HOLDER)
    labels = Column(JSON, nullable=False, default=list)
    external_explorer_url = Column(Text, nullable=True)
    first_seen_at = Column(DateTime(timezone=True), nullable=True)
    last_active_at = Column(DateTime(timezone=True), nullable=True)


class CurrentWalletMetrics(Base, TimestampMixin):
    __tablename__ = "current_wallet_metrics"

    whale_id = Column(String(36), ForeignKey("whales.id", ondelete="CASCADE"), primary_key=True)
    roi_percent = Column(Float, nullable=True)
    portfolio_value_usd = Column(Numeric(30, 10), nullable=True)
    realized_pnl_usd = Column(Numeric(30, 10), nullable=True)
    unrealized_pnl_usd = Column(Numeric(30, 10), nullable=True)
    volume_30d_usd = Column(Numeric(30, 10), nullable=True)
    trades_30d = Column(Integer, nullable=True)
    win_rate_percent = Column(Float, nullable=True)


class WalletMetricsDaily(Base):
    __tablename__ = "wallet_metrics_daily"
    __table_args__ = (UniqueConstraint("whale_id", "date", name="uq_wallet_metrics_daily"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    whale_id = Column(String(36), ForeignKey("whales.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    roi_percent = Column(Float, nullable=True)
    portfolio_value_usd = Column(Numeric(30, 10), nullable=True)
    realized_pnl_usd = Column(Numeric(30, 10), nullable=True)
    unrealized_pnl_usd = Column(Numeric(30, 10), nullable=True)
    volume_1d_usd = Column(Numeric(30, 10), nullable=True)
    trades_1d = Column(Integer, nullable=True)
    win_rate_percent = Column(Float, nullable=True)


class Holding(Base, TimestampMixin):
    __tablename__ = "holdings"
    __table_args__ = (Index("ix_holdings_whale_updated", "whale_id", "updated_at"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    whale_id = Column(String(36), ForeignKey("whales.id", ondelete="CASCADE"), nullable=False)
    asset_symbol = Column(String(64), nullable=False)
    asset_name = Column(String(256), nullable=True)
    chain_id = Column(Integer, ForeignKey("chains.id", ondelete="SET NULL"), nullable=True)
    amount = Column(Numeric(38, 18), nullable=True)
    value_usd = Column(Numeric(30, 10), nullable=True)
    portfolio_percent = Column(Float, nullable=True)
    cost_basis_usd = Column(Numeric(30, 10), nullable=True)
    avg_unit_cost_usd = Column(Numeric(30, 10), nullable=True)


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        Index("ix_trades_whale_timestamp", "whale_id", "timestamp"),
        Index("ix_trades_chain_timestamp", "chain_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    whale_id = Column(String(36), ForeignKey("whales.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    chain_id = Column(Integer, ForeignKey("chains.id", ondelete="SET NULL"), nullable=True)
    source = Column(trade_source_enum, nullable=False)
    platform = Column(String(128), nullable=True)
    direction = Column(trade_direction_enum, nullable=False)
    base_asset = Column(String(128), nullable=True)
    quote_asset = Column(String(128), nullable=True)
    amount_base = Column(Numeric(38, 18), nullable=True)
    amount_quote = Column(Numeric(38, 18), nullable=True)
    value_usd = Column(Numeric(30, 10), nullable=True)
    pnl_usd = Column(Numeric(30, 10), nullable=True)
    pnl_percent = Column(Float, nullable=True)
    tx_hash = Column(String(256), nullable=True)
    external_url = Column(Text, nullable=True)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_timestamp", "timestamp"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    chain_id = Column(Integer, ForeignKey("chains.id", ondelete="SET NULL"), nullable=True)
    type = Column(event_type_enum, nullable=False)
    whale_id = Column(String(36), ForeignKey("whales.id", ondelete="CASCADE"), nullable=False)
    summary = Column(Text, nullable=True)
    value_usd = Column(Numeric(30, 10), nullable=True)
    tx_hash = Column(String(256), nullable=True)
    details = Column(JSON, nullable=True)


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (Index("ix_price_history_asset_ts", "asset_symbol", "timestamp"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_symbol = Column(String(64), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    price_usd = Column(Numeric(30, 10), nullable=True)


class IngestionCheckpoint(Base, TimestampMixin):
    __tablename__ = "ingestion_checkpoints"
    __table_args__ = (UniqueConstraint("whale_id", name="uq_ingestion_checkpoint_whale"),)

    whale_id = Column(String(36), ForeignKey("whales.id", ondelete="CASCADE"), primary_key=True)
    chain_slug = Column(String(64), nullable=False)
    last_fill_time = Column(BigInteger, nullable=True)  # ms epoch of latest ingested fill
    last_position_time = Column(DateTime(timezone=True), nullable=True)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    __table_args__ = (Index("ix_backtest_runs_whale", "whale_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    whale_id = Column(String(36), ForeignKey("whales.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    leverage = Column(Numeric(20, 10), nullable=True)
    position_size_pct = Column(Float, nullable=True)
    asset_symbols = Column(JSON, nullable=True)
    win_rate_percent = Column(Float, nullable=True)
    trades_copied = Column(Integer, nullable=True)
    max_drawdown_percent = Column(Float, nullable=True)
    max_drawdown_usd = Column(Numeric(30, 10), nullable=True)
    initial_deposit_usd = Column(Numeric(30, 10), nullable=True)
    net_pnl_usd = Column(Numeric(30, 10), nullable=True)
    roi_percent = Column(Float, nullable=True)
