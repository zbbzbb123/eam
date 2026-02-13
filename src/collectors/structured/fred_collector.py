"""FRED (Federal Reserve Economic Data) collector for US macro data."""
import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
import logging

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

# FRED API base URL
FRED_API_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# HTTP client timeout in seconds
HTTP_CLIENT_TIMEOUT = httpx.Timeout(30.0)

# Number of days to look back when fetching latest value
LATEST_VALUE_LOOKBACK_DAYS = 30

# Maximum number of observations to fetch for latest value
FETCH_LATEST_LIMIT = 10

# Configured macro data series
CONFIGURED_SERIES = {
    "DFII10": "10-Year Treasury Inflation-Indexed Security, Constant Maturity",
    "CPIAUCSL": "Consumer Price Index for All Urban Consumers: All Items",
    "GDP": "Gross Domestic Product",
    "UNRATE": "Unemployment Rate",
    "FEDFUNDS": "Federal Funds Effective Rate",
    "DGS2": "2-Year Treasury Constant Maturity Rate",
    "DGS10": "10-Year Treasury Constant Maturity Rate",
}


@dataclass
class MacroDataPoint:
    """Data class for a single macro data observation."""

    series_id: str
    date: date
    value: Decimal

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "series_id": self.series_id,
            "date": self.date,
            "value": self.value,
        }


@dataclass
class YieldSpread:
    """Data class for the 10Y-2Y Treasury yield spread.

    A negative spread indicates an inverted yield curve, which is
    historically a recession signal.
    """

    date: date
    dgs2: Decimal
    dgs10: Decimal
    spread: Decimal

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "date": self.date,
            "dgs2": self.dgs2,
            "dgs10": self.dgs10,
            "spread": self.spread,
        }


class FREDCollector:
    """Collector for US macro economic data from FRED API."""

    def __init__(self):
        """Initialize the FRED collector."""
        settings = get_settings()
        self._api_key = settings.fred_api_key
        self._configured_series = list(CONFIGURED_SERIES.keys())

        if not self._api_key:
            logger.warning("FRED_API_KEY is not configured. API requests will fail.")

    @property
    def name(self) -> str:
        """Return collector name."""
        return "fred_collector"

    @property
    def source(self) -> str:
        """Return data source name."""
        return "fred"

    @property
    def configured_series(self) -> List[str]:
        """Return list of configured series IDs."""
        return self._configured_series

    async def fetch_series(
        self,
        series_id: str,
        start_date: date,
        end_date: date,
    ) -> List[MacroDataPoint]:
        """
        Fetch observations for a single FRED series.

        Args:
            series_id: FRED series ID (e.g., "DFII10", "CPIAUCSL")
            start_date: Start date for observations
            end_date: End date for observations

        Returns:
            List of MacroDataPoint objects

        Note:
            This method handles API errors gracefully and returns an empty
            list on error. This allows batch operations to continue processing
            other series when one fails.
        """
        try:
            params = {
                "series_id": series_id,
                "api_key": self._api_key,
                "file_type": "json",
                "observation_start": start_date.isoformat(),
                "observation_end": end_date.isoformat(),
            }

            async with httpx.AsyncClient(timeout=HTTP_CLIENT_TIMEOUT) as client:
                response = await client.get(FRED_API_BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

            observations = data.get("observations", [])
            data_points = []

            for obs in observations:
                value_str = obs.get("value", "")
                # FRED uses "." to indicate missing data
                if value_str == "." or not value_str:
                    continue

                try:
                    data_point = MacroDataPoint(
                        series_id=series_id,
                        date=date.fromisoformat(obs["date"]),
                        value=Decimal(value_str),
                    )
                    data_points.append(data_point)
                except (ValueError, KeyError) as e:
                    logger.warning(f"Skipping invalid observation for {series_id}: {e}")
                    continue

            return data_points

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching FRED series {series_id}: {e}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Network error fetching FRED series {series_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching FRED series {series_id}: {e}")
            return []

    async def fetch_all_series(
        self,
        start_date: date,
        end_date: date,
        series_ids: Optional[List[str]] = None,
    ) -> Dict[str, List[MacroDataPoint]]:
        """
        Fetch observations for multiple FRED series.

        Args:
            start_date: Start date for observations
            end_date: End date for observations
            series_ids: Optional list of series IDs. If None, fetches all
                       configured series.

        Returns:
            Dictionary mapping series ID to list of MacroDataPoint objects
        """
        if series_ids is None:
            series_ids = self._configured_series

        # Fetch all series concurrently
        tasks = [
            self.fetch_series(series_id, start_date, end_date)
            for series_id in series_ids
        ]
        results = await asyncio.gather(*tasks)

        return dict(zip(series_ids, results))

    async def fetch_latest_value(
        self,
        series_id: str,
    ) -> Optional[MacroDataPoint]:
        """
        Fetch the most recent observation for a FRED series.

        Args:
            series_id: FRED series ID

        Returns:
            MacroDataPoint or None if not available

        Note:
            This method fetches the last 30 days of data and returns the
            most recent valid observation. This accounts for series that
            may have different update frequencies.
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=LATEST_VALUE_LOOKBACK_DAYS)

        try:
            params = {
                "series_id": series_id,
                "api_key": self._api_key,
                "file_type": "json",
                "observation_start": start_date.isoformat(),
                "observation_end": end_date.isoformat(),
                "sort_order": "desc",
                "limit": FETCH_LATEST_LIMIT,
            }

            async with httpx.AsyncClient(timeout=HTTP_CLIENT_TIMEOUT) as client:
                response = await client.get(FRED_API_BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

            observations = data.get("observations", [])

            for obs in observations:
                value_str = obs.get("value", "")
                if value_str == "." or not value_str:
                    continue

                try:
                    return MacroDataPoint(
                        series_id=series_id,
                        date=date.fromisoformat(obs["date"]),
                        value=Decimal(value_str),
                    )
                except (ValueError, KeyError):
                    continue

            return None

        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error(f"Error fetching latest value for {series_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching latest value for {series_id}: {e}")
            return None

    async def fetch_yield_spread(self) -> Optional[YieldSpread]:
        """
        Fetch the latest 10Y-2Y Treasury yield spread.

        Fetches the most recent DGS10 and DGS2 values and calculates
        the spread (DGS10 - DGS2). A negative spread indicates an
        inverted yield curve, which is historically a recession signal.

        Returns:
            YieldSpread object or None if data is unavailable.
        """
        dgs10_point, dgs2_point = await asyncio.gather(
            self.fetch_latest_value("DGS10"),
            self.fetch_latest_value("DGS2"),
        )

        if dgs10_point is None or dgs2_point is None:
            logger.warning(
                "Unable to calculate yield spread: missing data "
                f"(DGS10={'available' if dgs10_point else 'missing'}, "
                f"DGS2={'available' if dgs2_point else 'missing'})"
            )
            return None

        spread = dgs10_point.value - dgs2_point.value
        # Use the earlier of the two dates to be conservative
        spread_date = min(dgs10_point.date, dgs2_point.date)

        return YieldSpread(
            date=spread_date,
            dgs2=dgs2_point.value,
            dgs10=dgs10_point.value,
            spread=spread,
        )
