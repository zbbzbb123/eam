"""Storage service: maps collector outputs to DB upserts."""
import logging
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert as mysql_insert

from src.db.models_market_data import (
    CnMacroRecord,
    FundNavSnapshot,
    IndexValuationSnapshot,
    MacroData,
    MarketBreadthSnapshot,
    NorthboundFlow,
    SectorFlowSnapshot,
    SectorSnapshot,
    MarketIndicatorSnapshot,
    FundamentalSnapshot,
    YieldSpreadRecord,
)

logger = logging.getLogger(__name__)


class StorageService:
    """Persists collector outputs to the database via upserts."""

    def __init__(self, db: Session):
        self.db = db

    def _mysql_upsert(self, model, rows: List[dict], index_elements: List[str]) -> int:
        """Generic MySQL upsert using INSERT ... ON DUPLICATE KEY UPDATE."""
        if not rows:
            return 0
        stmt = mysql_insert(model).values(rows)
        update_cols = {
            c.name: stmt.inserted[c.name]
            for c in model.__table__.columns
            if c.name not in index_elements and c.name not in ("id", "created_at")
        }
        stmt = stmt.on_duplicate_key_update(**update_cols)
        self.db.execute(stmt)
        self.db.commit()
        return len(rows)

    def store_fred_data(self, series_data: Dict[str, list]) -> int:
        """Store FRED MacroDataPoint objects."""
        rows = []
        for series_id, points in series_data.items():
            for p in points:
                rows.append({
                    "series_id": p.series_id,
                    "date": p.date,
                    "value": p.value,
                })
        return self._mysql_upsert(MacroData, rows, ["series_id", "date"])

    def store_yield_spread(self, spread) -> int:
        """Store a YieldSpread dataclass."""
        if spread is None:
            return 0
        rows = [{
            "date": spread.date,
            "dgs2": spread.dgs2,
            "dgs10": spread.dgs10,
            "spread": spread.spread,
        }]
        return self._mysql_upsert(YieldSpreadRecord, rows, ["date"])

    def store_northbound_flow(self, flows: list) -> int:
        """Store NorthboundFlowData objects."""
        rows = [{
            "trade_date": f.trade_date,
            "net_flow": f.net_flow,
            "hgt": f.hgt,
            "sgt": f.sgt,
            "south_money": f.south_money,
            "quota_remaining": f.quota_remaining,
        } for f in flows]
        return self._mysql_upsert(NorthboundFlow, rows, ["trade_date"])

    def store_cn_macro(self, data: Dict[str, list]) -> int:
        """Store CnMacroData objects grouped by category."""
        rows = []
        for category, points in data.items():
            for p in points:
                rows.append({
                    "indicator": p.indicator,
                    "date": p.date,
                    "value": p.value,
                    "yoy_change": p.yoy_change,
                })
        return self._mysql_upsert(CnMacroRecord, rows, ["indicator", "date"])

    def store_sectors(self, data: Dict[str, list]) -> int:
        """Store SectorData objects. data keys are 'industry'/'concept'."""
        today = date.today()
        rows = []
        for sector_type, sectors in data.items():
            for s in sectors:
                rows.append({
                    "snapshot_date": today,
                    "sector_type": sector_type,
                    "code": s.code,
                    "name": s.name,
                    "stock_count": s.stock_count,
                    "avg_price": s.avg_price,
                    "change_pct": s.change_pct,
                    "volume": s.volume,
                    "amount": s.amount,
                    "leading_stock": s.leading_stock,
                })
        return self._mysql_upsert(SectorSnapshot, rows, ["snapshot_date", "sector_type", "code"])

    def store_market_indicators(self, indicators: list) -> int:
        """Store MarketIndicator objects. Skips entries with no data."""
        rows = []
        for ind in indicators:
            if ind.value is None or ind.date is None:
                continue
            rows.append({
                "symbol": ind.symbol,
                "name": ind.name,
                "value": Decimal(str(ind.value)),
                "change_pct": Decimal(str(ind.change_pct)) if ind.change_pct is not None else None,
                "date": ind.date,
            })
        return self._mysql_upsert(MarketIndicatorSnapshot, rows, ["symbol", "date"])

    def store_fundamentals(self, fundamentals: list) -> int:
        """Store FundamentalData objects."""
        today = date.today()
        rows = []
        for f in fundamentals:
            if f is None:
                continue
            rows.append({
                "symbol": f.symbol,
                "market": f.market,
                "snapshot_date": today,
                "name": f.name,
                "market_cap": Decimal(str(f.market_cap)) if f.market_cap else None,
                "pe_ratio": Decimal(str(f.pe_ratio)) if f.pe_ratio else None,
                "pb_ratio": Decimal(str(f.pb_ratio)) if f.pb_ratio else None,
                "revenue": Decimal(str(f.revenue)) if f.revenue else None,
                "net_income": Decimal(str(f.net_income)) if f.net_income else None,
                "revenue_growth": Decimal(str(f.revenue_growth)) if f.revenue_growth else None,
                "profit_margin": Decimal(str(f.profit_margin)) if f.profit_margin else None,
                "analyst_rating": f.analyst_rating,
                "target_price": Decimal(str(f.target_price)) if f.target_price else None,
            })
        return self._mysql_upsert(FundamentalSnapshot, rows, ["symbol", "snapshot_date"])

    def store_sector_flows(self, data: Dict[str, list]) -> int:
        """Store SectorFlowData objects. data keys are 'industry'/'concept'."""
        today = date.today()
        rows = []
        for sector_type, flows in data.items():
            for f in flows:
                rows.append({
                    "snapshot_date": today,
                    "sector_type": sector_type,
                    "code": f.code,
                    "name": f.name,
                    "main_net_inflow": f.main_net_inflow,
                    "super_large_inflow": f.super_large_inflow,
                    "large_inflow": f.large_inflow,
                    "medium_inflow": f.medium_inflow,
                    "small_inflow": f.small_inflow,
                    "main_pct": f.main_pct,
                })
        return self._mysql_upsert(SectorFlowSnapshot, rows, ["snapshot_date", "sector_type", "code"])

    def store_market_breadth(self, breadth_data: list) -> int:
        """Store MarketBreadthData objects."""
        today = date.today()
        rows = []
        for b in breadth_data:
            rows.append({
                "snapshot_date": today,
                "index_code": b.index_code,
                "index_name": b.index_name,
                "close": Decimal(str(b.close)),
                "change_pct": Decimal(str(b.change_pct)),
                "advancing": b.advancing,
                "declining": b.declining,
                "unchanged": b.unchanged,
            })
        return self._mysql_upsert(MarketBreadthSnapshot, rows, ["snapshot_date", "index_code"])

    def store_tushare_data(self, data: dict) -> int:
        """Store TuShare fetch_all output (index valuations + fund NAVs)."""
        total = 0

        # Index valuations
        index_vals = data.get("index_valuations", [])
        if index_vals:
            rows = []
            for v in index_vals:
                rows.append({
                    "ts_code": v.ts_code,
                    "name": v.name,
                    "trade_date": v.trade_date,
                    "pe": Decimal(str(v.pe)) if v.pe else None,
                    "pb": Decimal(str(v.pb)) if v.pb else None,
                    "total_mv": v.total_mv,
                })
            total += self._mysql_upsert(IndexValuationSnapshot, rows, ["ts_code", "trade_date"])

        # Fund NAVs
        fund_navs = data.get("fund_navs", [])
        if fund_navs:
            rows = []
            for n in fund_navs:
                rows.append({
                    "ts_code": n.ts_code,
                    "nav_date": n.nav_date,
                    "unit_nav": Decimal(str(n.unit_nav)) if n.unit_nav else None,
                    "accum_nav": Decimal(str(n.accum_nav)) if n.accum_nav else None,
                    "adj_nav": Decimal(str(n.adj_nav)) if n.adj_nav else None,
                })
            total += self._mysql_upsert(FundNavSnapshot, rows, ["ts_code", "nav_date"])

        return total
