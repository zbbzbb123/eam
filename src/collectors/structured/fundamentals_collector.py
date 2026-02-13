"""Fundamentals collector for company financial data (US/HK/CN stocks)."""
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple
import logging

import pandas as pd
import tushare as ts
import yfinance

from src.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class FundamentalData:
    """Data class for company fundamental data."""

    symbol: str
    market: str  # "US", "HK", or "CN"
    name: Optional[str] = None
    market_cap: Optional[float] = None  # 市值
    pe_ratio: Optional[float] = None  # PE
    pb_ratio: Optional[float] = None  # PB
    revenue: Optional[float] = None  # 营收 (latest annual)
    net_income: Optional[float] = None  # 净利润 (latest annual)
    revenue_growth: Optional[float] = None  # 营收增长率 YoY %
    profit_margin: Optional[float] = None  # 利润率 %
    analyst_rating: Optional[str] = None  # 分析师评级 (US only)
    target_price: Optional[float] = None  # 目标价 (US only)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


class FundamentalsCollector:
    """Collector for company fundamental data across US, HK, and CN markets."""

    def __init__(self):
        """Initialize the fundamentals collector."""
        settings = get_settings()
        self._tushare_token = settings.tushare_token
        self._pro = None

        if self._tushare_token:
            try:
                ts.set_token(self._tushare_token)
                self._pro = ts.pro_api()
            except Exception as e:
                logger.error(f"Failed to initialize TuShare Pro API: {e}")
        else:
            logger.warning(
                "TUSHARE_TOKEN is not configured. CN stock fundamentals will be unavailable."
            )

    @property
    def name(self) -> str:
        """Return collector name."""
        return "fundamentals_collector"

    @property
    def source(self) -> str:
        """Return data source name."""
        return "fundamentals"

    @staticmethod
    def _safe_float(value) -> Optional[float]:
        """Safely convert value to float, returning None for NaN or invalid values."""
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _convert_hk_symbol(symbol: str) -> str:
        """Convert HK symbol to yfinance format.

        Examples:
            "01810" -> "1810.HK"
            "00700" -> "0700.HK"
        """
        # Strip leading zeros but keep at least one digit, then append .HK
        numeric = symbol.lstrip("0") or "0"
        return f"{numeric}.HK"

    @staticmethod
    def _convert_cn_symbol(symbol: str) -> str:
        """Convert CN symbol to TuShare format.

        Prefix logic (same as Sina convention):
            5xx, 6xx -> .SH (Shanghai)
            others   -> .SZ (Shenzhen)
        """
        if symbol.startswith("5") or symbol.startswith("6"):
            return f"{symbol}.SH"
        return f"{symbol}.SZ"

    def _fetch_us_hk_fundamentals(self, symbol: str, market: str) -> Optional[FundamentalData]:
        """Fetch fundamentals for US or HK stock via yfinance.

        Args:
            symbol: Stock symbol (e.g., "AAPL" for US, "01810" for HK)
            market: "US" or "HK"

        Returns:
            FundamentalData or None on error.
        """
        try:
            if market == "HK":
                yf_symbol = self._convert_hk_symbol(symbol)
            else:
                yf_symbol = symbol

            ticker = yfinance.Ticker(yf_symbol)
            info = ticker.info

            if not info:
                logger.warning(f"No info returned for {yf_symbol}")
                return None

            data = FundamentalData(
                symbol=symbol,
                market=market,
                name=info.get("shortName") or info.get("longName"),
                market_cap=self._safe_float(info.get("marketCap")),
                pe_ratio=self._safe_float(info.get("trailingPE")),
                pb_ratio=self._safe_float(info.get("priceToBook")),
                revenue=self._safe_float(info.get("totalRevenue")),
                net_income=self._safe_float(info.get("netIncomeToCommon")),
                revenue_growth=self._safe_float(info.get("revenueGrowth")),
                profit_margin=self._safe_float(info.get("profitMargins")),
            )

            # Analyst data is typically only available for US stocks
            if market == "US":
                data.analyst_rating = info.get("recommendationKey")
                data.target_price = self._safe_float(info.get("targetMeanPrice"))

            return data

        except Exception as e:
            logger.error(f"Error fetching fundamentals for {symbol} ({market}): {e}")
            return None

    def _fetch_cn_fundamentals(self, symbol: str) -> Optional[FundamentalData]:
        """Fetch fundamentals for CN stock via TuShare.

        Args:
            symbol: Stock symbol (e.g., "512480", "159682", "600519")

        Returns:
            FundamentalData or None on error.
        """
        if not self._pro:
            logger.warning("TuShare Pro API not initialized. Cannot fetch CN fundamentals.")
            return None

        ts_code = self._convert_cn_symbol(symbol)

        try:
            # Fetch daily basic for PE, PB, market cap
            df_basic = self._pro.daily_basic(ts_code=ts_code, limit=1)

            if df_basic is None or df_basic.empty:
                logger.warning(f"No daily_basic data for {ts_code}")
                return None

            row = df_basic.iloc[0]

            data = FundamentalData(
                symbol=symbol,
                market="CN",
                name=None,  # daily_basic does not include name
                market_cap=self._safe_float(row.get("total_mv")),
                pe_ratio=self._safe_float(row.get("pe")),
                pb_ratio=self._safe_float(row.get("pb")),
            )

            # Fetch financial indicators for revenue growth, profit margin
            df_fina = self._pro.fina_indicator(ts_code=ts_code, limit=1)

            if df_fina is not None and not df_fina.empty:
                fina_row = df_fina.iloc[0]
                data.revenue_growth = self._safe_float(fina_row.get("q_gsprofit_yoy"))
                data.profit_margin = self._safe_float(fina_row.get("netprofit_margin"))

            return data

        except Exception as e:
            logger.error(f"Error fetching CN fundamentals for {ts_code}: {e}")
            return None

    def fetch_fundamentals(self, symbol: str, market: str) -> Optional[FundamentalData]:
        """Fetch fundamental data for a single stock.

        Args:
            symbol: Stock symbol (e.g., "AAPL", "01810", "600519")
            market: Market identifier ("US", "HK", or "CN")

        Returns:
            FundamentalData or None on error.
        """
        market = market.upper()

        if market in ("US", "HK"):
            return self._fetch_us_hk_fundamentals(symbol, market)
        elif market == "CN":
            return self._fetch_cn_fundamentals(symbol)
        else:
            logger.error(f"Unsupported market: {market}")
            return None

    def fetch_all_holdings_fundamentals(
        self,
        holdings: List[Tuple[str, str]],
    ) -> List[Optional[FundamentalData]]:
        """Fetch fundamental data for all holdings.

        Args:
            holdings: List of (symbol, market) tuples.
                      e.g., [("AAPL", "US"), ("01810", "HK"), ("600519", "CN")]

        Returns:
            List of FundamentalData (or None for failed fetches), in same order
            as the input holdings list.
        """
        results: List[Optional[FundamentalData]] = []
        for symbol, market in holdings:
            try:
                data = self.fetch_fundamentals(symbol, market)
                results.append(data)
            except Exception as e:
                logger.error(f"Unexpected error fetching fundamentals for {symbol}: {e}")
                results.append(None)
        return results
