from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ChainId = Literal["ethereum", "bitcoin", "hyperliquid"]
WhaleType = Literal["holder", "trader", "holder_trader"]
TradeSource = Literal["onchain", "hyperliquid", "exchange_flow"]
EventType = Literal["large_swap", "large_transfer", "exchange_flow", "perp_trade"]


class DashboardSummary(BaseModel):
    total_tracked_whales: int
    active_whales_24h: int
    total_volume_24h_usd: float
    hyperliquid_whales: int


class WhaleSummary(BaseModel):
    id: str
    address: str
    chain: ChainId
    type: WhaleType
    labels: list[str]
    roi_percent: float
    realized_pnl_usd: float
    unrealized_pnl_usd: float | None
    portfolio_value_usd: float
    volume_30d_usd: float
    trades_30d: int
    win_rate_percent: float | None
    last_active_at: datetime


class Holding(BaseModel):
    asset_symbol: str
    asset_name: str
    chain: ChainId
    amount: str
    value_usd: float
    portfolio_percent: float


class RoiPoint(BaseModel):
    timestamp: datetime
    roi_percent: float


class PortfolioPoint(BaseModel):
    timestamp: datetime
    value_usd: float


class OpenPosition(BaseModel):
    asset: str
    direction: Literal["long", "short"]
    size: float
    entry_price_usd: float | None = Field(default=None)
    mark_price_usd: float | None = Field(default=None)
    value_usd: float | None = Field(default=None)
    unrealized_pnl_usd: float | None = Field(default=None)


class Trade(BaseModel):
    id: str
    timestamp: datetime
    chain: ChainId
    source: TradeSource
    platform: str
    direction: Literal[
        "buy",
        "sell",
        "deposit",
        "withdraw",
        "long",
        "short",
        "close_long",
        "close_short",
    ]
    base_asset: str | None = Field(default=None)
    quote_asset: str | None = Field(default=None)
    amount_base: str | None = Field(default=None)
    amount_quote: str | None = Field(default=None)
    value_usd: float
    pnl_usd: float | None
    pnl_percent: float | None
    tx_hash: str | None
    external_url: str | None
    price_usd: float | None = Field(default=None)
    open_price_usd: float | None = Field(default=None)
    close_price_usd: float | None = Field(default=None)


class LiveEventWallet(BaseModel):
    address: str
    chain: ChainId
    label: str | None


class LiveEvent(BaseModel):
    id: str
    timestamp: datetime
    chain: ChainId
    type: EventType
    wallet: LiveEventWallet
    summary: str
    value_usd: float
    tx_hash: str | None
    details: dict


class WalletSummary(BaseModel):
    id: str | None = None
    address: str
    chain: ChainId
    type: WhaleType
    labels: list[str]
    external_explorer_url: str


class WalletMetrics(BaseModel):
    roi_percent: float
    realized_pnl_usd: float
    unrealized_pnl_usd: float | None
    portfolio_value_usd: float
    volume_30d_usd: float
    trades_30d: int
    win_rate_percent: float | None
    first_seen_at: datetime
    last_active_at: datetime


class WalletDetail(BaseModel):
    wallet: WalletSummary
    metrics: WalletMetrics
    holdings: list[Holding]
    notes: str | None = None


class ListResponse(BaseModel):
    items: list[WhaleSummary]
    total: int


class TradesResponse(BaseModel):
    items: list[Trade]
    next_cursor: str | None = None
    total: int


class EventsResponse(BaseModel):
    items: list[LiveEvent]


class WhaleCreateRequest(BaseModel):
    address: str
    chain: ChainId
    labels: list[str] = Field(default_factory=list)
    type: WhaleType | None = None


class WhaleUpdateRequest(BaseModel):
    labels: list[str] | None = None
    type: WhaleType | None = None


class DeleteResponse(BaseModel):
    success: bool


class BackfillStatus(BaseModel):
    whale_id: str
    chain: ChainId | None = None
    status: Literal["idle", "running", "done", "error"]
    progress: float
    message: str | None = None
    updated_at: datetime | None = None


