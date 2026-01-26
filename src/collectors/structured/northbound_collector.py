"""Northbound capital flow collector for A-shares via AkShare."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional
import logging

import pandas as pd
import akshare as ak

logger = logging.getLogger(__name__)


@dataclass
class NorthboundFlowData:
    """Data class for daily northbound capital flow."""

    trade_date: date
    net_flow: Decimal  # 每日北向资金净流入 (亿元)
    quota_remaining: Decimal  # 当日余额 (亿元)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "trade_date": self.trade_date,
            "net_flow": self.net_flow,
            "quota_remaining": self.quota_remaining,
        }


@dataclass
class HoldingChangeData:
    """Data class for individual stock holding changes by northbound capital."""

    symbol: str  # 股票代码
    name: str  # 股票名称
    holding: Decimal  # 今日持股 (万股)
    market_value: Decimal  # 今日参考市值 (亿元)
    holding_change: Decimal  # 今日持股变化 (万股)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "name": self.name,
            "holding": self.holding,
            "market_value": self.market_value,
            "holding_change": self.holding_change,
        }


class NorthboundCollector:
    """Collector for A-share northbound capital flow (北向资金) via AkShare.

    This collector fetches:
    - Daily northbound net flow (每日北向资金净流入)
    - Top stocks by northbound holding change (持股变化前N)
    """

    @property
    def name(self) -> str:
        """Return collector name."""
        return "northbound_collector"

    @property
    def source(self) -> str:
        """Return data source name."""
        return "akshare"

    def fetch_daily_net_flow(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[NorthboundFlowData]:
        """
        Fetch daily northbound net flow data.

        Args:
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering

        Returns:
            List of NorthboundFlowData objects

        Note:
            Uses akshare.stock_hsgt_hist_em() API.
            Returns empty list on error for graceful degradation.
        """
        try:
            df = ak.stock_hsgt_hist_em(symbol="北向资金")

            if df.empty:
                logger.info("No northbound flow data available")
                return []

            # Parse and convert data
            result = []
            for _, row in df.iterrows():
                trade_date = row["日期"]
                if hasattr(trade_date, "date"):
                    trade_date = trade_date.date()
                elif isinstance(trade_date, str):
                    trade_date = date.fromisoformat(trade_date)

                # Apply date filter if specified
                if start_date and trade_date < start_date:
                    continue
                if end_date and trade_date > end_date:
                    continue

                # Use column names from actual API response
                net_flow = row.get("当日成交净买额", row.get("当日净流入-Loss", 0))
                quota_remaining = row.get("当日余额", row.get("当日余额-Loss", 0))

                data = NorthboundFlowData(
                    trade_date=trade_date,
                    net_flow=Decimal(str(net_flow)) if pd.notna(net_flow) else Decimal("0"),
                    quota_remaining=Decimal(str(quota_remaining)) if pd.notna(quota_remaining) else Decimal("0"),
                )
                result.append(data)

            return result

        except Exception as e:
            logger.error(f"Error fetching northbound flow data: {e}")
            return []

    def fetch_top_holding_changes(
        self,
        market: str = "北向",
        top_n: int = 10,
    ) -> List[HoldingChangeData]:
        """
        Fetch top stocks by northbound holding change.

        Args:
            market: Market to query - "北向", "沪股通", or "深股通"
            top_n: Number of top stocks to return (default 10)

        Returns:
            List of HoldingChangeData objects sorted by absolute change (descending)

        Note:
            Uses akshare.stock_hsgt_hold_stock_em() API.
            Returns empty list on error for graceful degradation.
        """
        try:
            df = ak.stock_hsgt_hold_stock_em(market=market)

            if df.empty:
                logger.info(f"No holding data available for market: {market}")
                return []

            # Parse and convert data
            result = []
            for _, row in df.iterrows():
                symbol = str(row.get("代码", ""))
                name = str(row.get("名称", ""))

                holding = row.get("今日持股-Loss", row.get("今日持股", 0))
                market_value = row.get("今日参考市值-Loss", row.get("今日参考市值", 0))
                holding_change = row.get("今日持股变化-Loss", row.get("今日持股变化", 0))

                data = HoldingChangeData(
                    symbol=symbol,
                    name=name,
                    holding=Decimal(str(holding)) if pd.notna(holding) else Decimal("0"),
                    market_value=Decimal(str(market_value)) if pd.notna(market_value) else Decimal("0"),
                    holding_change=Decimal(str(holding_change)) if pd.notna(holding_change) else Decimal("0"),
                )
                result.append(data)

            # Sort by absolute holding change (descending) and return top N
            result.sort(key=lambda x: abs(x.holding_change), reverse=True)
            return result[:top_n]

        except Exception as e:
            logger.error(f"Error fetching holding changes for {market}: {e}")
            return []

    def get_latest_flow(self) -> Optional[NorthboundFlowData]:
        """
        Get the most recent northbound flow data point.

        Returns:
            NorthboundFlowData or None if not available

        Note:
            Convenience method that returns the most recent data point.
            Returns None on error for graceful degradation.
        """
        try:
            data = self.fetch_daily_net_flow()
            if not data:
                return None
            # Return the most recent data point (last in list after sorting by date)
            return max(data, key=lambda x: x.trade_date)
        except Exception as e:
            logger.error(f"Error getting latest flow: {e}")
            return None
