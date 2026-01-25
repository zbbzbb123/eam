"""Yahoo Finance collector for US stocks."""
from typing import Dict, List, Optional
from datetime import date, timedelta
import logging

import pandas as pd
import yfinance as yf

from src.collectors.base import BaseCollector, QuoteData

logger = logging.getLogger(__name__)


class YFinanceCollector(BaseCollector):
    """Collector for US stock data via Yahoo Finance."""

    def fetch_quotes(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[QuoteData]:
        """
        Fetch historical quotes for a US stock.

        Args:
            symbol: Stock symbol (e.g., "NVDA", "VOO")
            start_date: Start date for historical data
            end_date: End date for historical data

        Returns:
            List of QuoteData objects

        Raises:
            Exception: Propagates any API errors to caller for batch operations.
                This allows callers to handle errors appropriately when fetching
                quotes for multiple symbols.
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date + timedelta(days=1))

            if df.empty:
                logger.warning(f"No data found for {symbol}")
                return []

            quotes = []
            for idx, row in df.iterrows():
                quote = QuoteData(
                    symbol=symbol.upper(),
                    trade_date=idx.date(),
                    open=round(row["Open"], 4) if pd.notna(row["Open"]) else None,
                    high=round(row["High"], 4) if pd.notna(row["High"]) else None,
                    low=round(row["Low"], 4) if pd.notna(row["Low"]) else None,
                    close=round(row["Close"], 4) if pd.notna(row["Close"]) else None,
                    volume=int(row["Volume"]) if pd.notna(row["Volume"]) else None,
                )
                quotes.append(quote)

            return quotes

        except Exception as e:
            logger.error(f"Error fetching quotes for {symbol}: {e}")
            raise

    def fetch_latest_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        Fetch the latest quote for a US stock.

        Args:
            symbol: Stock symbol

        Returns:
            QuoteData or None if not available

        Note:
            Unlike fetch_quotes(), this method swallows exceptions and returns
            None on API errors. This is intentional for single-symbol lookups
            where graceful degradation is preferred over error propagation.
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="1d")

            if df.empty:
                return None

            row = df.iloc[-1]
            return QuoteData(
                symbol=symbol.upper(),
                trade_date=df.index[-1].date(),
                open=round(row["Open"], 4) if pd.notna(row["Open"]) else None,
                high=round(row["High"], 4) if pd.notna(row["High"]) else None,
                low=round(row["Low"], 4) if pd.notna(row["Low"]) else None,
                close=round(row["Close"], 4) if pd.notna(row["Close"]) else None,
                volume=int(row["Volume"]) if pd.notna(row["Volume"]) else None,
            )

        except Exception as e:
            logger.error(f"Error fetching latest quote for {symbol}: {e}")
            return None

    def fetch_multiple_quotes(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date,
    ) -> Dict[str, List[QuoteData]]:
        """
        Fetch historical quotes for multiple symbols.

        Args:
            symbols: List of stock symbols
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary mapping symbol to list of quotes
        """
        result = {}
        for symbol in symbols:
            try:
                quotes = self.fetch_quotes(symbol, start_date, end_date)
                result[symbol] = quotes
            except Exception as e:
                logger.error(f"Error fetching {symbol}: {e}")
                result[symbol] = []
        return result
