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


class EventsResponse(BaseModel):
    items: list[LiveEvent]


class WhaleCreateRequest(BaseModel):
    address: str
    chain: ChainId
    labels: list[str] = Field(default_factory=list)
    type: WhaleType | None = None


class RoiHistoryResponse(BaseModel):
    points: list[RoiPoint]


class PortfolioHistoryResponse(BaseModel):
    points: list[PortfolioPoint]

class PositionsResponse(BaseModel):
    items: list[OpenPosition]

class PositionsResponse(BaseModel):
    items: list[OpenPosition]
