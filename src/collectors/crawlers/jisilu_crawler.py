"""Jisilu ETF premium/discount crawler for Chinese ETF data."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
import logging
import time

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ETFPremiumData:
    """Data class for ETF premium/discount information.

    Attributes:
        fund_id: ETF fund code (e.g., "510050")
        fund_name: ETF name (e.g., "50ETF")
        price: Current trading price
        net_value: Latest net asset value (NAV)
        estimate_value: Estimated value based on index
        premium_rate: Premium/discount rate as percentage (positive = premium, negative = discount)
        volume: Trading volume
        turnover: Trading turnover amount
        nav_date: Date of the NAV
        index_id: Underlying index code
        index_name: Underlying index name
    """
    fund_id: str
    fund_name: str
    price: Decimal
    net_value: Decimal
    estimate_value: Optional[Decimal]
    premium_rate: Decimal
    volume: int
    turnover: Decimal
    nav_date: Optional[date]
    index_id: Optional[str]
    index_name: Optional[str]

    @property
    def is_premium(self) -> bool:
        """Check if this ETF is trading at a premium."""
        return self.premium_rate > Decimal("0")

    @property
    def is_discount(self) -> bool:
        """Check if this ETF is trading at a discount."""
        return self.premium_rate < Decimal("0")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "fund_id": self.fund_id,
            "fund_name": self.fund_name,
            "price": self.price,
            "net_value": self.net_value,
            "estimate_value": self.estimate_value,
            "premium_rate": self.premium_rate,
            "volume": self.volume,
            "turnover": self.turnover,
            "nav_date": self.nav_date,
            "index_id": self.index_id,
            "index_name": self.index_name,
        }


class JisiluCrawler:
    """Crawler for Jisilu.cn ETF premium/discount data.

    This crawler fetches ETF premium/discount data from Jisilu.cn which
    tracks Chinese ETF market data including premium/discount rates,
    trading volume, and fund net values.

    Attributes:
        BASE_URL: Base URL for Jisilu ETF API
        DEFAULT_TIMEOUT: Default request timeout in seconds
        USER_AGENT: User-Agent header for requests
    """

    BASE_URL = "https://www.jisilu.cn/data/etf/etf_list/"
    DEFAULT_TIMEOUT = 30.0
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )

    @property
    def name(self) -> str:
        """Return crawler name."""
        return "jisilu_crawler"

    @property
    def source(self) -> str:
        """Return data source name."""
        return "jisilu"

    def _build_url(self) -> str:
        """Build API URL with timestamp parameter.

        Returns:
            Constructed URL string with timestamp to bypass cache
        """
        timestamp = int(time.time())
        return f"{self.BASE_URL}?___jsl=LST___t={timestamp}&rp=1000&page=1"

    def _parse_percentage(self, text: str) -> Decimal:
        """Parse a percentage value from text, removing % sign.

        Args:
            text: Text containing the percentage (e.g., "5.88%", "-2.5%", "0.80")

        Returns:
            Parsed Decimal value (without % sign)
        """
        if not text:
            return Decimal("0")

        # Remove % sign and whitespace
        cleaned = text.strip().replace("%", "")
        if not cleaned:
            return Decimal("0")

        try:
            return Decimal(cleaned)
        except Exception:
            return Decimal("0")

    def _parse_decimal(self, text: str) -> Decimal:
        """Parse a decimal value from text.

        Args:
            text: Text containing the decimal

        Returns:
            Parsed Decimal value
        """
        if not text:
            return Decimal("0")

        cleaned = text.strip()
        if not cleaned:
            return Decimal("0")

        try:
            return Decimal(cleaned)
        except Exception:
            return Decimal("0")

    def _parse_int(self, text: str) -> int:
        """Parse an integer value from text.

        Args:
            text: Text containing the integer

        Returns:
            Parsed integer value
        """
        if not text:
            return 0

        cleaned = text.strip()
        if not cleaned:
            return 0

        try:
            return int(float(cleaned))
        except Exception:
            return 0

    def _parse_date(self, text: str) -> Optional[date]:
        """Parse date from text.

        Args:
            text: Text containing date (e.g., "2026-01-25")

        Returns:
            Parsed date or None if invalid
        """
        if not text:
            return None

        try:
            return datetime.strptime(text.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None

    def _parse_row(self, row: dict) -> Optional[ETFPremiumData]:
        """Parse a single row from the API response.

        Args:
            row: Dictionary containing row data from API

        Returns:
            ETFPremiumData object or None if parsing fails
        """
        try:
            cell = row.get("cell", {})

            fund_id = cell.get("fund_id", "")
            fund_name = cell.get("fund_nm", "")

            if not fund_id or not fund_name:
                return None

            price = self._parse_decimal(cell.get("price", "0"))
            net_value = self._parse_decimal(cell.get("fund_nav", "0"))
            estimate_value_str = cell.get("estimate_value")
            estimate_value = self._parse_decimal(estimate_value_str) if estimate_value_str else None
            premium_rate = self._parse_percentage(cell.get("discount_rt", "0"))
            volume = self._parse_int(cell.get("volume", "0"))
            turnover = self._parse_decimal(cell.get("amount", "0"))
            nav_date = self._parse_date(cell.get("nav_dt"))
            index_id = cell.get("index_id")
            index_name = cell.get("index_nm")

            # Validate essential fields
            if price == Decimal("0") and net_value == Decimal("0"):
                return None

            return ETFPremiumData(
                fund_id=fund_id,
                fund_name=fund_name,
                price=price,
                net_value=net_value,
                estimate_value=estimate_value,
                premium_rate=premium_rate,
                volume=volume,
                turnover=turnover,
                nav_date=nav_date,
                index_id=index_id,
                index_name=index_name,
            )
        except Exception as e:
            logger.debug(f"Error parsing row: {e}")
            return None

    def _fetch_json(self, url: str) -> Optional[dict]:
        """Fetch JSON content from URL.

        Args:
            url: URL to fetch

        Returns:
            JSON response as dict or None on error
        """
        try:
            response = httpx.get(
                url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=self.DEFAULT_TIMEOUT,
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def fetch_etf_premium_data(self) -> List[ETFPremiumData]:
        """Fetch ETF premium/discount data from Jisilu.

        Returns:
            List of ETFPremiumData objects
        """
        try:
            url = self._build_url()
            data = self._fetch_json(url)

            if not data:
                return []

            rows = data.get("rows", [])
            result = []

            for row in rows:
                parsed = self._parse_row(row)
                if parsed:
                    result.append(parsed)

            return result
        except Exception as e:
            logger.error(f"Error fetching ETF premium data: {e}")
            return []

    def filter_high_premium(
        self,
        threshold: Decimal = Decimal("5.0"),
    ) -> List[ETFPremiumData]:
        """Filter ETFs with premium rate above threshold.

        Args:
            threshold: Minimum premium rate percentage (default 5.0%)

        Returns:
            List of ETFPremiumData with premium rate > threshold
        """
        try:
            all_data = self.fetch_etf_premium_data()
            return [item for item in all_data if item.premium_rate > threshold]
        except Exception as e:
            logger.error(f"Error filtering high premium ETFs: {e}")
            return []

    def filter_high_discount(
        self,
        threshold: Decimal = Decimal("-5.0"),
    ) -> List[ETFPremiumData]:
        """Filter ETFs with discount rate below threshold.

        Args:
            threshold: Maximum discount rate percentage (default -5.0%)

        Returns:
            List of ETFPremiumData with premium rate < threshold
        """
        try:
            all_data = self.fetch_etf_premium_data()
            return [item for item in all_data if item.premium_rate < threshold]
        except Exception as e:
            logger.error(f"Error filtering high discount ETFs: {e}")
            return []
