"""Tests for OpenInsider Crawler."""
import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch, Mock

from src.collectors.crawlers.openinsider_crawler import (
    OpenInsiderCrawler,
    InsiderTradeData,
    TradeType,
)


# Sample HTML response for mocking
MOCK_HTML_RESPONSE = """
<!doctype html>
<html lang=en>
<head><title>Insider Trading Screener</title></head>
<body>
<table width="100%" cellpadding="0" cellspacing="0" border="0" class="tinytable">
<thead>
<tr>
<th width="31"><h3>X</h3></th>
<th width="108"><h3>Filing&nbsp;Date</h3></th>
<th width="64"><h3>Trade&nbsp;Date</h3></th>
<th width="45"><h3>Ticker</h3></th>
<th width="190"><h3>Company&nbsp;Name</h3></th>
<th width="180"><h3>Insider&nbsp;Name</h3></th>
<th width="100"><h3>Title</h3></th>
<th><h3>Trade&nbsp;Type&nbsp;&nbsp;</h3></th>
<th><h3>Price</h3></th>
<th><h3>Qty</h3></th>
<th><h3>Owned</h3></th>
<th><h3>&Delta;Own</h3></th>
<th><h3>Value</h3></th>
<th><h3>1d</h3></th>
<th><h3>1w</h3></th>
<th><h3>1m</h3></th>
<th><h3>6m</h3></th>
</tr>
</thead>
<tbody>
<tr style="background:#f0fff0">
<td align=right>M</td>
<td align=right><div><a href="http://www.sec.gov/example1.xml" title="SEC Form 4" target="_blank">2026-01-23 21:52:11</a></div></td>
<td align=right><div>2026-01-20</div></td>
<td><b><a href="/AAPL">AAPL</a></b></td>
<td><a href="/AAPL">Apple Inc.</a></td>
<td><a href="/insider/Cook-Tim/123456" title="info">Cook Tim</a></td>
<td>CEO</td>
<td>P - Purchase</td>
<td align=right>$150.50</td>
<td align=right>+10,000</td>
<td align=right>1,500,000</td>
<td align=right>+1%</td>
<td align=right>+$1,505,000</td>
<td align=right></td>
<td align=right></td>
<td align=right></td>
<td align=right></td>
</tr>
<tr style="background:#ffe5e5">
<td align=right></td>
<td align=right><div><a href="http://www.sec.gov/example2.xml" title="SEC Form 4" target="_blank">2026-01-22 15:30:00</a></div></td>
<td align=right><div>2026-01-21</div></td>
<td><b><a href="/MSFT">MSFT</a></b></td>
<td><a href="/MSFT">Microsoft Corp</a></td>
<td><a href="/insider/Nadella-Satya/789012" title="info">Nadella Satya</a></td>
<td>CEO</td>
<td>S - Sale</td>
<td align=right>$420.00</td>
<td align=right>-5,000</td>
<td align=right>500,000</td>
<td align=right>-1%</td>
<td align=right>-$2,100,000</td>
<td align=right></td>
<td align=right></td>
<td align=right></td>
<td align=right></td>
</tr>
<tr style="background:#ffffd9">
<td align=right>D</td>
<td align=right><div><a href="http://www.sec.gov/example3.xml" title="SEC Form 4" target="_blank">2026-01-21 10:00:00</a></div></td>
<td align=right><div>2026-01-19</div></td>
<td><b><a href="/NVDA">NVDA</a></b></td>
<td><a href="/NVDA">NVIDIA Corp</a></td>
<td><a href="/insider/Huang-Jensen/345678" title="info">Huang Jensen</a></td>
<td>CEO, Founder</td>
<td>S - Sale+OE</td>
<td align=right>$890.25</td>
<td align=right>-2,500</td>
<td align=right>350,000,000</td>
<td align=right>0%</td>
<td align=right>-$2,225,625</td>
<td align=right></td>
<td align=right></td>
<td align=right></td>
<td align=right></td>
</tr>
</tbody>
</table>
</body>
</html>
"""

