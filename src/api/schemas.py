"""Pydantic schemas for API request/response validation."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


class MarketEnum(str, Enum):
    """Stock market enum."""
    US = "US"
    HK = "HK"
    CN = "CN"


class TierEnum(str, Enum):
    """Portfolio tier enum."""
    CORE = "core"
    GROWTH = "growth"
    GAMBLE = "gamble"


class AssetTypeEnum(str, Enum):
    """Investable asset type."""
    STOCK = "stock"
    ETF = "etf"
    CASH = "cash"


class StrategyBucketEnum(str, Enum):
    """AI-theme strategy allocation buckets."""
    AI_INFRASTRUCTURE = "ai_infrastructure"
    AI_APPLICATION = "ai_application"
    MISC = "misc"
    CASH = "cash"


class HoldingStatusEnum(str, Enum):
    """Holding status enum."""
    ACTIVE = "active"
    CLOSED = "closed"


class TransactionActionEnum(str, Enum):
    """Transaction action enum."""
    BUY = "buy"
    SELL = "sell"


# ===== Holding Schemas =====

class HoldingBase(BaseModel):
    """Base schema for Holding."""
    symbol: str = Field(..., min_length=1, max_length=20)
    market: MarketEnum
    tier: TierEnum = TierEnum.GAMBLE
    asset_type: AssetTypeEnum = AssetTypeEnum.STOCK
    strategy_bucket: StrategyBucketEnum = StrategyBucketEnum.MISC
    strategy_sub_bucket: Optional[str] = Field(None, max_length=100)
    target_weight_pct: Optional[Decimal] = Field(None, ge=0, le=100)
    research_priority: int = Field(0, ge=0, le=5)
    quantity: Decimal = Field(..., gt=0)
    avg_cost: Decimal = Field(..., gt=0)
    first_buy_date: date
    buy_reason: str = Field(..., min_length=1)
    stop_loss_price: Optional[Decimal] = Field(None, gt=0)
    take_profit_price: Optional[Decimal] = Field(None, gt=0)
    custom_keywords: Optional[List[str]] = None
    notes: Optional[str] = None


class HoldingCreate(HoldingBase):
    """Schema for creating a new holding."""
    pass


class HoldingUpdate(BaseModel):
    """Schema for updating a holding."""
    tier: Optional[TierEnum] = None
    asset_type: Optional[AssetTypeEnum] = None
    strategy_bucket: Optional[StrategyBucketEnum] = None
    strategy_sub_bucket: Optional[str] = Field(None, max_length=100)
    target_weight_pct: Optional[Decimal] = Field(None, ge=0, le=100)
    research_priority: Optional[int] = Field(None, ge=0, le=5)
    quantity: Optional[Decimal] = Field(None, gt=0)
    avg_cost: Optional[Decimal] = Field(None, gt=0)
    stop_loss_price: Optional[Decimal] = Field(None, gt=0)
    take_profit_price: Optional[Decimal] = Field(None, gt=0)
    custom_keywords: Optional[List[str]] = None
    notes: Optional[str] = None
    status: Optional[HoldingStatusEnum] = None


class HoldingResponse(HoldingBase):
    """Schema for holding response."""
    id: int
    status: HoldingStatusEnum
    created_at: datetime
    updated_at: datetime
    # Override quantity to allow 0 for closed positions
    quantity: Decimal = Field(..., ge=0)

    model_config = ConfigDict(from_attributes=True)


# ===== Transaction Schemas =====

class TransactionBase(BaseModel):
    """Base schema for Transaction."""
    action: TransactionActionEnum
    quantity: Decimal = Field(..., gt=0)
    price: Decimal = Field(..., gt=0)
    reason: str = Field(..., min_length=1)
    transaction_date: datetime


class TransactionCreate(TransactionBase):
    """Schema for creating a new transaction."""
    pass


class TransactionResponse(TransactionBase):
    """Schema for transaction response."""
    id: int
    holding_id: int
    total_amount: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===== Daily Quote Schemas =====

class DailyQuoteResponse(BaseModel):
    """Schema for daily quote response."""
    symbol: str
    market: MarketEnum
    trade_date: date
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Optional[Decimal] = None
    volume: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# ===== Portfolio Overview Schemas =====

class TierAllocation(BaseModel):
    """Schema for tier allocation."""
    tier: TierEnum
    target_pct: Decimal
    actual_pct: Decimal
    drift_pct: Decimal
    market_value: Decimal


class PortfolioOverview(BaseModel):
    """Schema for portfolio overview."""
    total_value: Decimal
    allocations: List[TierAllocation]
    holdings_count: int


# ===== Signal Schemas =====

class SignalTypeEnum(str, Enum):
    """Signal type enum."""
    SECTOR = "sector"
    PRICE = "price"
    MACRO = "macro"
    SMART_MONEY = "smart_money"
    HOLDING = "holding"


class SignalSeverityEnum(str, Enum):
    """Signal severity enum."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SignalStatusEnum(str, Enum):
    """Signal status enum."""
    ACTIVE = "active"
    READ = "read"
    ARCHIVED = "archived"


