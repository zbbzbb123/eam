"""SQLAlchemy models for institutional holdings data."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    String, Text, DECIMAL, Integer, BigInteger,
    DateTime, Date, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.db.database import Base


class InstitutionalHolding(Base):
    """Institutional holding table - stores SEC 13F-HR filing data.

    This table stores institutional holdings data from 13F filings,
    which are quarterly reports filed by institutional investment managers
    with at least $100 million in assets under management.
    """
    __tablename__ = "institutional_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Institution information
    institution_cik: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    institution_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Report date (end of reporting quarter)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Security information
    cusip: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    stock_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Holding details
    shares: Mapped[int] = mapped_column(BigInteger, nullable=False)
    value: Mapped[Decimal] = mapped_column(DECIMAL(20, 2), nullable=False)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    __table_args__ = (
        # Unique constraint to prevent duplicate entries
        UniqueConstraint(
            'institution_cik', 'report_date', 'cusip',
            name='uq_institutional_holding_unique'
        ),
        {"mysql_charset": "utf8mb4"},
    )