class ResolveWhaleResponse(BaseModel):
    whale_id: str


class RoiHistoryResponse(BaseModel):
    points: list[RoiPoint]


class PortfolioHistoryResponse(BaseModel):
    points: list[PortfolioPoint]

class PositionsResponse(BaseModel):
    items: list[OpenPosition]


class CopierBacktestRequest(BaseModel):
    chain: ChainId
    address: str
    initial_deposit_usd: float = Field(gt=0, description="Starting capital for the backtest")
    position_size_pct: float | None = Field(
        default=None, ge=0, le=200, description="Optional override: % of whale size to copy"
    )
    fee_bps: float = Field(default=5.0, ge=0, le=1000, description="Per-trade fee in bps")
    slippage_bps: float = Field(default=5.0, ge=0, le=1000, description="Per-trade slippage in bps")
    leverage: float | None = Field(
        default=1.0,
        ge=0.1,
        le=100.0,
        description="Leverage multiplier applied to position notional",
    )
    start: datetime | None = Field(default=None, description="Optional start time filter")
    end: datetime | None = Field(default=None, description="Optional end time filter")
    max_trades: int | None = Field(
        default=None,
        ge=1,
        le=5000,
        description="Optional limit on trades to simulate; defaults to all available",
    )
    trades_limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Pagination: max trade rows to return in the response",
    )
    trades_offset: int = Field(
        default=0,
        ge=0,
        description="Pagination: offset of trade rows to return in the response",
    )
    asset_symbols: list[str] | None = Field(
        default=None,
        description="Optional allowlist of asset symbols to include; defaults to all traded assets",
    )
    include_price_points: bool = Field(
        default=False,
        description="Return price points used for marking to avoid re-downloading later",
    )


class BacktestTradeResult(BaseModel):
    id: int
    timestamp: datetime
    direction: str
    base_asset: str | None
    notional_usd: float
    pnl_usd: float
    fee_usd: float
    slippage_usd: float
    net_pnl_usd: float
    cumulative_pnl_usd: float
    equity_usd: float
    unrealized_pnl_usd: float
    position_size_base: float | None


class BacktestSummary(BaseModel):
    initial_deposit_usd: float
    recommended_position_pct: float
    used_position_pct: float
    leverage_used: float | None = None
    asset_symbols: list[str] | None = None
    total_fees_usd: float
    total_slippage_usd: float
    gross_pnl_usd: float
    net_pnl_usd: float
    roi_percent: float
    trades_copied: int
    win_rate_percent: float | None
    max_drawdown_percent: float | None = None
    max_drawdown_usd: float | None = None
    start: datetime | None
    end: datetime | None


class BacktestRunSummary(BaseModel):
    id: int
    whale_id: str
    created_at: datetime
    leverage: float | None
    position_size_pct: float | None
    asset_symbols: list[str] | None
    win_rate_percent: float | None
    trades_copied: int | None
    max_drawdown_percent: float | None
    max_drawdown_usd: float | None
    initial_deposit_usd: float | None
    net_pnl_usd: float | None
    roi_percent: float | None


class LiveTrade(BaseModel):
    id: int
    timestamp: datetime
    direction: str
    base_asset: str | None
    value_usd: float | None


class LiveTradesResponse(BaseModel):
    trades: list[LiveTrade]


class StartCopierRequest(BaseModel):
    chain: ChainId
    address: str
    run_id: int
    execute: bool = Field(default=False, description="If true, will submit live orders; otherwise dry-run.")
    position_size_pct: float | None = Field(
        default=None, ge=0, le=200, description="Override position size percent; defaults to backtest value"
    )


class CopierSessionStatus(BaseModel):
    session_id: int
    active: bool
    processed: int
    errors: list[str]
    notifications: list[str] = Field(default_factory=list)


class CopierBacktestResponse(BaseModel):
    summary: BacktestSummary
    trades: list[BacktestTradeResult]
    equity_curve: list[dict]
    price_points: dict[str, list[dict]] | None = None
    trades_total: int
    trades_limit: int
    trades_offset: int


class WhaleAssetsResponse(BaseModel):
    assets: list[str]
