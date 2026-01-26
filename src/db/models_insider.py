"""SQLAlchemy models for insider trading data."""
from datetime import datetime, date
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    String, Text, Enum, DECIMAL, Integer, BigInteger,
    DateTime, Date, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.db.database import Base


class InsiderTradeType(PyEnum):
    """Insider trade type enum."""
    PURCHASE = "purchase"
    SALE = "sale"


class InsiderTrade(Base):
    """Insider trade table - stores SEC Form 4 filings from OpenInsider.

    This table stores insider trading data including purchases and sales
    by company executives, directors, and major shareholders.
    """
    __tablename__ = "insider_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Filing and trade dates
    filing_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Company information
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Insider information
    insider_name: Mapped[str] = mapped_column(String(200), nullable=False)
    insider_title: Mapped[str] = mapped_column(String(100), nullable=False)

    # Trade details
    trade_type: Mapped[InsiderTradeType] = mapped_column(
        Enum(InsiderTradeType), nullable=False, index=True
    )
    price: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shares_owned_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    value: Mapped[Decimal] = mapped_column(DECIMAL(18, 2), nullable=False)

    # Data source and metadata
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    sec_form_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    __table_args__ = (
        # Unique constraint to prevent duplicate entries
        UniqueConstraint(
            'filing_date', 'ticker', 'insider_name', 'trade_type', 'price', 'quantity',
            name='uq_insider_trade_unique'
        ),
        {"mysql_charset": "utf8mb4"},
    )
