"""SQLAlchemy models for market data."""
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import String, DECIMAL, Integer, DateTime, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.db.database import Base


class MacroData(Base):
    """Macro economic data from FRED and other sources."""
    __tablename__ = "macro_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value: Mapped[Decimal] = mapped_column(DECIMAL(18, 6), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint('series_id', 'date', name='uq_macro_data_series_date'),
        {"mysql_charset": "utf8mb4"},
    )
