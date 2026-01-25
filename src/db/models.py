"""SQLAlchemy models for EAM."""
from datetime import datetime, date
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import (
    String, Text, Enum, DECIMAL, Integer, BigInteger,
    DateTime, Date, Boolean, JSON, ForeignKey
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
    STABLE = "stable"
    MEDIUM = "medium"
    GAMBLE = "gamble"


class HoldingStatus(PyEnum):
    """Holding status enum."""
    ACTIVE = "active"
    CLOSED = "closed"


class Holding(Base):
    """Holdings table - tracks current positions."""
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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


class DailyQuote(Base):
    """Daily stock quotes table."""
    __tablename__ = "daily_quotes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    market: Mapped[Market] = mapped_column(Enum(Market), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    open: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)
    high: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)
    low: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)
    close: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)
    volume: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        # Unique constraint on symbol + market + trade_date
        {"mysql_charset": "utf8mb4"},
    )