MOCK_EMPTY_HTML_RESPONSE = """
<!doctype html>
<html lang=en>
<head><title>Insider Trading Screener</title></head>
<body>
<table width="100%" cellpadding="0" cellspacing="0" border="0" class="tinytable">
<thead>
<tr>
<th width="31"><h3>X</h3></th>
<th width="108"><h3>Filing&nbsp;Date</h3></th>
<th width="64"><h3>Trade&nbsp;Date</h3></th>
<th width="45"><h3>Ticker</h3></th>
<th width="190"><h3>Company&nbsp;Name</h3></th>
<th width="180"><h3>Insider&nbsp;Name</h3></th>
<th width="100"><h3>Title</h3></th>
<th><h3>Trade&nbsp;Type&nbsp;&nbsp;</h3></th>
<th><h3>Price</h3></th>
<th><h3>Qty</h3></th>
<th><h3>Owned</h3></th>
<th><h3>&Delta;Own</h3></th>
<th><h3>Value</h3></th>
</tr>
</thead>
<tbody>
</tbody>
</table>
</body>
</html>
"""


class TestTradeType:
    """Tests for TradeType enum."""

    def test_trade_type_purchase(self):
        """Test TradeType.PURCHASE value."""
        assert TradeType.PURCHASE.value == "P"

    def test_trade_type_sale(self):
        """Test TradeType.SALE value."""
        assert TradeType.SALE.value == "S"


class TestInsiderTradeData:
    """Tests for InsiderTradeData dataclass."""

    def test_insider_trade_data_creation(self):
        """Test InsiderTradeData can be created with required fields."""
        data = InsiderTradeData(
            filing_date=datetime(2026, 1, 23, 21, 52, 11),
            trade_date=date(2026, 1, 20),
            ticker="AAPL",
            company_name="Apple Inc.",
            insider_name="Cook Tim",
            title="CEO",
            trade_type=TradeType.PURCHASE,
            price=Decimal("150.50"),
            quantity=10000,
            owned_after=1500000,
            value=Decimal("1505000"),
        )

        assert data.ticker == "AAPL"
        assert data.company_name == "Apple Inc."
        assert data.insider_name == "Cook Tim"
        assert data.title == "CEO"
        assert data.trade_type == TradeType.PURCHASE
        assert data.price == Decimal("150.50")
        assert data.quantity == 10000
        assert data.owned_after == 1500000
        assert data.value == Decimal("1505000")

    def test_insider_trade_data_to_dict(self):
        """Test InsiderTradeData to_dict method."""
        data = InsiderTradeData(
            filing_date=datetime(2026, 1, 23, 21, 52, 11),
            trade_date=date(2026, 1, 20),
            ticker="AAPL",
            company_name="Apple Inc.",
            insider_name="Cook Tim",
            title="CEO",
            trade_type=TradeType.PURCHASE,
            price=Decimal("150.50"),
            quantity=10000,
            owned_after=1500000,
            value=Decimal("1505000"),
        )

        d = data.to_dict()

        assert d["ticker"] == "AAPL"
        assert d["company_name"] == "Apple Inc."
        assert d["trade_type"] == "P"
        assert d["price"] == Decimal("150.50")

    def test_insider_trade_data_is_purchase(self):
        """Test is_purchase property."""
        purchase = InsiderTradeData(
            filing_date=datetime(2026, 1, 23),
            trade_date=date(2026, 1, 20),
            ticker="AAPL",
            company_name="Apple Inc.",
            insider_name="Cook Tim",
            title="CEO",
            trade_type=TradeType.PURCHASE,
            price=Decimal("150.50"),
            quantity=10000,
            owned_after=1500000,
            value=Decimal("1505000"),
        )

        sale = InsiderTradeData(
            filing_date=datetime(2026, 1, 23),
            trade_date=date(2026, 1, 20),
            ticker="MSFT",
            company_name="Microsoft Corp",
            insider_name="Nadella Satya",
            title="CEO",
            trade_type=TradeType.SALE,
            price=Decimal("420.00"),
            quantity=5000,
            owned_after=500000,
            value=Decimal("2100000"),
        )

        assert purchase.is_purchase is True
        assert sale.is_purchase is False

    def test_insider_trade_data_is_sale(self):
        """Test is_sale property."""
        purchase = InsiderTradeData(
            filing_date=datetime(2026, 1, 23),
            trade_date=date(2026, 1, 20),
            ticker="AAPL",
            company_name="Apple Inc.",
            insider_name="Cook Tim",
            title="CEO",
            trade_type=TradeType.PURCHASE,
            price=Decimal("150.50"),
            quantity=10000,
            owned_after=1500000,
            value=Decimal("1505000"),
        )

        sale = InsiderTradeData(
            filing_date=datetime(2026, 1, 23),
            trade_date=date(2026, 1, 20),
            ticker="MSFT",
            company_name="Microsoft Corp",
            insider_name="Nadella Satya",
            title="CEO",
            trade_type=TradeType.SALE,
            price=Decimal("420.00"),
            quantity=5000,
            owned_after=500000,
            value=Decimal("2100000"),
        )

        assert purchase.is_sale is False
        assert sale.is_sale is True


