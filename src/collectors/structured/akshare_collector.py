"""AkShare collector for A-share and HK stocks."""
from typing import Dict, List, Optional
from datetime import date
import logging

import pandas as pd
import akshare as ak

from src.collectors.base import BaseCollector, QuoteData

logger = logging.getLogger(__name__)


class AkShareCollector(BaseCollector):
    """Collector for A-share and HK stock data via AkShare."""

    def fetch_quotes(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        market: str = "CN",
    ) -> List[QuoteData]:
        """
        Fetch historical quotes for A-share or HK stock.

        Args:
            symbol: Stock symbol (e.g., "000001" for A-share, "00700" for HK)
            start_date: Start date
            end_date: End date
            market: "CN" for A-share, "HK" for Hong Kong

        Returns:
            List of QuoteData objects

        Raises:
            ValueError: If market is not "CN" or "HK"
            Exception: Propagates any API errors to caller
        """
        try:
            if market == "CN":
                return self._fetch_cn_quotes(symbol, start_date, end_date)
            elif market == "HK":
                return self._fetch_hk_quotes(symbol, start_date, end_date)
            else:
                raise ValueError(f"Unsupported market: {market}")

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error fetching quotes for {symbol}: {e}")
            raise

    def _fetch_cn_quotes(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[QuoteData]:
        """Fetch A-share quotes."""
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust="qfq",  # 前复权
        )

        if df.empty:
            return []

        quotes = []
        for _, row in df.iterrows():
            trade_date = row["日期"]
            if hasattr(trade_date, "date"):
                trade_date = trade_date.date()
            elif isinstance(trade_date, str):
                trade_date = date.fromisoformat(trade_date)

            quote = QuoteData(
                symbol=symbol,
                trade_date=trade_date,
                open=round(float(row["开盘"]), 4) if pd.notna(row["开盘"]) else None,
                high=round(float(row["最高"]), 4) if pd.notna(row["最高"]) else None,
                low=round(float(row["最低"]), 4) if pd.notna(row["最低"]) else None,
                close=round(float(row["收盘"]), 4) if pd.notna(row["收盘"]) else None,
                volume=int(row["成交量"]) if pd.notna(row["成交量"]) else None,
            )
            quotes.append(quote)

        return quotes

    def _fetch_hk_quotes(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[QuoteData]:
        """Fetch HK stock quotes."""
        df = ak.stock_hk_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust="qfq",
        )

        if df.empty:
            return []

        quotes = []
        for _, row in df.iterrows():
            trade_date = row["日期"]
            if hasattr(trade_date, "date"):
                trade_date = trade_date.date()
            elif isinstance(trade_date, str):
                trade_date = date.fromisoformat(trade_date)

            quote = QuoteData(
                symbol=symbol,
                trade_date=trade_date,
                open=round(float(row["开盘"]), 4) if pd.notna(row["开盘"]) else None,
                high=round(float(row["最高"]), 4) if pd.notna(row["最高"]) else None,
                low=round(float(row["最低"]), 4) if pd.notna(row["最低"]) else None,
                close=round(float(row["收盘"]), 4) if pd.notna(row["收盘"]) else None,
                volume=int(row["成交量"]) if pd.notna(row["成交量"]) else None,
            )
            quotes.append(quote)

        return quotes

    def fetch_latest_quote(self, symbol: str, market: str = "CN") -> Optional[QuoteData]:
        """
        Fetch the latest quote.

        Args:
            symbol: Stock symbol
            market: "CN" or "HK"

        Returns:
            QuoteData or None

        Note:
            Unlike fetch_quotes(), this method returns None on API errors
            for graceful degradation in single-symbol lookups.
        """
        try:
            today = date.today()
            quotes = self.fetch_quotes(symbol, today, today, market)
            return quotes[-1] if quotes else None
        except Exception as e:
            logger.error(f"Error fetching latest quote for {symbol}: {e}")
            return None

    def fetch_northbound_flow(self, trade_date: date) -> dict:
        """
        Fetch northbound capital flow data.

        Args:
            trade_date: The trading date

        Returns:
            Dictionary with northbound flow data
        """
        try:
            df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
            if df.empty:
                return {}

            return {
                "date": trade_date,
                "data": df.to_dict("records")[:10],
            }
        except Exception as e:
            logger.error(f"Error fetching northbound flow: {e}")
            return {}
