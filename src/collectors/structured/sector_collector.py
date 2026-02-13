"""Chinese A-share sector/industry data collector using Sina Finance API."""
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional
import logging

import httpx

logger = logging.getLogger(__name__)

# Sina sector API endpoints
SINA_INDUSTRY_URL = "https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php"
SINA_CONCEPT_URL = "https://vip.stock.finance.sina.com.cn/q/view/newFLJK.php"

# Required headers for Sina API
SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
}

# HTTP client timeout in seconds
HTTP_CLIENT_TIMEOUT = httpx.Timeout(30.0)

# Regex to extract the JS object from the response
# Matches: var S_Finance_bankuai_sinaindustry = {...}
JS_VAR_PATTERN = re.compile(r"var\s+\w+\s*=\s*(\{.*\})", re.DOTALL)


@dataclass
class SectorData:
    """Data class for a single sector/industry entry."""

    code: str
    name: str
    stock_count: int
    avg_price: Decimal
    change_pct: Decimal
    volume: Decimal
    amount: Decimal
    leading_stock: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "name": self.name,
            "stock_count": self.stock_count,
            "avg_price": self.avg_price,
            "change_pct": self.change_pct,
            "volume": self.volume,
            "amount": self.amount,
            "leading_stock": self.leading_stock,
        }


class SectorCollector:
    """Collector for Chinese A-share sector/industry data from Sina Finance."""

    def __init__(self):
        """Initialize the sector collector."""
        self._client = httpx.Client(
            timeout=HTTP_CLIENT_TIMEOUT,
            headers=SINA_HEADERS,
        )

    @property
    def name(self) -> str:
        """Return collector name."""
        return "sector_collector"

    @property
    def source(self) -> str:
        """Return data source name."""
        return "sina"

    def close(self):
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _parse_js_response(self, text: str) -> Dict[str, str]:
        """
        Parse Sina's JS variable assignment response into a Python dict.

        The response format is:
            var S_Finance_bankuai_sinaindustry = {"key":"val,...", ...}

        Args:
            text: Raw JS response text

        Returns:
            Dictionary mapping sector codes to comma-separated value strings

        Raises:
            ValueError: If the response cannot be parsed
        """
        match = JS_VAR_PATTERN.search(text)
        if not match:
            raise ValueError("Could not extract JS object from response")

        js_object_str = match.group(1)

        # The Sina response uses JS object syntax which is valid JSON
        try:
            return json.loads(js_object_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse sector data JSON: {e}")

    def _parse_sector_entry(self, code: str, raw_value: str) -> Optional[SectorData]:
        """
        Parse a single sector entry from comma-separated values.

        The value format is:
            code,name,count,avg_price,change,pct_change,volume,amount,
            leading_stock_code,leading_stock_price,leading_stock_close,
            leading_stock_change,leading_stock_name

        Args:
            code: Sector code (dict key)
            raw_value: Comma-separated value string

        Returns:
            SectorData or None if parsing fails
        """
        try:
            fields = raw_value.split(",")
            if len(fields) < 13:
                logger.warning(f"Sector entry {code} has insufficient fields: {len(fields)}")
                return None

            return SectorData(
                code=fields[0],
                name=fields[1],
                stock_count=int(fields[2]),
                avg_price=Decimal(fields[3]),
                change_pct=Decimal(fields[5]),
                volume=Decimal(fields[6]),
                amount=Decimal(fields[7]),
                leading_stock=fields[12],
            )
        except (ValueError, IndexError, InvalidOperation) as e:
            logger.warning(f"Failed to parse sector entry {code}: {e}")
            return None

    def _fetch_sectors(self, url: str, params: Optional[Dict] = None) -> List[SectorData]:
        """
        Fetch and parse sector data from a Sina API endpoint.

        Args:
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            List of SectorData objects
        """
        try:
            response = self._client.get(url, params=params)
            response.raise_for_status()

            raw_data = self._parse_js_response(response.text)

            sectors = []
            for code, value in raw_data.items():
                sector = self._parse_sector_entry(code, value)
                if sector is not None:
                    sectors.append(sector)

            return sectors

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching sectors from {url}: {e}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Network error fetching sectors from {url}: {e}")
            return []
        except ValueError as e:
            logger.error(f"Parse error for sectors from {url}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching sectors from {url}: {e}")
            return []

    def fetch_industry_sectors(self) -> List[SectorData]:
        """
        Fetch industry sector data (e.g., banking, real estate, auto).

        Returns:
            List of SectorData objects for industry sectors
        """
        return self._fetch_sectors(SINA_INDUSTRY_URL)

    def fetch_concept_sectors(self) -> List[SectorData]:
        """
        Fetch concept sector data (e.g., AI, biotech, new energy).

        Returns:
            List of SectorData objects for concept sectors
        """
        return self._fetch_sectors(SINA_CONCEPT_URL, params={"param": "class"})

    def fetch_all(self) -> Dict[str, List[SectorData]]:
        """
        Fetch both industry and concept sector data.

        Returns:
            Dictionary with 'industry' and 'concept' keys mapping to
            lists of SectorData objects
        """
        return {
            "industry": self.fetch_industry_sectors(),
            "concept": self.fetch_concept_sectors(),
        }
