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
    STABLE = "stable"
    MEDIUM = "medium"
    GAMBLE = "gamble"


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
    tier: TierEnum
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
