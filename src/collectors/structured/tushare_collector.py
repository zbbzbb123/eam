"""TuShare Pro collector for A-share financial metrics and valuation percentiles."""
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
import logging

import pandas as pd
import tushare as ts

from src.config import get_settings

logger = logging.getLogger(__name__)

# Default lookback period for percentile calculation (1 year)
DEFAULT_PERCENTILE_LOOKBACK_DAYS = 365


@dataclass
class StockValuationData:
    """Data class for stock valuation metrics."""

    ts_code: str
    trade_date: date
    pe: Optional[float] = None
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
    ps_ttm: Optional[float] = None
    total_mv: Optional[Decimal] = None  # Total market value
    circ_mv: Optional[Decimal] = None  # Circulating market value
    turnover_rate: Optional[float] = None
    turnover_rate_f: Optional[float] = None  # Free float turnover rate

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class StockFinancialsData:
    """Data class for stock financial indicators."""

    ts_code: str
    ann_date: date  # Announcement date
    end_date: date  # Report end date
    roe: Optional[float] = None  # Return on Equity
    roe_waa: Optional[float] = None  # ROE (weighted average)
    roa: Optional[float] = None  # Return on Assets
    roa2: Optional[float] = None  # ROA (alternative calculation)
    revenue_yoy: Optional[float] = None  # Revenue year-over-year growth
    netprofit_yoy: Optional[float] = None  # Net profit year-over-year growth
    grossprofit_margin: Optional[float] = None
    netprofit_margin: Optional[float] = None
    fcff: Optional[Decimal] = None  # Free cash flow to firm
    fcfe: Optional[Decimal] = None  # Free cash flow to equity

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