class SignalCreate(BaseModel):
    """Schema for creating a signal."""
    signal_type: SignalTypeEnum
    sector: Optional[str] = Field(None, max_length=50)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    severity: SignalSeverityEnum
    source: str = Field(..., min_length=1, max_length=100)
    data: Optional[dict] = None
    related_symbols: Optional[List[str]] = None
    holding_id: Optional[int] = None
    expires_at: Optional[datetime] = None


class SignalResponse(BaseModel):
    """Schema for signal response."""
    id: int
    signal_type: SignalTypeEnum
    sector: Optional[str] = None
    title: str
    description: str
    severity: SignalSeverityEnum
    status: SignalStatusEnum
    source: str
    data: Optional[dict] = None
    related_symbols: Optional[List[str]] = None
    holding_id: Optional[int] = None
    telegram_sent: bool
    telegram_sent_at: Optional[datetime] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SignalUpdate(BaseModel):
    """Schema for updating a signal."""
    status: Optional[SignalStatusEnum] = None


# ===== Portfolio Summary Schemas =====

class TierSummaryResponse(BaseModel):
    """Schema for tier summary in portfolio."""
    tier: str
    target_pct: Decimal
    actual_pct: Decimal
    deviation: Decimal
    market_value: Decimal
    holdings_count: int


class PortfolioSummaryResponse(BaseModel):
    """Schema for portfolio summary."""
    total_value: Decimal
    tiers: List[TierSummaryResponse]


class HoldingSummaryResponse(BaseModel):
    """Schema for a holding with P&L info."""
    id: int
    symbol: str
    name: str = ""
    market: MarketEnum
    tier: TierEnum
    asset_type: AssetTypeEnum = AssetTypeEnum.STOCK
    strategy_bucket: StrategyBucketEnum = StrategyBucketEnum.MISC
    strategy_sub_bucket: Optional[str] = None
    target_weight_pct: Optional[Decimal] = None
    portfolio_weight_pct: Decimal = Decimal("0")
    research_priority: int = 0
    quantity: Decimal
    avg_cost: Decimal
    current_price: Decimal
    market_value: Decimal
    pnl: Decimal
    pnl_pct: Decimal

    model_config = ConfigDict(from_attributes=True)


# ===== Weekly Report Schemas =====

class TierSummaryReportResponse(BaseModel):
    """Tier summary within a weekly report."""
    tier: str
    target_pct: Decimal
    actual_pct: Decimal
    deviation_pct: Decimal
    market_value: Decimal
    holdings_count: int


class PortfolioSummaryReportResponse(BaseModel):
    """Portfolio summary within a weekly report."""
    total_value: Decimal
    tiers: List[TierSummaryReportResponse]


class SignalSummaryItemResponse(BaseModel):
    """Signal summary item."""
    sector: str
    count: int
    max_severity: str
    titles: List[str]


class RiskAlertResponse(BaseModel):
    """Risk alert."""
    level: str
    message: str
    symbol: Optional[str] = None


class ActionItemResponse(BaseModel):
    """Action item."""
    priority: str
    description: str


class WeeklyReportResponse(BaseModel):
    """Full weekly report response."""
    report_date: date
    portfolio_summary: PortfolioSummaryReportResponse
    signal_summary: List[SignalSummaryItemResponse]
    risk_alerts: List[RiskAlertResponse]
    action_items: List[ActionItemResponse]


# ===== Enhanced Report Schemas =====

class AnalyzerSectionResponse(BaseModel):
    """A single analyzer section in the enhanced report."""
    name: str
    rating: Optional[str] = None
    score: Optional[int] = None
    summary: str
    details: List[str] = []
    recommendations: List[str] = []
    data: Optional[dict] = None


class EnhancedReportResponse(BaseModel):
    """Full enhanced report response (daily or weekly)."""
    report_date: date
    report_type: str  # "daily" or "weekly"
    sections: List[AnalyzerSectionResponse]
    ai_advice: Optional[str] = None
    # Legacy fields (populated in weekly reports)
    portfolio_summary: Optional[PortfolioSummaryReportResponse] = None
    signal_summary: List[SignalSummaryItemResponse] = []
    risk_alerts: List[RiskAlertResponse] = []
    action_items: List[ActionItemResponse] = []


# ===== Generated Report Schemas =====

class GeneratedReportListItem(BaseModel):
    """List item for generated reports."""
    id: int
    report_type: str
    report_date: date
    generated_at: datetime
    summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class GeneratedReportDetail(BaseModel):
    """Full generated report with content."""
    id: int
    report_type: str
    report_date: date
    generated_at: datetime
    summary: Optional[str] = None
    content: dict

    model_config = ConfigDict(from_attributes=True)


# ===== Transaction Preview / Position Update Schemas =====

