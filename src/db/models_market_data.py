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


class NorthboundFlow(Base):
    """Northbound capital flow data (北向资金) from AkShare."""
    __tablename__ = "northbound_flow"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    net_flow: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)  # 每日北向资金净流入 (亿元)
    quota_remaining: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=True)  # 当日余额 (亿元)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint('trade_date', name='uq_northbound_flow_trade_date'),
        {"mysql_charset": "utf8mb4"},
    )


class NorthboundHolding(Base):
    """Northbound capital individual stock holdings (北向资金持股) from AkShare."""
    __tablename__ = "northbound_holding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # 股票代码
    name: Mapped[str] = mapped_column(String(50), nullable=False)  # 股票名称
    holding: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)  # 今日持股 (万股)
    market_value: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=True)  # 今日参考市值 (亿元)
    holding_change: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=True)  # 今日持股变化 (万股)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint('trade_date', 'symbol', name='uq_northbound_holding_date_symbol'),
        {"mysql_charset": "utf8mb4"},
    )