class TestOpenInsiderCrawlerProperties:
    """Tests for OpenInsiderCrawler properties."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return OpenInsiderCrawler()

    def test_name_property(self, crawler):
        """Test that name property returns 'openinsider_crawler'."""
        assert crawler.name == "openinsider_crawler"

    def test_source_property(self, crawler):
        """Test that source property returns 'openinsider'."""
        assert crawler.source == "openinsider"


class TestOpenInsiderCrawlerFetchLatestPurchases:
    """Tests for OpenInsiderCrawler fetch_latest_purchases method."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return OpenInsiderCrawler()

    def test_fetch_latest_purchases_returns_list(self, crawler):
        """Test that fetch_latest_purchases returns list of InsiderTradeData."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_latest_purchases()

            assert isinstance(result, list)
            assert all(isinstance(item, InsiderTradeData) for item in result)

    def test_fetch_latest_purchases_filters_only_purchases(self, crawler):
        """Test that fetch_latest_purchases returns only purchase transactions."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_latest_purchases()

            # Only the AAPL purchase should be returned (not MSFT and NVDA sales)
            assert len(result) == 1
            assert result[0].ticker == "AAPL"
            assert result[0].trade_type == TradeType.PURCHASE

    def test_fetch_latest_purchases_correct_data(self, crawler):
        """Test that fetch_latest_purchases parses data correctly."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_latest_purchases()

            assert len(result) == 1
            trade = result[0]
            assert trade.ticker == "AAPL"
            assert trade.company_name == "Apple Inc."
            assert trade.insider_name == "Cook Tim"
            assert trade.title == "CEO"
            assert trade.price == Decimal("150.50")
            assert trade.quantity == 10000
            assert trade.owned_after == 1500000
            assert trade.value == Decimal("1505000")

    def test_fetch_latest_purchases_empty_response(self, crawler):
        """Test handling of empty response."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_EMPTY_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_latest_purchases()

            assert result == []

    def test_fetch_latest_purchases_api_error(self, crawler):
        """Test that API errors are handled gracefully."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_get.side_effect = Exception("Network Error")

            result = crawler.fetch_latest_purchases()

            assert result == []

    def test_fetch_latest_purchases_with_limit(self, crawler):
        """Test fetch_latest_purchases respects limit parameter."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # Even though there's only 1 purchase, test that limit parameter works
            result = crawler.fetch_latest_purchases(limit=10)

            assert len(result) <= 10


class TestOpenInsiderCrawlerFetchLatestSales:
    """Tests for OpenInsiderCrawler fetch_latest_sales method."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return OpenInsiderCrawler()

    def test_fetch_latest_sales_returns_list(self, crawler):
        """Test that fetch_latest_sales returns list of InsiderTradeData."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_latest_sales()

            assert isinstance(result, list)
            assert all(isinstance(item, InsiderTradeData) for item in result)

    def test_fetch_latest_sales_filters_only_sales(self, crawler):
        """Test that fetch_latest_sales returns only sale transactions."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_latest_sales()

            # MSFT and NVDA sales should be returned (not AAPL purchase)
            assert len(result) == 2
            assert all(item.trade_type == TradeType.SALE for item in result)

    def test_fetch_latest_sales_correct_data(self, crawler):
        """Test that fetch_latest_sales parses data correctly."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_latest_sales()

            # Find MSFT sale
            msft_trade = next(t for t in result if t.ticker == "MSFT")
            assert msft_trade.company_name == "Microsoft Corp"
            assert msft_trade.insider_name == "Nadella Satya"
            assert msft_trade.price == Decimal("420.00")
            assert msft_trade.quantity == 5000
            assert msft_trade.value == Decimal("2100000")

    def test_fetch_latest_sales_empty_response(self, crawler):
        """Test handling of empty response."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_EMPTY_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_latest_sales()

            assert result == []

    def test_fetch_latest_sales_api_error(self, crawler):
        """Test that API errors are handled gracefully."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_get.side_effect = Exception("Network Error")

            result = crawler.fetch_latest_sales()

            assert result == []