class TransactionPreviewRequest(BaseModel):
    """Request to preview an inferred transaction from position changes."""
    new_quantity: Decimal = Field(..., ge=0)
    new_avg_cost: Decimal = Field(..., gt=0)
    transaction_date: Optional[datetime] = None


class TransactionPreviewResponse(BaseModel):
    """Response with inferred transaction details."""
    action: str
    quantity: Decimal
    inferred_price: Decimal
    suggested_date: Optional[str] = None
    old_quantity: Decimal
    old_avg_cost: Decimal


class PositionUpdateRequest(BaseModel):
    """Request to update a position with inferred transaction."""
    new_quantity: Decimal = Field(..., ge=0)
    new_avg_cost: Decimal = Field(..., gt=0)
    transaction_date: Optional[datetime] = None
    reason: Optional[str] = None


# ===== Dashboard Schemas =====

class DashboardHoldingItem(BaseModel):
    """Single holding within a dashboard tier."""
    id: int
    symbol: str
    name: str = ""
    market: MarketEnum
    asset_type: AssetTypeEnum = AssetTypeEnum.STOCK
    strategy_bucket: StrategyBucketEnum = StrategyBucketEnum.MISC
    strategy_sub_bucket: Optional[str] = None
    target_weight_pct: Optional[Decimal] = None
    portfolio_weight_pct: Decimal = Decimal("0")
    current_price: Decimal
    market_value: Decimal
    weight_in_tier: Decimal      # % within tier
    pnl_7d: Decimal
    pnl_7d_pct: Decimal
    pnl_30d: Decimal
    pnl_30d_pct: Decimal


class DashboardTier(BaseModel):
    """Tier summary for dashboard."""
    tier: str
    market_value: Decimal
    weight_pct: Decimal          # % of total portfolio
    pnl_7d: Decimal
    pnl_7d_pct: Decimal
    pnl_30d: Decimal
    pnl_30d_pct: Decimal
    holdings: List[DashboardHoldingItem]


class DashboardResponse(BaseModel):
    """Full dashboard response."""
    total_value: Decimal
    pnl_7d: Decimal
    pnl_7d_pct: Decimal
    pnl_30d: Decimal
    pnl_30d_pct: Decimal
    tiers: List[DashboardTier]


# ===== Trade Date Prediction & Backfill Schemas =====

class TradeDateCandidate(BaseModel):
    """A candidate trading date for an initial purchase."""
    trade_date: str          # ISO date
    close: Decimal
    low: Decimal
    high: Decimal
    confidence: str          # "high", "medium", "low"
    price_diff_pct: Decimal  # abs((close - avg_cost) / avg_cost * 100)


class PredictTradeDateResponse(BaseModel):
    """Response for trade date prediction."""
    holding_id: int
    symbol: str
    avg_cost: Decimal
    first_buy_date: str
    has_transactions: bool   # whether any transactions exist already
    candidates: List[TradeDateCandidate]


class BackfillTransactionRequest(BaseModel):
    """Request to backfill an initial transaction."""
    transaction_date: date   # user-confirmed date from candidates


# ===== AI Strategy Allocation Schemas =====

class StrategyTargetResponse(BaseModel):
    """Target allocation for an AI strategy bucket."""
    bucket: StrategyBucketEnum
    target_pct: Decimal
    actual_pct: Decimal = Decimal("0")
    market_value: Decimal = Decimal("0")


class StrategyTargetUpdateItem(BaseModel):
    """Request item for updating a strategy bucket target."""
    bucket: StrategyBucketEnum
    target_pct: Decimal = Field(..., ge=0, le=100)


class StrategyTargetUpdateRequest(BaseModel):
    """Bulk update for strategy allocation targets."""
    targets: List[StrategyTargetUpdateItem]


class RebalanceBucketItem(BaseModel):
    """Bucket-level rebalance status."""
    bucket: StrategyBucketEnum
    target_pct: Decimal
    actual_pct: Decimal
    drift_pct: Decimal
    relative_drift_pct: Optional[Decimal] = None
    market_value: Decimal
    action: str
    severity: str
    trade_amount_cny: Decimal


class RebalanceHoldingItem(BaseModel):
    """Holding-level rebalance status."""
    holding_id: int
    symbol: str
    market: MarketEnum
    bucket: StrategyBucketEnum
    target_pct: Decimal
    actual_pct: Decimal
    drift_pct: Decimal
    relative_drift_pct: Optional[Decimal] = None
    market_value: Decimal
    action: str
    severity: str
    trade_amount_cny: Decimal


class RebalancePlanResponse(BaseModel):
    """Full AI strategy rebalance plan."""
    total_value: Decimal
    warning_threshold_pct: Decimal
    critical_threshold_pct: Decimal
    buckets: List[RebalanceBucketItem]
    holdings: List[RebalanceHoldingItem]
    needs_rebalance: bool
    needs_trade: bool
