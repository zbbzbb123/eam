"""Northbound capital flow collector for A-shares via TuShare (moneyflow_hsgt)."""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional
import logging

import tushare as ts

from src.config import get_settings

logger = logging.getLogger(__name__)

# Conversion factor: TuShare returns values in 百万元, we store in 亿元
_TO_YI = Decimal("100")


@dataclass
class NorthboundFlowData:
    """Data class for daily northbound capital trading volume.

    Note: TuShare moneyflow_hsgt returns daily TRADING VOLUME (成交额),
    not net buy amounts (净买入). The field 'net_flow' stores north_money
    (total northbound trading volume). Day-over-day changes in volume
    indicate activity level changes.
    """

    trade_date: date
    net_flow: Decimal  # 北向交易额 (亿元) = north_money from TuShare
    hgt: Optional[Decimal] = None  # 沪股通交易额 (亿元)
    sgt: Optional[Decimal] = None  # 深股通交易额 (亿元)
    south_money: Optional[Decimal] = None  # 南向交易额 (亿元)
    quota_remaining: Optional[Decimal] = None  # Unused, kept for compatibility

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "trade_date": self.trade_date,
            "net_flow": self.net_flow,
            "hgt": self.hgt,
            "sgt": self.sgt,
            "south_money": self.south_money,
            "quota_remaining": self.quota_remaining,
        }


class NorthboundCollector:
    """Collector for A-share northbound capital flow (北向资金) via TuShare API.

    Uses moneyflow_hsgt to fetch daily northbound/southbound net buy amounts,
    with breakdown by channel (沪股通 / 深股通).
    """

    def __init__(self):
        settings = get_settings()
        self._token = settings.tushare_token
        self._pro = None

        if not self._token:
            logger.warning("TUSHARE_TOKEN is not configured. Northbound collector will fail.")
        else:
            try:
                ts.set_token(self._token)
                self._pro = ts.pro_api()
            except Exception as e:
                logger.error(f"Failed to initialize TuShare Pro API: {e}")

    @property
    def name(self) -> str:
        return "northbound_collector"

    @property
    def source(self) -> str:
        return "tushare"

    def _parse_date(self, date_str: str) -> date:
        """Parse TuShare date string (YYYYMMDD) to date object."""
        return date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))

    def _format_date(self, d: date) -> str:
        """Format date to TuShare format (YYYYMMDD)."""
        return d.strftime("%Y%m%d")

    def _safe_decimal(self, value) -> Optional[Decimal]:
        """Safely convert to Decimal, returning None for NaN/None."""
        if value is None:
            return None
        try:
            import math
            if math.isnan(float(value)):
                return None
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None

    def fetch_daily_net_flow(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 30,
    ) -> List[NorthboundFlowData]:
        """Fetch daily northbound net flow data from TuShare moneyflow_hsgt.

        TuShare returns values in 百万元 (million yuan). We convert to 亿元.
        Fields: trade_date, hgt, sgt, north_money, ggt_ss, ggt_sz, south_money.

        Args:
            start_date: Optional start date for filtering.
            end_date: Optional end date for filtering.
            limit: Number of recent trading days to fetch (default 30).

        Returns:
            List of NorthboundFlowData objects.
        """
        if not self._pro:
            logger.error("TuShare API not initialized")
            return []

        try:
            if not end_date:
                end_date = date.today()
            if not start_date:
                start_date = end_date - timedelta(days=limit + 15)  # Extra buffer for non-trading days

            df = self._pro.moneyflow_hsgt(
                start_date=self._format_date(start_date),
                end_date=self._format_date(end_date),
            )

            if df is None or df.empty:
                logger.info("No northbound flow data from TuShare")
                return []

            result = []
            for _, row in df.iterrows():
                trade_date = self._parse_date(str(row["trade_date"]))

                # Convert from 百万元 to 亿元 (divide by 100)
                north = self._safe_decimal(row.get("north_money"))
                hgt_val = self._safe_decimal(row.get("hgt"))
                sgt_val = self._safe_decimal(row.get("sgt"))
                south = self._safe_decimal(row.get("south_money"))

                net_flow = north / _TO_YI if north is not None else Decimal("0")
                hgt_yi = hgt_val / _TO_YI if hgt_val is not None else None
                sgt_yi = sgt_val / _TO_YI if sgt_val is not None else None
                south_yi = south / _TO_YI if south is not None else None

                flow = NorthboundFlowData(
                    trade_date=trade_date,
                    net_flow=net_flow,
                    hgt=hgt_yi,
                    sgt=sgt_yi,
                    south_money=south_yi,
                )
                result.append(flow)

            # Sort by date ascending
            result.sort(key=lambda x: x.trade_date)

            # Trim to limit
            if len(result) > limit:
                result = result[-limit:]

            return result

        except Exception as e:
            logger.error(f"Error fetching northbound flow data: {e}")
            return []

    def get_latest_flow(self) -> Optional[NorthboundFlowData]:
        """Get the most recent northbound flow data point."""
        try:
            data = self.fetch_daily_net_flow(limit=5)
            if not data:
                return None
            return max(data, key=lambda x: x.trade_date)
        except Exception as e:
            logger.error(f"Error getting latest flow: {e}")
            return None