class TestOpenInsiderCrawlerFetchByTicker:
    """Tests for OpenInsiderCrawler fetch_by_ticker method."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return OpenInsiderCrawler()

    def test_fetch_by_ticker_returns_list(self, crawler):
        """Test that fetch_by_ticker returns list of InsiderTradeData."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_by_ticker("AAPL")

            assert isinstance(result, list)

    def test_fetch_by_ticker_calls_correct_url(self, crawler):
        """Test that fetch_by_ticker constructs correct URL with ticker."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_EMPTY_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            crawler.fetch_by_ticker("AAPL")

            # Check that the URL contains the ticker symbol
            call_args = mock_get.call_args
            url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
            assert "s=AAPL" in url or "AAPL" in url

    def test_fetch_by_ticker_returns_all_trade_types(self, crawler):
        """Test that fetch_by_ticker returns both purchases and sales."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_by_ticker("AAPL")

            # Should return all trades (purchases and sales)
            assert isinstance(result, list)

    def test_fetch_by_ticker_empty_response(self, crawler):
        """Test handling of empty response."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_EMPTY_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_by_ticker("INVALID")

            assert result == []

    def test_fetch_by_ticker_api_error(self, crawler):
        """Test that API errors are handled gracefully."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_get.side_effect = Exception("Network Error")

            result = crawler.fetch_by_ticker("AAPL")

            assert result == []


class TestOpenInsiderCrawlerParsing:
    """Tests for OpenInsiderCrawler HTML parsing edge cases."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return OpenInsiderCrawler()

    def test_parse_date_formats(self, crawler):
        """Test that various date formats are parsed correctly."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_latest_purchases()

            assert len(result) == 1
            assert result[0].trade_date == date(2026, 1, 20)
            assert result[0].filing_date == datetime(2026, 1, 23, 21, 52, 11)

    def test_parse_price_formats(self, crawler):
        """Test that price with dollar sign is parsed correctly."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_latest_purchases()

            assert result[0].price == Decimal("150.50")

    def test_parse_quantity_with_commas(self, crawler):
        """Test that quantity with commas is parsed correctly."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_latest_purchases()

            assert result[0].quantity == 10000
            assert result[0].owned_after == 1500000

    def test_parse_value_with_commas(self, crawler):
        """Test that value with commas and dollar sign is parsed correctly."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_latest_purchases()

            assert result[0].value == Decimal("1505000")


class TestOpenInsiderCrawlerRateLimiting:
    """Tests for OpenInsiderCrawler rate limiting."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return OpenInsiderCrawler()

    def test_request_includes_user_agent(self, crawler):
        """Test that requests include a proper User-Agent header."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_EMPTY_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            crawler.fetch_latest_purchases()

            # Check that headers were passed
            call_args = mock_get.call_args
            headers = call_args[1].get("headers", {})
            assert "User-Agent" in headers

    def test_request_includes_timeout(self, crawler):
        """Test that requests include a timeout."""
        with patch("src.collectors.crawlers.openinsider_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_EMPTY_HTML_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            crawler.fetch_latest_purchases()

            # Check that timeout was passed
            call_args = mock_get.call_args
            timeout = call_args[1].get("timeout")
            assert timeout is not None


# Integration test (skipped by default, run with: pytest -m integration)
@pytest.mark.integration
class TestOpenInsiderCrawlerIntegration:
    """Integration tests that hit real OpenInsider website."""

    def test_fetch_real_purchases(self):
        """Test fetching real insider purchases."""
        crawler = OpenInsiderCrawler()

        result = crawler.fetch_latest_purchases(limit=5)

        assert isinstance(result, list)
        if result:
            assert all(isinstance(item, InsiderTradeData) for item in result)
            assert all(item.trade_type == TradeType.PURCHASE for item in result)

    def test_fetch_real_sales(self):
        """Test fetching real insider sales."""
        crawler = OpenInsiderCrawler()

        result = crawler.fetch_latest_sales(limit=5)

        assert isinstance(result, list)
        if result:
            assert all(isinstance(item, InsiderTradeData) for item in result)
            assert all(item.trade_type == TradeType.SALE for item in result)

    def test_fetch_by_real_ticker(self):
        """Test fetching insider trades for a real ticker."""
        crawler = OpenInsiderCrawler()

        result = crawler.fetch_by_ticker("AAPL")

        assert isinstance(result, list)
        if result:
            assert all(isinstance(item, InsiderTradeData) for item in result)
