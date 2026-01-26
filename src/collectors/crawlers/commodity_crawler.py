"""Commodity price crawler for lithium carbonate and polysilicon prices."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
import logging
import re

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class CommodityPriceData:
    """Data class for commodity price information.

    Attributes:
        commodity_name: Name of the commodity (e.g., "碳酸锂", "多晶硅")
        commodity_name_en: English name of the commodity
        price: Latest price value
        price_unit: Unit of price (e.g., "元/吨", "元/千克")
        price_change: Price change amount
        price_change_pct: Price change percentage
        price_date: Date of the price
        source: Data source name
    """

    commodity_name: str
    commodity_name_en: str
    price: Decimal
    price_unit: str
    price_change: Optional[Decimal]
    price_change_pct: Optional[Decimal]
    price_date: date
    source: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "commodity_name": self.commodity_name,
            "commodity_name_en": self.commodity_name_en,
            "price": self.price,
            "price_unit": self.price_unit,
            "price_change": self.price_change,
            "price_change_pct": self.price_change_pct,
            "price_date": self.price_date,
            "source": self.source,
        }


class CommodityCrawler:
    """Crawler for commodity price data.

    This crawler fetches commodity prices from multiple sources:
    1. AkShare futures_spot_price for lithium carbonate (碳酸锂)
    2. 生意社 (100ppi.com) for polysilicon (多晶硅) and other commodities

    Key commodities tracked:
    - 碳酸锂 (Lithium Carbonate) - Symbol: LC
    - 电池级碳酸锂 (Battery-grade Lithium Carbonate)
    - 多晶硅 (Polysilicon)

    Attributes:
        BASE_URL_100PPI: Base URL for 生意社 commodity data
        DEFAULT_TIMEOUT: Default request timeout in seconds
        USER_AGENT: User-Agent header for requests
    """

    BASE_URL_100PPI = "https://www.100ppi.com"
    DEFAULT_TIMEOUT = 30.0
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )

    # Commodity mappings for 100ppi.com
    # Format: (commodity_code, english_name, unit)
    COMMODITY_MAPPINGS = {
        "碳酸锂": ("tsl", "lithium_carbonate", "元/吨"),
        "电池级碳酸锂": ("tsl", "battery_grade_lithium_carbonate", "元/吨"),
        "多晶硅": ("djg", "polysilicon", "元/千克"),
    }

    # AkShare symbol mapping
    AKSHARE_SYMBOLS = {
        "碳酸锂": "LC",
        "电池级碳酸锂": "LC",
    }

    @property
    def name(self) -> str:
        """Return crawler name."""
        return "commodity_crawler"

    @property
    def source(self) -> str:
        """Return primary data source name."""
        return "100ppi"

    def _fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML content from URL.

        Args:
            url: URL to fetch

        Returns:
            HTML content string or None on error
        """
        try:
            response = httpx.get(
                url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=self.DEFAULT_TIMEOUT,
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def _parse_decimal(self, text: str) -> Optional[Decimal]:
        """Parse a decimal value from text.

        Args:
            text: Text containing the decimal (e.g., "172000.00", "75,050")

        Returns:
            Parsed Decimal value or None if invalid
        """
        if not text:
            return None

        # Remove commas, whitespace, and currency symbols
        cleaned = re.sub(r"[,\s¥$]", "", text.strip())
        if not cleaned:
            return None

        try:
            return Decimal(cleaned)
        except Exception:
            return None

    def _parse_percentage(self, text: str) -> Optional[Decimal]:
        """Parse a percentage value from text.

        Args:
            text: Text containing percentage (e.g., "+10.97%", "-2.5%")

        Returns:
            Parsed Decimal value (without % sign) or None if invalid
        """
        if not text:
            return None

        # Remove % sign and whitespace
        cleaned = text.strip().replace("%", "").replace("％", "")
        if not cleaned:
            return None

        try:
            return Decimal(cleaned)
        except Exception:
            return None

    def _parse_date(self, text: str) -> Optional[date]:
        """Parse date from text.

        Args:
            text: Text containing date (various formats)

        Returns:
            Parsed date or None if invalid
        """
        if not text:
            return None

        # Common date formats
        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y年%m月%d日",
            "%m月%d日",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(text.strip(), fmt)
                # If year is missing, use current year
                if "%Y" not in fmt:
                    parsed = parsed.replace(year=datetime.now().year)
                return parsed.date()
            except ValueError:
                continue

        return None

    def fetch_from_akshare(
        self, symbol: str = "LC", price_date: Optional[str] = None
    ) -> Optional[CommodityPriceData]:
        """Fetch commodity price from AkShare futures_spot_price.

        Args:
            symbol: Commodity symbol (default: "LC" for lithium carbonate)
            price_date: Date string in format "YYYYMMDD" (default: latest)

        Returns:
            CommodityPriceData or None if not found
        """
        try:
            import akshare as ak

            if price_date is None:
                # Use yesterday's date as latest might not be available
                from datetime import timedelta

                price_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

            df = ak.futures_spot_price(date=price_date)

            if df is None or df.empty:
                logger.warning(f"No data returned from AkShare for date {price_date}")
                return None

            # Find the row for the symbol
            # Column names may vary, try common variations
            symbol_col = None
            for col in ["symbol", "品种", "商品"]:
                if col in df.columns:
                    symbol_col = col
                    break

            if symbol_col is None:
                logger.warning("Could not find symbol column in AkShare data")
                return None

            # Filter for the symbol
            row = df[df[symbol_col] == symbol]
            if row.empty:
                logger.warning(f"Symbol {symbol} not found in AkShare data")
                return None

            row = row.iloc[0]

            # Get spot price
            spot_price_col = None
            for col in ["spot_price", "现货价", "现货价格"]:
                if col in df.columns:
                    spot_price_col = col
                    break

            if spot_price_col is None or row[spot_price_col] is None:
                logger.warning("Could not find spot price in AkShare data")
                return None

            spot_price = self._parse_decimal(str(row[spot_price_col]))
            if spot_price is None:
                return None

            # Get commodity name based on symbol
            commodity_name = "碳酸锂" if symbol == "LC" else symbol
            commodity_name_en = "lithium_carbonate" if symbol == "LC" else symbol

            return CommodityPriceData(
                commodity_name=commodity_name,
                commodity_name_en=commodity_name_en,
                price=spot_price,
                price_unit="元/吨",
                price_change=None,  # AkShare may not provide this directly
                price_change_pct=None,
                price_date=datetime.strptime(price_date, "%Y%m%d").date(),
                source="akshare",
            )

        except ImportError:
            logger.warning("AkShare not installed, falling back to web scraping")
            return None
        except Exception as e:
            logger.error(f"Error fetching from AkShare: {e}")
            return None

    def _build_100ppi_url(self, commodity_code: str) -> str:
        """Build URL for 100ppi.com commodity page.

        Args:
            commodity_code: Commodity code (e.g., "tsl" for lithium carbonate)

        Returns:
            URL string for the commodity price page
        """
        return f"https://{commodity_code}.100ppi.com/"

    def _parse_100ppi_page(
        self, html: str, commodity_name: str, commodity_name_en: str, unit: str
    ) -> Optional[CommodityPriceData]:
        """Parse 100ppi.com commodity page for price data.

        Args:
            html: HTML content to parse
            commodity_name: Chinese name of commodity
            commodity_name_en: English name of commodity
            unit: Price unit

        Returns:
            CommodityPriceData or None if parsing fails
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Find price element - 100ppi uses various structures
            # Try to find price in common locations
            price = None
            price_change_pct = None
            price_date = date.today()

            # Look for price in stat info section
            stat_info = soup.find("div", class_="stat-info")
            if stat_info:
                # Try to find price value
                price_elem = stat_info.find("span", class_="price")
                if price_elem:
                    price = self._parse_decimal(price_elem.get_text())

                # Try to find change percentage
                change_elem = stat_info.find("span", class_="change")
                if change_elem:
                    price_change_pct = self._parse_percentage(change_elem.get_text())

            # Alternative: Look for price in table
            if price is None:
                tables = soup.find_all("table")
                for table in tables:
                    rows = table.find_all("tr")
                    for row in rows:
                        cells = row.find_all(["td", "th"])
                        for i, cell in enumerate(cells):
                            text = cell.get_text(strip=True)
                            if "价格" in text or "报价" in text:
                                # Next cell might have the price
                                if i + 1 < len(cells):
                                    price = self._parse_decimal(
                                        cells[i + 1].get_text(strip=True)
                                    )
                                    if price:
                                        break

            # Alternative: Look for price in divs with class containing 'price'
            if price is None:
                price_divs = soup.find_all(
                    lambda tag: tag.name in ["div", "span"]
                    and tag.get("class")
                    and any("price" in c.lower() for c in tag.get("class", []))
                )
                for div in price_divs:
                    price = self._parse_decimal(div.get_text())
                    if price and price > Decimal("0"):
                        break

            # Try to find date
            date_elem = soup.find(string=re.compile(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}"))
            if date_elem:
                price_date = self._parse_date(str(date_elem)) or date.today()

            if price is None:
                logger.warning(
                    f"Could not extract price for {commodity_name} from 100ppi"
                )
                return None

            return CommodityPriceData(
                commodity_name=commodity_name,
                commodity_name_en=commodity_name_en,
                price=price,
                price_unit=unit,
                price_change=None,
                price_change_pct=price_change_pct,
                price_date=price_date,
                source="100ppi",
            )

        except Exception as e:
            logger.error(f"Error parsing 100ppi page for {commodity_name}: {e}")
            return None

    def fetch_from_100ppi(self, commodity_name: str) -> Optional[CommodityPriceData]:
        """Fetch commodity price from 100ppi.com.

        Args:
            commodity_name: Chinese name of the commodity

        Returns:
            CommodityPriceData or None if not found
        """
        if commodity_name not in self.COMMODITY_MAPPINGS:
            logger.warning(f"Unknown commodity: {commodity_name}")
            return None

        commodity_code, commodity_name_en, unit = self.COMMODITY_MAPPINGS[
            commodity_name
        ]
        url = self._build_100ppi_url(commodity_code)

        html = self._fetch_html(url)
        if not html:
            return None

        return self._parse_100ppi_page(html, commodity_name, commodity_name_en, unit)

    def fetch_lithium_carbonate(self) -> Optional[CommodityPriceData]:
        """Fetch lithium carbonate (碳酸锂) price.

        Tries AkShare first, then falls back to 100ppi.com.

        Returns:
            CommodityPriceData for lithium carbonate or None if not found
        """
        # Try AkShare first (more reliable API)
        result = self.fetch_from_akshare(symbol="LC")
        if result:
            return result

        # Fall back to 100ppi.com
        return self.fetch_from_100ppi("碳酸锂")

    def fetch_battery_grade_lithium_carbonate(self) -> Optional[CommodityPriceData]:
        """Fetch battery-grade lithium carbonate (电池级碳酸锂) price.

        Returns:
            CommodityPriceData for battery-grade lithium carbonate or None if not found
        """
        # Battery-grade lithium carbonate uses the same symbol in futures
        result = self.fetch_from_akshare(symbol="LC")
        if result:
            # Update name to battery-grade
            return CommodityPriceData(
                commodity_name="电池级碳酸锂",
                commodity_name_en="battery_grade_lithium_carbonate",
                price=result.price,
                price_unit=result.price_unit,
                price_change=result.price_change,
                price_change_pct=result.price_change_pct,
                price_date=result.price_date,
                source=result.source,
            )

        # Fall back to 100ppi.com
        return self.fetch_from_100ppi("电池级碳酸锂")

    def fetch_polysilicon(self) -> Optional[CommodityPriceData]:
        """Fetch polysilicon (多晶硅) price.

        Uses 100ppi.com as the primary source.

        Returns:
            CommodityPriceData for polysilicon or None if not found
        """
        return self.fetch_from_100ppi("多晶硅")

    def fetch_all_tracked_commodities(self) -> Dict[str, Optional[CommodityPriceData]]:
        """Fetch prices for all tracked commodities.

        Returns:
            Dictionary mapping commodity names to their price data
        """
        results: Dict[str, Optional[CommodityPriceData]] = {}

        # Fetch each tracked commodity
        results["碳酸锂"] = self.fetch_lithium_carbonate()
        results["电池级碳酸锂"] = self.fetch_battery_grade_lithium_carbonate()
        results["多晶硅"] = self.fetch_polysilicon()

        return results

    def fetch_commodity_by_name(
        self, commodity_name: str
    ) -> Optional[CommodityPriceData]:
        """Fetch price for a specific commodity by name.

        Args:
            commodity_name: Chinese name of the commodity

        Returns:
            CommodityPriceData or None if not found
        """
        if commodity_name == "碳酸锂":
            return self.fetch_lithium_carbonate()
        elif commodity_name == "电池级碳酸锂":
            return self.fetch_battery_grade_lithium_carbonate()
        elif commodity_name == "多晶硅":
            return self.fetch_polysilicon()
        else:
            # Try generic 100ppi fetch
            return self.fetch_from_100ppi(commodity_name)
