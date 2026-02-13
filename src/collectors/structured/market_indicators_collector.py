"""Market indicators collector for VIX, precious metals, and industrial metals."""
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import date
import logging

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class MarketIndicator:
    """Market indicator data point."""

    symbol: str
    name: str
    value: Optional[float]
    change_pct: Optional[float]
    date: Optional[date]


# Tracked market indicators
TRACKED_INDICATORS: Dict[str, str] = {
    "^VIX": "VIX恐慌指数",
    "SI=F": "白银期货",
    "HG=F": "铜期货",
    "GC=F": "黄金期货",
    "CL=F": "原油期货",
    "CNY=X": "美元/人民币",
}


class MarketIndicatorsCollector:
    """Collector for market indicators via Yahoo Finance.

    Fetches VIX, silver, copper, and gold futures data
    to provide a snapshot of market sentiment and commodity prices.
    """

    def __init__(self, indicators: Optional[Dict[str, str]] = None):
        """Initialize with optional custom indicator mapping.

        Args:
            indicators: Dictionary mapping symbol to display name.
                        Defaults to TRACKED_INDICATORS.
        """
        self.indicators = indicators or TRACKED_INDICATORS

    def fetch_indicator(self, symbol: str) -> MarketIndicator:
        """Fetch a single market indicator.

        Args:
            symbol: Yahoo Finance symbol (e.g., "^VIX", "SI=F")

        Returns:
            MarketIndicator with current value and daily change percentage.
            On error, returns indicator with None value/change_pct.
        """
        name = self.indicators.get(symbol, symbol)
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="5d")

            if df.empty:
                logger.warning(f"No data found for {symbol}")
                return MarketIndicator(
                    symbol=symbol, name=name, value=None, change_pct=None, date=None
                )

            latest = df.iloc[-1]
            latest_close = (
                round(float(latest["Close"]), 4) if pd.notna(latest["Close"]) else None
            )
            latest_date = df.index[-1].date()

            # Calculate change_pct from previous close
            change_pct = None
            if len(df) >= 2 and latest_close is not None:
                prev_close = df.iloc[-2]["Close"]
                if pd.notna(prev_close) and prev_close != 0:
                    change_pct = round(
                        (latest_close - float(prev_close)) / float(prev_close) * 100, 4
                    )

            return MarketIndicator(
                symbol=symbol,
                name=name,
                value=latest_close,
                change_pct=change_pct,
                date=latest_date,
            )

        except Exception as e:
            logger.error(f"Error fetching indicator {symbol}: {e}")
            return MarketIndicator(
                symbol=symbol, name=name, value=None, change_pct=None, date=None
            )

    def fetch_all(self) -> List[MarketIndicator]:
        """Fetch all tracked market indicators.

        Returns:
            List of MarketIndicator objects for every tracked symbol.
        """
        results = []
        for symbol in self.indicators:
            indicator = self.fetch_indicator(symbol)
            results.append(indicator)
        return results
