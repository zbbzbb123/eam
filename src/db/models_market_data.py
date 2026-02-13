"""SQLAlchemy models for market data."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, DECIMAL, Integer, DateTime, Date, Text, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import JSON
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
    """Northbound capital flow data (北向资金) from TuShare moneyflow_hsgt."""
    __tablename__ = "northbound_flow"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    net_flow: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)  # 北向交易额 (亿元) - TuShare north_money
    hgt: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)  # 沪股通交易额 (亿元)
    sgt: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)  # 深股通交易额 (亿元)
    south_money: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)  # 南向交易额 (亿元)
    quota_remaining: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)  # 当日余额 (亿元)

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


class CnMacroRecord(Base):
    """Chinese macroeconomic data (PMI/CPI/M2) from EastMoney."""
    __tablename__ = "cn_macro_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    indicator: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value: Mapped[Decimal] = mapped_column(DECIMAL(18, 6), nullable=False)
    yoy_change: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 6), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('indicator', 'date', name='uq_cn_macro_indicator_date'),
        {"mysql_charset": "utf8mb4"},
    )


class SectorSnapshot(Base):
    """Daily sector/industry snapshot from Sina Finance."""
    __tablename__ = "sector_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    sector_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "industry" or "concept"
    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    stock_count: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_price: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)
    change_pct: Mapped[Decimal] = mapped_column(DECIMAL(10, 4), nullable=False)
    volume: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)
    leading_stock: Mapped[str] = mapped_column(String(50), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('snapshot_date', 'sector_type', 'code', name='uq_sector_date_type_code'),
        {"mysql_charset": "utf8mb4"},
    )


class MarketIndicatorSnapshot(Base):
    """Market indicator snapshots (VIX, gold, silver, copper) from YFinance."""
    __tablename__ = "market_indicator_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)
    change_pct: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 4), nullable=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('symbol', 'date', name='uq_market_indicator_symbol_date'),
        {"mysql_charset": "utf8mb4"},
    )


class FundamentalSnapshot(Base):
    """Company fundamental data snapshots."""
    __tablename__ = "fundamental_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(5), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    market_cap: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(20, 2), nullable=True)
    pe_ratio: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 4), nullable=True)
    pb_ratio: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 4), nullable=True)
    revenue: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(20, 2), nullable=True)
    net_income: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(20, 2), nullable=True)
    revenue_growth: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 6), nullable=True)
    profit_margin: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 6), nullable=True)
    analyst_rating: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    target_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('symbol', 'snapshot_date', name='uq_fundamental_symbol_date'),
        {"mysql_charset": "utf8mb4"},
    )


class SectorFlowSnapshot(Base):
    """Daily sector fund flow snapshot from EastMoney."""
    __tablename__ = "sector_flow_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    sector_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "industry" or "concept"
    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    main_net_inflow: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    super_large_inflow: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    large_inflow: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    medium_inflow: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    small_inflow: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    main_pct: Mapped[Decimal] = mapped_column(DECIMAL(10, 4), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('snapshot_date', 'sector_type', 'code', name='uq_sector_flow_date_type_code'),
        {"mysql_charset": "utf8mb4"},
    )


class MarketBreadthSnapshot(Base):
    """A-share market breadth (advance/decline counts) snapshot."""
    __tablename__ = "market_breadth_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    index_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    index_name: Mapped[str] = mapped_column(String(50), nullable=False)
    close: Mapped[Decimal] = mapped_column(DECIMAL(12, 4), nullable=False)
    change_pct: Mapped[Decimal] = mapped_column(DECIMAL(10, 4), nullable=False)
    advancing: Mapped[int] = mapped_column(Integer, nullable=False)
    declining: Mapped[int] = mapped_column(Integer, nullable=False)
    unchanged: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('snapshot_date', 'index_code', name='uq_breadth_date_index'),
        {"mysql_charset": "utf8mb4"},
    )


class IndexValuationSnapshot(Base):
    """A-share index valuation (PE/PB) from TuShare."""
    __tablename__ = "index_valuation_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    pe: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 4), nullable=True)
    pb: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 4), nullable=True)
    total_mv: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(20, 2), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('ts_code', 'trade_date', name='uq_index_val_code_date'),
        {"mysql_charset": "utf8mb4"},
    )


class FundNavSnapshot(Base):
    """ETF/Fund NAV (net asset value) from TuShare."""
    __tablename__ = "fund_nav_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    nav_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    unit_nav: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 6), nullable=True)
    accum_nav: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 6), nullable=True)
    adj_nav: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 6), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('ts_code', 'nav_date', name='uq_fund_nav_code_date'),
        {"mysql_charset": "utf8mb4"},
    )


class YieldSpreadRecord(Base):
    """10Y-2Y Treasury yield spread history."""
    __tablename__ = "yield_spreads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    dgs2: Mapped[Decimal] = mapped_column(DECIMAL(8, 4), nullable=False)
    dgs10: Mapped[Decimal] = mapped_column(DECIMAL(8, 4), nullable=False)
    spread: Mapped[Decimal] = mapped_column(DECIMAL(8, 4), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        {"mysql_charset": "utf8mb4"},
    )


class GeneratedReport(Base):
    """Pre-generated report storage."""
    __tablename__ = "generated_report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # "daily" or "weekly"
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # One-line summary for list view
    content: Mapped[dict] = mapped_column(JSON, nullable=False)  # Full report JSON

    __table_args__ = (
        Index("ix_generated_report_type_date", "report_type", "generated_at"),
        {"mysql_charset": "utf8mb4"},
    )