class TuShareCollector:
    """Collector for A-share financial metrics via TuShare Pro API."""

    def __init__(self):
        """Initialize the TuShare collector."""
        settings = get_settings()
        self._token = settings.tushare_token
        self._pro = None

        if not self._token:
            logger.warning(
                "TUSHARE_TOKEN is not configured. TuShare API requests will fail."
            )
        else:
            try:
                ts.set_token(self._token)
                self._pro = ts.pro_api()
            except Exception as e:
                logger.error(f"Failed to initialize TuShare Pro API: {e}")

    @property
    def name(self) -> str:
        """Return collector name."""
        return "tushare_collector"

    @property
    def source(self) -> str:
        """Return data source name."""
        return "tushare"

    def _parse_date(self, date_str: str) -> date:
        """Parse TuShare date string (YYYYMMDD) to date object."""
        return date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))

    def _format_date(self, d: date) -> str:
        """Format date to TuShare format (YYYYMMDD)."""
        return d.strftime("%Y%m%d")

    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float, returning None for NaN or invalid values."""
        if value is None:
            return None
        if pd.isna(value):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _safe_decimal(self, value) -> Optional[Decimal]:
        """Safely convert value to Decimal, returning None for NaN or invalid values."""
        if value is None:
            return None
        if pd.isna(value):
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None

    def fetch_daily_valuation(
        self,
        ts_code: str,
        start_date: date,
        end_date: date,
    ) -> List[StockValuationData]:
        """
        Fetch daily valuation metrics (PE, PB, PS, etc.) for a stock.

        Args:
            ts_code: TuShare stock code (e.g., "000001.SZ")
            start_date: Start date for the query
            end_date: End date for the query

        Returns:
            List of StockValuationData objects

        Note:
            Returns empty list on API error for graceful degradation.
        """
        if not self._pro:
            logger.warning("TuShare Pro API not initialized. Cannot fetch data.")
            return []

        try:
            df = self._pro.daily_basic(
                ts_code=ts_code,
                start_date=self._format_date(start_date),
                end_date=self._format_date(end_date),
            )

            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                valuation = StockValuationData(
                    ts_code=row["ts_code"],
                    trade_date=self._parse_date(row["trade_date"]),
                    pe=self._safe_float(row.get("pe")),
                    pe_ttm=self._safe_float(row.get("pe_ttm")),
                    pb=self._safe_float(row.get("pb")),
                    ps=self._safe_float(row.get("ps")),
                    ps_ttm=self._safe_float(row.get("ps_ttm")),
                    total_mv=self._safe_decimal(row.get("total_mv")),
                    circ_mv=self._safe_decimal(row.get("circ_mv")),
                    turnover_rate=self._safe_float(row.get("turnover_rate")),
                    turnover_rate_f=self._safe_float(row.get("turnover_rate_f")),
                )
                result.append(valuation)

            return result

        except Exception as e:
            logger.error(f"Error fetching daily valuation for {ts_code}: {e}")
            return []

    def fetch_financial_indicators(
        self,
        ts_code: str,
        period: Optional[str] = None,
    ) -> List[StockFinancialsData]:
        """
        Fetch financial indicators (ROE, ROA, growth rates, etc.) for a stock.

        Args:
            ts_code: TuShare stock code (e.g., "000001.SZ")
            period: Optional report period (e.g., "20241231")

        Returns:
            List of StockFinancialsData objects

        Note:
            Returns empty list on API error for graceful degradation.
        """
        if not self._pro:
            logger.warning("TuShare Pro API not initialized. Cannot fetch data.")
            return []

        try:
            params = {"ts_code": ts_code}
            if period:
                params["period"] = period

            df = self._pro.fina_indicator(**params)

            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                financials = StockFinancialsData(
                    ts_code=row["ts_code"],
                    ann_date=self._parse_date(row["ann_date"]),
                    end_date=self._parse_date(row["end_date"]),
                    roe=self._safe_float(row.get("roe")),
                    roe_waa=self._safe_float(row.get("roe_waa")),
                    roa=self._safe_float(row.get("roa")),
                    roa2=self._safe_float(row.get("roa2")),
                    revenue_yoy=self._safe_float(row.get("q_gsprofit_yoy")),
                    netprofit_yoy=self._safe_float(row.get("q_profit_yoy")),
                    grossprofit_margin=self._safe_float(row.get("grossprofit_margin")),
                    netprofit_margin=self._safe_float(row.get("netprofit_margin")),
                    fcff=self._safe_decimal(row.get("fcff")),
                    fcfe=self._safe_decimal(row.get("fcfe")),
                )
                result.append(financials)

            return result

        except Exception as e:
            logger.error(f"Error fetching financial indicators for {ts_code}: {e}")
            return []

    def calculate_percentile(
        self,
        ts_code: str,
        metric: str,
        current_value: float,
        lookback_days: int = DEFAULT_PERCENTILE_LOOKBACK_DAYS,
    ) -> Optional[float]:
        """
        Calculate the historical percentile for a given metric value.

        Args:
            ts_code: TuShare stock code (e.g., "000001.SZ")
            metric: The metric to calculate percentile for ("pe", "pb", etc.)
            current_value: The current value to find percentile for
            lookback_days: Number of days to look back for historical data

        Returns:
            Percentile (0-100) or None if calculation fails

        Note:
            Percentile indicates what percentage of historical values are
            below the current value. A percentile of 80 means the current
            value is higher than 80% of historical values.
        """
        if not self._pro:
            logger.warning("TuShare Pro API not initialized. Cannot calculate percentile.")
            return None

        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=lookback_days)

            df = self._pro.daily_basic(
                ts_code=ts_code,
                start_date=self._format_date(start_date),
                end_date=self._format_date(end_date),
            )

            if df is None or df.empty:
                logger.warning(f"No historical data available for {ts_code}")
                return None

            if metric not in df.columns:
                logger.warning(f"Metric '{metric}' not found in data for {ts_code}")
                return None

            # Get the metric values, dropping NaN
            values = df[metric].dropna()

            if len(values) == 0:
                logger.warning(f"No valid values for metric '{metric}' in {ts_code}")
                return None

            # Calculate percentile: percentage of values below current_value
            count_below = (values < current_value).sum()
            percentile = (count_below / len(values)) * 100

            return round(percentile, 2)

        except Exception as e:
            logger.error(f"Error calculating percentile for {ts_code}: {e}")
            return None

    def get_valuation_with_percentile(
        self,
        ts_code: str,
        lookback_days: int = DEFAULT_PERCENTILE_LOOKBACK_DAYS,
    ) -> Optional[Dict]:
        """
        Get current valuation data along with PE and PB percentiles.

        Args:
            ts_code: TuShare stock code (e.g., "000001.SZ")
            lookback_days: Number of days for percentile calculation

        Returns:
            Dictionary with valuation data and percentiles, or None if no data

        Example return value:
            {
                "valuation": StockValuationData(...),
                "pe_percentile": 45.5,
                "pb_percentile": 62.3
            }
        """
        if not self._pro:
            logger.warning("TuShare Pro API not initialized. Cannot fetch data.")
            return None

        try:
            # Get latest valuation
            today = date.today()
            df = self._pro.daily_basic(
                ts_code=ts_code,
                start_date=self._format_date(today - timedelta(days=10)),
                end_date=self._format_date(today),
            )

            if df is None or df.empty:
                logger.warning(f"No current valuation data for {ts_code}")
                return None

            # Get the most recent record
            latest_row = df.iloc[0]

            valuation = StockValuationData(
                ts_code=latest_row["ts_code"],
                trade_date=self._parse_date(latest_row["trade_date"]),
                pe=self._safe_float(latest_row.get("pe")),
                pe_ttm=self._safe_float(latest_row.get("pe_ttm")),
                pb=self._safe_float(latest_row.get("pb")),
                ps=self._safe_float(latest_row.get("ps")),
                ps_ttm=self._safe_float(latest_row.get("ps_ttm")),
                total_mv=self._safe_decimal(latest_row.get("total_mv")),
                circ_mv=self._safe_decimal(latest_row.get("circ_mv")),
                turnover_rate=self._safe_float(latest_row.get("turnover_rate")),
                turnover_rate_f=self._safe_float(latest_row.get("turnover_rate_f")),
            )

            # Calculate percentiles
            pe_percentile = None
            pb_percentile = None

            if valuation.pe is not None:
                pe_percentile = self.calculate_percentile(
                    ts_code=ts_code,
                    metric="pe",
                    current_value=valuation.pe,
                    lookback_days=lookback_days,
                )

            if valuation.pb is not None:
                pb_percentile = self.calculate_percentile(
                    ts_code=ts_code,
                    metric="pb",
                    current_value=valuation.pb,
                    lookback_days=lookback_days,
                )

            return {
                "valuation": valuation,
                "pe_percentile": pe_percentile,
                "pb_percentile": pb_percentile,
            }

        except Exception as e:
            logger.error(f"Error getting valuation with percentile for {ts_code}: {e}")
            return None
