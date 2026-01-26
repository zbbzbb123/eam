"""OpenInsider crawler for US insider trading data."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional
import logging
import re

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class TradeType(Enum):
    """Insider trade type enum."""
    PURCHASE = "P"
    SALE = "S"


@dataclass
class InsiderTradeData:
    """Data class for insider trade information."""

    filing_date: datetime
    trade_date: date
    ticker: str
    company_name: str
    insider_name: str
    title: str
    trade_type: TradeType
    price: Decimal
    quantity: int
    owned_after: int
    value: Decimal

    @property
    def is_purchase(self) -> bool:
        """Check if this is a purchase transaction."""
        return self.trade_type == TradeType.PURCHASE

    @property
    def is_sale(self) -> bool:
        """Check if this is a sale transaction."""
        return self.trade_type == TradeType.SALE

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "filing_date": self.filing_date,
            "trade_date": self.trade_date,
            "ticker": self.ticker,
            "company_name": self.company_name,
            "insider_name": self.insider_name,
            "title": self.title,
            "trade_type": self.trade_type.value,
            "price": self.price,
            "quantity": self.quantity,
            "owned_after": self.owned_after,
            "value": self.value,
        }


class OpenInsiderCrawler:
    """Crawler for OpenInsider.com insider trading data.

    This crawler fetches SEC Form 4 filings from OpenInsider.com which
    tracks US insider trading activity (purchases and sales by company
    executives, directors, and major shareholders).

    Attributes:
        BASE_URL: Base URL for OpenInsider screener
        DEFAULT_TIMEOUT: Default request timeout in seconds
        USER_AGENT: User-Agent header for requests
    """

    BASE_URL = "http://openinsider.com/screener"
    DEFAULT_TIMEOUT = 30.0
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )

    @property
    def name(self) -> str:
        """Return crawler name."""
        return "openinsider_crawler"

    @property
    def source(self) -> str:
        """Return data source name."""
        return "openinsider"

    def _build_url(
        self,
        ticker: Optional[str] = None,
        purchases_only: bool = False,
        sales_only: bool = False,
        filing_days: int = 7,
        limit: int = 100,
    ) -> str:
        """Build screener URL with parameters.

        Args:
            ticker: Optional ticker symbol to filter by
            purchases_only: If True, only show purchases
            sales_only: If True, only show sales
            filing_days: Number of days to look back for filings
            limit: Maximum number of results

        Returns:
            Constructed URL string
        """
        params = {
            "s": ticker or "",
            "o": "",
            "pl": "",
            "ph": "",
            "ll": "",
            "lh": "",
            "fd": str(filing_days),
            "fdr": "",
            "td": "0",
            "tdr": "",
            "feession": "all",
            "sort": "",
            "cnt": str(limit),
        }

        # Add transaction type filters
        if purchases_only:
            params["xp"] = "1"
        elif sales_only:
            params["xs"] = "1"
        else:
            # Include both purchases and sales
            params["xp"] = "1"
            params["xs"] = "1"

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.BASE_URL}?{query_string}"

    def _parse_number(self, text: str) -> int:
        """Parse a number from text, removing commas and +/- signs.

        Args:
            text: Text containing the number

        Returns:
            Parsed integer value
        """
        # Remove dollar signs, commas, plus/minus signs, and whitespace
        cleaned = re.sub(r"[$,+\-\s]", "", text.strip())
        if not cleaned:
            return 0
        try:
            return int(cleaned)
        except ValueError:
            return 0

    def _parse_decimal(self, text: str) -> Decimal:
        """Parse a decimal from text, removing dollar signs and commas.

        Args:
            text: Text containing the decimal

        Returns:
            Parsed Decimal value
        """
        # Remove dollar signs, commas, plus/minus signs, and whitespace
        cleaned = re.sub(r"[$,+\-\s]", "", text.strip())
        if not cleaned:
            return Decimal("0")
        try:
            return Decimal(cleaned)
        except Exception:
            return Decimal("0")

    def _parse_trade_type(self, text: str) -> Optional[TradeType]:
        """Parse trade type from text.

        Args:
            text: Text containing trade type (e.g., "P - Purchase", "S - Sale")

        Returns:
            TradeType enum or None if not recognized
        """
        text = text.strip().upper()
        if text.startswith("P"):
            return TradeType.PURCHASE
        elif text.startswith("S"):
            return TradeType.SALE
        return None

    def _parse_filing_date(self, text: str) -> Optional[datetime]:
        """Parse filing date and time from text.

        Args:
            text: Text containing datetime (e.g., "2026-01-23 21:52:11")

        Returns:
            Parsed datetime or None if invalid
        """
        try:
            return datetime.strptime(text.strip(), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                return datetime.strptime(text.strip(), "%Y-%m-%d")
            except ValueError:
                return None

    def _parse_trade_date(self, text: str) -> Optional[date]:
        """Parse trade date from text.

        Args:
            text: Text containing date (e.g., "2026-01-20")

        Returns:
            Parsed date or None if invalid
        """
        try:
            return datetime.strptime(text.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None

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

    def _parse_html(self, html: str) -> List[InsiderTradeData]:
        """Parse insider trades from HTML content.

        Args:
            html: HTML content to parse

        Returns:
            List of InsiderTradeData objects
        """
        trades = []
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Find the data table by class
            table = soup.find("table", class_="tinytable")
            if not table:
                logger.warning("Could not find tinytable in HTML")
                return trades

            # Find tbody and iterate through rows
            tbody = table.find("tbody")
            if not tbody:
                logger.warning("Could not find tbody in table")
                return trades

            rows = tbody.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 13:
                    continue

                try:
                    # Extract filing date from the link text
                    filing_date_cell = cells[1]
                    filing_date_link = filing_date_cell.find("a")
                    if filing_date_link:
                        filing_date_text = filing_date_link.get_text(strip=True)
                    else:
                        filing_date_text = filing_date_cell.get_text(strip=True)
                    filing_date = self._parse_filing_date(filing_date_text)

                    # Extract trade date
                    trade_date_text = cells[2].get_text(strip=True)
                    trade_date = self._parse_trade_date(trade_date_text)

                    # Extract ticker
                    ticker_link = cells[3].find("a")
                    ticker = ticker_link.get_text(strip=True) if ticker_link else cells[3].get_text(strip=True)

                    # Extract company name
                    company_link = cells[4].find("a")
                    company_name = company_link.get_text(strip=True) if company_link else cells[4].get_text(strip=True)

                    # Extract insider name
                    insider_link = cells[5].find("a")
                    insider_name = insider_link.get_text(strip=True) if insider_link else cells[5].get_text(strip=True)

                    # Extract title
                    title = cells[6].get_text(strip=True)

                    # Extract trade type
                    trade_type_text = cells[7].get_text(strip=True)
                    trade_type = self._parse_trade_type(trade_type_text)

                    # Extract price
                    price_text = cells[8].get_text(strip=True)
                    price = self._parse_decimal(price_text)

                    # Extract quantity
                    quantity_text = cells[9].get_text(strip=True)
                    quantity = self._parse_number(quantity_text)

                    # Extract owned after
                    owned_text = cells[10].get_text(strip=True)
                    owned_after = self._parse_number(owned_text)

                    # Extract value (column 12, after own change)
                    value_text = cells[12].get_text(strip=True)
                    value = self._parse_decimal(value_text)

                    # Skip if we couldn't parse essential fields
                    if not filing_date or not trade_date or not trade_type:
                        continue

                    trade = InsiderTradeData(
                        filing_date=filing_date,
                        trade_date=trade_date,
                        ticker=ticker,
                        company_name=company_name,
                        insider_name=insider_name,
                        title=title,
                        trade_type=trade_type,
                        price=price,
                        quantity=quantity,
                        owned_after=owned_after,
                        value=value,
                    )
                    trades.append(trade)

                except Exception as e:
                    logger.debug(f"Error parsing row: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")

        return trades

    def fetch_latest_purchases(self, limit: int = 100) -> List[InsiderTradeData]:
        """Fetch latest insider purchase transactions.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of InsiderTradeData for purchase transactions
        """
        try:
            url = self._build_url(purchases_only=True, limit=limit)
            html = self._fetch_html(url)
            if not html:
                return []

            trades = self._parse_html(html)
            # Filter for purchases only (in case the API returns mixed results)
            return [t for t in trades if t.trade_type == TradeType.PURCHASE][:limit]

        except Exception as e:
            logger.error(f"Error fetching latest purchases: {e}")
            return []

    def fetch_latest_sales(self, limit: int = 100) -> List[InsiderTradeData]:
        """Fetch latest insider sale transactions.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of InsiderTradeData for sale transactions
        """
        try:
            url = self._build_url(sales_only=True, limit=limit)
            html = self._fetch_html(url)
            if not html:
                return []

            trades = self._parse_html(html)
            # Filter for sales only (in case the API returns mixed results)
            return [t for t in trades if t.trade_type == TradeType.SALE][:limit]

        except Exception as e:
            logger.error(f"Error fetching latest sales: {e}")
            return []

    def fetch_by_ticker(
        self,
        ticker: str,
        limit: int = 100,
    ) -> List[InsiderTradeData]:
        """Fetch insider trades for a specific ticker symbol.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            limit: Maximum number of results to return

        Returns:
            List of InsiderTradeData for the ticker
        """
        try:
            url = self._build_url(ticker=ticker, limit=limit)
            html = self._fetch_html(url)
            if not html:
                return []

            return self._parse_html(html)[:limit]

        except Exception as e:
            logger.error(f"Error fetching trades for {ticker}: {e}")
            return []

    def fetch_all(self, limit: int = 100) -> List[InsiderTradeData]:
        """Fetch all latest insider trades (both purchases and sales).

        Args:
            limit: Maximum number of results to return

        Returns:
            List of InsiderTradeData for all transaction types
        """
        try:
            url = self._build_url(limit=limit)
            html = self._fetch_html(url)
            if not html:
                return []

            return self._parse_html(html)[:limit]

        except Exception as e:
            logger.error(f"Error fetching all trades: {e}")
            return []
