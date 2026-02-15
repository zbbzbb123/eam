"""SQLAlchemy models for EAM."""
from datetime import datetime, date
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import (
    String, Text, Enum, DECIMAL, Integer, BigInteger,
    DateTime, Date, Boolean, JSON, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.db.database import Base


class Market(PyEnum):
    """Stock market enum."""
    US = "US"
    HK = "HK"
    CN = "CN"


class Tier(PyEnum):
    """Portfolio tier enum."""
    CORE = "core"
    GROWTH = "growth"
    GAMBLE = "gamble"


class HoldingStatus(PyEnum):
    """Holding status enum."""
    ACTIVE = "active"
    CLOSED = "closed"


class Holding(Base):
    """Holdings table - tracks current positions."""
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    market: Mapped[Market] = mapped_column(Enum(Market), nullable=False)
    tier: Mapped[Tier] = mapped_column(Enum(Tier), nullable=False, index=True)

    quantity: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)
    avg_cost: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)

    first_buy_date: Mapped[date] = mapped_column(Date, nullable=False)
    buy_reason: Mapped[str] = mapped_column(Text, nullable=False)

    stop_loss_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)
    take_profit_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)

    custom_keywords: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[HoldingStatus] = mapped_column(
        Enum(HoldingStatus), default=HoldingStatus.ACTIVE, index=True
    )

    # Custom __init__ is required to ensure the default status is set at Python
    # instantiation time (before session.add). SQLAlchemy's `default=` only applies
    # when the object is persisted to the database, but tests verify the default
    # is available immediately after object creation.
    def __init__(self, **kwargs):
        if 'status' not in kwargs:
            kwargs['status'] = HoldingStatus.ACTIVE
        super().__init__(**kwargs)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction", back_populates="holding", cascade="all, delete-orphan"
    )


class TransactionAction(PyEnum):
    """Transaction action enum."""
    BUY = "buy"
    SELL = "sell"


class Transaction(Base):
    """Transaction history table."""
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    holding_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("holdings.id"), nullable=False, index=True
    )

    action: Mapped[TransactionAction] = mapped_column(Enum(TransactionAction), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)
    price: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)

    reason: Mapped[str] = mapped_column(Text, nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relationships
    holding: Mapped["Holding"] = relationship("Holding", back_populates="transactions")


class Watchlist(Base):
    """Watchlist items — symbols to track but not in portfolio."""
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    market: Mapped[Market] = mapped_column(Enum(Market), nullable=False)
    theme: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint('symbol', 'market', 'user_id', name='uq_watchlist_symbol_market_user'),
        {"mysql_charset": "utf8mb4"},
    )


class DailyQuote(Base):
    """Daily stock quotes table."""
    __tablename__ = "daily_quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    market: Mapped[Market] = mapped_column(Enum(Market), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    open: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)
    high: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)
    low: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)
    close: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)
    volume: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        UniqueConstraint('symbol', 'market', 'trade_date', name='uq_daily_quote_symbol_market_date'),
        {"mysql_charset": "utf8mb4"},
    )


class SignalType(PyEnum):
    """Signal type enum."""
    SECTOR = "sector"
    PRICE = "price"
    MACRO = "macro"
    SMART_MONEY = "smart_money"
    HOLDING = "holding"


class SignalSeverity(PyEnum):
    """Signal severity enum."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SignalStatus(PyEnum):
    """Signal status enum."""
    ACTIVE = "active"
    READ = "read"
    ARCHIVED = "archived"


class Signal(Base):
    """Investment signals table."""
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )

    signal_type: Mapped[SignalType] = mapped_column(Enum(SignalType), nullable=False, index=True)
    sector: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    severity: Mapped[SignalSeverity] = mapped_column(Enum(SignalSeverity), nullable=False, index=True)
    status: Mapped[SignalStatus] = mapped_column(
        Enum(SignalStatus), default=SignalStatus.ACTIVE, index=True
    )

    source: Mapped[str] = mapped_column(String(100), nullable=False)
    data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    related_symbols: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    holding_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("holdings.id"), nullable=True, index=True
    )

    telegram_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __init__(self, **kwargs):
        if 'status' not in kwargs:
            kwargs['status'] = SignalStatus.ACTIVE
        if 'telegram_sent' not in kwargs:
            kwargs['telegram_sent'] = False
        super().__init__(**kwargs)

    __table_args__ = (
        {"mysql_charset": "utf8mb4"},
    )
