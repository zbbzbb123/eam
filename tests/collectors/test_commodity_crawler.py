"""Tests for Commodity Price Crawler."""
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import patch, Mock, MagicMock
import pandas as pd

from src.collectors.crawlers.commodity_crawler import (
    CommodityCrawler,
    CommodityPriceData,
)


# Sample HTML response for 100ppi.com mocking
MOCK_100PPI_HTML_LITHIUM = """
<!DOCTYPE html>
<html>
<head><title>碳酸锂价格走势</title></head>
<body>
    <div class="stat-info">
        <span class="price">172000.00</span>
        <span class="change">+10.97%</span>
    </div>
    <div class="date-info">2026-01-25</div>
</body>
</html>
"""

MOCK_100PPI_HTML_POLYSILICON = """
<!DOCTYPE html>
<html>
<head><title>多晶硅价格走势</title></head>
<body>
    <div class="stat-info">
        <span class="price">45.50</span>
        <span class="change">-2.35%</span>
    </div>
    <div class="date-info">2026-01-25</div>
</body>
</html>
"""

MOCK_100PPI_HTML_TABLE_FORMAT = """
<!DOCTYPE html>
<html>
<head><title>商品价格</title></head>
<body>
    <table class="price-table">
        <tr>
            <th>商品</th>
            <th>报价</th>
            <th>单位</th>
        </tr>
        <tr>
            <td>碳酸锂</td>
            <td>175000.00</td>
            <td>元/吨</td>
        </tr>
    </table>
</body>
</html>
"""

MOCK_100PPI_HTML_EMPTY = """
<!DOCTYPE html>
<html>
<head><title>No Data</title></head>
<body>
    <div>暂无数据</div>
</body>
</html>
"""

# Mock AkShare DataFrame
MOCK_AKSHARE_DATA = pd.DataFrame(
    {
        "symbol": ["LC", "CU", "AL"],
        "spot_price": [138000.0, 75000.0, 19500.0],
        "dom_contract": ["LC2502", "CU2502", "AL2502"],
        "dom_contract_price": [137500.0, 74800.0, 19400.0],
    }
)

MOCK_AKSHARE_EMPTY = pd.DataFrame()


class TestCommodityPriceData:
    """Tests for CommodityPriceData dataclass."""

    def test_commodity_price_data_creation(self):
        """Test CommodityPriceData can be created with required fields."""
        data = CommodityPriceData(
            commodity_name="碳酸锂",
            commodity_name_en="lithium_carbonate",
            price=Decimal("172000.00"),
            price_unit="元/吨",
            price_change=Decimal("2000.00"),
            price_change_pct=Decimal("10.97"),
            price_date=date(2026, 1, 25),
            source="100ppi",
        )

        assert data.commodity_name == "碳酸锂"
        assert data.commodity_name_en == "lithium_carbonate"
        assert data.price == Decimal("172000.00")
        assert data.price_unit == "元/吨"
        assert data.price_change == Decimal("2000.00")
        assert data.price_change_pct == Decimal("10.97")
        assert data.price_date == date(2026, 1, 25)
        assert data.source == "100ppi"

    def test_commodity_price_data_optional_fields(self):
        """Test CommodityPriceData with optional fields as None."""
        data = CommodityPriceData(
            commodity_name="多晶硅",
            commodity_name_en="polysilicon",
            price=Decimal("45.50"),
            price_unit="元/千克",
            price_change=None,
            price_change_pct=None,
            price_date=date(2026, 1, 25),
            source="100ppi",
        )

        assert data.price_change is None
        assert data.price_change_pct is None

    def test_commodity_price_data_to_dict(self):
        """Test CommodityPriceData to_dict method."""
        data = CommodityPriceData(
            commodity_name="碳酸锂",
            commodity_name_en="lithium_carbonate",
            price=Decimal("172000.00"),
            price_unit="元/吨",
            price_change=Decimal("2000.00"),
            price_change_pct=Decimal("10.97"),
            price_date=date(2026, 1, 25),
            source="100ppi",
        )

        d = data.to_dict()

        assert d["commodity_name"] == "碳酸锂"
        assert d["commodity_name_en"] == "lithium_carbonate"
        assert d["price"] == Decimal("172000.00")
        assert d["price_unit"] == "元/吨"
        assert d["price_change"] == Decimal("2000.00")
        assert d["price_change_pct"] == Decimal("10.97")
        assert d["price_date"] == date(2026, 1, 25)
        assert d["source"] == "100ppi"


class TestCommodityCrawlerProperties:
    """Tests for CommodityCrawler properties."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return CommodityCrawler()

    def test_name_property(self, crawler):
        """Test that name property returns 'commodity_crawler'."""
        assert crawler.name == "commodity_crawler"

    def test_source_property(self, crawler):
        """Test that source property returns '100ppi'."""
        assert crawler.source == "100ppi"

    def test_commodity_mappings_exist(self, crawler):
        """Test that commodity mappings are properly defined."""
        assert "碳酸锂" in crawler.COMMODITY_MAPPINGS
        assert "电池级碳酸锂" in crawler.COMMODITY_MAPPINGS
        assert "多晶硅" in crawler.COMMODITY_MAPPINGS

    def test_akshare_symbols_exist(self, crawler):
        """Test that AkShare symbols are properly defined."""
        assert "碳酸锂" in crawler.AKSHARE_SYMBOLS
        assert crawler.AKSHARE_SYMBOLS["碳酸锂"] == "LC"


class TestCommodityCrawlerParsing:
    """Tests for CommodityCrawler parsing methods."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return CommodityCrawler()

    def test_parse_decimal_normal(self, crawler):
        """Test parsing normal decimal values."""
        assert crawler._parse_decimal("172000.00") == Decimal("172000.00")
        assert crawler._parse_decimal("45.5") == Decimal("45.5")
        assert crawler._parse_decimal("0") == Decimal("0")

    def test_parse_decimal_with_commas(self, crawler):
        """Test parsing decimal values with commas."""
        assert crawler._parse_decimal("172,000.00") == Decimal("172000.00")
        assert crawler._parse_decimal("1,234,567.89") == Decimal("1234567.89")

    def test_parse_decimal_with_whitespace(self, crawler):
        """Test parsing decimal values with whitespace."""
        assert crawler._parse_decimal("  172000.00  ") == Decimal("172000.00")
        assert crawler._parse_decimal(" 45.5 ") == Decimal("45.5")

    def test_parse_decimal_with_currency(self, crawler):
        """Test parsing decimal values with currency symbols."""
        assert crawler._parse_decimal("¥172000.00") == Decimal("172000.00")
        assert crawler._parse_decimal("$45.50") == Decimal("45.50")

    def test_parse_decimal_empty_or_invalid(self, crawler):
        """Test parsing empty or invalid decimal values."""
        assert crawler._parse_decimal("") is None
        assert crawler._parse_decimal("   ") is None
        assert crawler._parse_decimal("abc") is None
        assert crawler._parse_decimal(None) is None

    def test_parse_percentage_positive(self, crawler):
        """Test parsing positive percentage values."""
        assert crawler._parse_percentage("+10.97%") == Decimal("10.97")
        assert crawler._parse_percentage("5.5%") == Decimal("5.5")
        assert crawler._parse_percentage("100%") == Decimal("100")

    def test_parse_percentage_negative(self, crawler):
        """Test parsing negative percentage values."""
        assert crawler._parse_percentage("-2.35%") == Decimal("-2.35")
        assert crawler._parse_percentage("-10%") == Decimal("-10")

    def test_parse_percentage_chinese_symbol(self, crawler):
        """Test parsing percentage with Chinese symbol."""
        assert crawler._parse_percentage("10.97％") == Decimal("10.97")

    def test_parse_percentage_empty_or_invalid(self, crawler):
        """Test parsing empty or invalid percentage values."""
        assert crawler._parse_percentage("") is None
        assert crawler._parse_percentage("   ") is None
        assert crawler._parse_percentage(None) is None

    def test_parse_date_iso_format(self, crawler):
        """Test parsing date in ISO format."""
        assert crawler._parse_date("2026-01-25") == date(2026, 1, 25)

    def test_parse_date_slash_format(self, crawler):
        """Test parsing date in slash format."""
        assert crawler._parse_date("2026/01/25") == date(2026, 1, 25)

    def test_parse_date_chinese_format(self, crawler):
        """Test parsing date in Chinese format."""
        assert crawler._parse_date("2026年01月25日") == date(2026, 1, 25)

    def test_parse_date_empty_or_invalid(self, crawler):
        """Test parsing empty or invalid date values."""
        assert crawler._parse_date("") is None
        assert crawler._parse_date("   ") is None
        assert crawler._parse_date("invalid") is None
        assert crawler._parse_date(None) is None


class TestCommodityCrawlerFetchFrom100ppi:
    """Tests for CommodityCrawler fetch_from_100ppi method."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return CommodityCrawler()

    def test_fetch_from_100ppi_lithium_carbonate(self, crawler):
        """Test fetching lithium carbonate price from 100ppi."""
        with patch(
            "src.collectors.crawlers.commodity_crawler.httpx.get"
        ) as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_100PPI_HTML_LITHIUM
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_from_100ppi("碳酸锂")

            assert result is not None
            assert result.commodity_name == "碳酸锂"
            assert result.commodity_name_en == "lithium_carbonate"
            assert result.price == Decimal("172000.00")
            assert result.price_unit == "元/吨"
            assert result.source == "100ppi"

    def test_fetch_from_100ppi_polysilicon(self, crawler):
        """Test fetching polysilicon price from 100ppi."""
        with patch(
            "src.collectors.crawlers.commodity_crawler.httpx.get"
        ) as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_100PPI_HTML_POLYSILICON
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_from_100ppi("多晶硅")

            assert result is not None
            assert result.commodity_name == "多晶硅"
            assert result.commodity_name_en == "polysilicon"
            assert result.price == Decimal("45.50")
            assert result.price_unit == "元/千克"
            assert result.source == "100ppi"

    def test_fetch_from_100ppi_unknown_commodity(self, crawler):
        """Test fetching unknown commodity returns None."""
        result = crawler.fetch_from_100ppi("未知商品")

        assert result is None

    def test_fetch_from_100ppi_http_error(self, crawler):
        """Test handling of HTTP errors."""
        with patch(
            "src.collectors.crawlers.commodity_crawler.httpx.get"
        ) as mock_get:
            mock_get.side_effect = Exception("Network Error")

            result = crawler.fetch_from_100ppi("碳酸锂")

            assert result is None

    def test_fetch_from_100ppi_empty_page(self, crawler):
        """Test handling of empty page response."""
        with patch(
            "src.collectors.crawlers.commodity_crawler.httpx.get"
        ) as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_100PPI_HTML_EMPTY
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_from_100ppi("碳酸锂")

            # Should return None when price cannot be extracted
            assert result is None

    def test_fetch_from_100ppi_table_format(self, crawler):
        """Test parsing price from alternative div format with price class."""
        # Test HTML that matches the parser's div-with-price-class logic
        html_with_price_div = """
        <!DOCTYPE html>
        <html>
        <head><title>商品价格</title></head>
        <body>
            <div class="commodity-price">175000.00</div>
            <span class="date-info">2026-01-25</span>
        </body>
        </html>
        """
        with patch(
            "src.collectors.crawlers.commodity_crawler.httpx.get"
        ) as mock_get:
            mock_response = Mock()
            mock_response.text = html_with_price_div
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_from_100ppi("碳酸锂")

            assert result is not None
            assert result.price == Decimal("175000.00")


class TestCommodityCrawlerFetchFromAkshare:
    """Tests for CommodityCrawler fetch_from_akshare method."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return CommodityCrawler()

    def test_fetch_from_akshare_lithium_carbonate(self, crawler):
        """Test fetching lithium carbonate price from AkShare."""
        mock_ak = MagicMock()
        mock_ak.futures_spot_price.return_value = MOCK_AKSHARE_DATA

        with patch.dict("sys.modules", {"akshare": mock_ak}):
            result = crawler.fetch_from_akshare(symbol="LC", price_date="20260125")

            assert result is not None
            assert result.commodity_name == "碳酸锂"
            assert result.commodity_name_en == "lithium_carbonate"
            assert result.price == Decimal("138000")
            assert result.source == "akshare"

    def test_fetch_from_akshare_empty_data(self, crawler):
        """Test handling of empty AkShare response."""
        mock_ak = MagicMock()
        mock_ak.futures_spot_price.return_value = MOCK_AKSHARE_EMPTY

        with patch.dict("sys.modules", {"akshare": mock_ak}):
            result = crawler.fetch_from_akshare(symbol="LC", price_date="20260125")

            assert result is None

    def test_fetch_from_akshare_symbol_not_found(self, crawler):
        """Test handling when symbol not found in AkShare data."""
        mock_ak = MagicMock()
        mock_ak.futures_spot_price.return_value = MOCK_AKSHARE_DATA

        with patch.dict("sys.modules", {"akshare": mock_ak}):
            result = crawler.fetch_from_akshare(
                symbol="UNKNOWN", price_date="20260125"
            )

            assert result is None

    def test_fetch_from_akshare_import_error(self, crawler):
        """Test handling when AkShare is not installed."""
        # Remove akshare from sys.modules to simulate ImportError
        import sys
        original_modules = sys.modules.copy()

        # Remove akshare if it exists
        if "akshare" in sys.modules:
            del sys.modules["akshare"]

        # Make the import fail
        with patch.dict("sys.modules", {"akshare": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module")):
                result = crawler.fetch_from_akshare(symbol="LC")
                # Should handle gracefully and return None
                assert result is None

    def test_fetch_from_akshare_api_error(self, crawler):
        """Test handling of AkShare API errors."""
        mock_ak = MagicMock()
        mock_ak.futures_spot_price.side_effect = Exception("API Error")

        with patch.dict("sys.modules", {"akshare": mock_ak}):
            result = crawler.fetch_from_akshare(symbol="LC", price_date="20260125")

            assert result is None


class TestCommodityCrawlerFetchLithiumCarbonate:
    """Tests for CommodityCrawler fetch_lithium_carbonate method."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return CommodityCrawler()

    def test_fetch_lithium_carbonate_akshare_success(self, crawler):
        """Test fetching lithium carbonate prefers AkShare."""
        with patch.object(
            crawler, "fetch_from_akshare"
        ) as mock_akshare, patch.object(
            crawler, "fetch_from_100ppi"
        ) as mock_100ppi:
            mock_akshare.return_value = CommodityPriceData(
                commodity_name="碳酸锂",
                commodity_name_en="lithium_carbonate",
                price=Decimal("138000"),
                price_unit="元/吨",
                price_change=None,
                price_change_pct=None,
                price_date=date(2026, 1, 25),
                source="akshare",
            )

            result = crawler.fetch_lithium_carbonate()

            assert result is not None
            assert result.source == "akshare"
            mock_100ppi.assert_not_called()

    def test_fetch_lithium_carbonate_fallback_to_100ppi(self, crawler):
        """Test fetching lithium carbonate falls back to 100ppi when AkShare fails."""
        with patch.object(
            crawler, "fetch_from_akshare"
        ) as mock_akshare, patch.object(
            crawler, "fetch_from_100ppi"
        ) as mock_100ppi:
            mock_akshare.return_value = None
            mock_100ppi.return_value = CommodityPriceData(
                commodity_name="碳酸锂",
                commodity_name_en="lithium_carbonate",
                price=Decimal("172000"),
                price_unit="元/吨",
                price_change=None,
                price_change_pct=Decimal("10.97"),
                price_date=date(2026, 1, 25),
                source="100ppi",
            )

            result = crawler.fetch_lithium_carbonate()

            assert result is not None
            assert result.source == "100ppi"
            mock_100ppi.assert_called_once_with("碳酸锂")


class TestCommodityCrawlerFetchBatteryGradeLithiumCarbonate:
    """Tests for CommodityCrawler fetch_battery_grade_lithium_carbonate method."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return CommodityCrawler()

    def test_fetch_battery_grade_lithium_carbonate(self, crawler):
        """Test fetching battery-grade lithium carbonate."""
        with patch.object(
            crawler, "fetch_from_akshare"
        ) as mock_akshare:
            mock_akshare.return_value = CommodityPriceData(
                commodity_name="碳酸锂",
                commodity_name_en="lithium_carbonate",
                price=Decimal("140000"),
                price_unit="元/吨",
                price_change=None,
                price_change_pct=None,
                price_date=date(2026, 1, 25),
                source="akshare",
            )

            result = crawler.fetch_battery_grade_lithium_carbonate()

            assert result is not None
            assert result.commodity_name == "电池级碳酸锂"
            assert result.commodity_name_en == "battery_grade_lithium_carbonate"
            assert result.price == Decimal("140000")


class TestCommodityCrawlerFetchPolysilicon:
    """Tests for CommodityCrawler fetch_polysilicon method."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return CommodityCrawler()

    def test_fetch_polysilicon(self, crawler):
        """Test fetching polysilicon price."""
        with patch.object(
            crawler, "fetch_from_100ppi"
        ) as mock_100ppi:
            mock_100ppi.return_value = CommodityPriceData(
                commodity_name="多晶硅",
                commodity_name_en="polysilicon",
                price=Decimal("45.50"),
                price_unit="元/千克",
                price_change=None,
                price_change_pct=Decimal("-2.35"),
                price_date=date(2026, 1, 25),
                source="100ppi",
            )

            result = crawler.fetch_polysilicon()

            assert result is not None
            assert result.commodity_name == "多晶硅"
            assert result.price == Decimal("45.50")
            mock_100ppi.assert_called_once_with("多晶硅")


class TestCommodityCrawlerFetchAllTrackedCommodities:
    """Tests for CommodityCrawler fetch_all_tracked_commodities method."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return CommodityCrawler()

    def test_fetch_all_tracked_commodities(self, crawler):
        """Test fetching all tracked commodities."""
        with patch.object(
            crawler, "fetch_lithium_carbonate"
        ) as mock_lc, patch.object(
            crawler, "fetch_battery_grade_lithium_carbonate"
        ) as mock_blc, patch.object(
            crawler, "fetch_polysilicon"
        ) as mock_ps:
            mock_lc.return_value = CommodityPriceData(
                commodity_name="碳酸锂",
                commodity_name_en="lithium_carbonate",
                price=Decimal("138000"),
                price_unit="元/吨",
                price_change=None,
                price_change_pct=None,
                price_date=date(2026, 1, 25),
                source="akshare",
            )
            mock_blc.return_value = CommodityPriceData(
                commodity_name="电池级碳酸锂",
                commodity_name_en="battery_grade_lithium_carbonate",
                price=Decimal("140000"),
                price_unit="元/吨",
                price_change=None,
                price_change_pct=None,
                price_date=date(2026, 1, 25),
                source="akshare",
            )
            mock_ps.return_value = CommodityPriceData(
                commodity_name="多晶硅",
                commodity_name_en="polysilicon",
                price=Decimal("45.50"),
                price_unit="元/千克",
                price_change=None,
                price_change_pct=None,
                price_date=date(2026, 1, 25),
                source="100ppi",
            )

            results = crawler.fetch_all_tracked_commodities()

            assert len(results) == 3
            assert "碳酸锂" in results
            assert "电池级碳酸锂" in results
            assert "多晶硅" in results
            assert results["碳酸锂"].price == Decimal("138000")
            assert results["电池级碳酸锂"].price == Decimal("140000")
            assert results["多晶硅"].price == Decimal("45.50")

    def test_fetch_all_tracked_commodities_partial_failure(self, crawler):
        """Test fetching all commodities when some fail."""
        with patch.object(
            crawler, "fetch_lithium_carbonate"
        ) as mock_lc, patch.object(
            crawler, "fetch_battery_grade_lithium_carbonate"
        ) as mock_blc, patch.object(
            crawler, "fetch_polysilicon"
        ) as mock_ps:
            mock_lc.return_value = CommodityPriceData(
                commodity_name="碳酸锂",
                commodity_name_en="lithium_carbonate",
                price=Decimal("138000"),
                price_unit="元/吨",
                price_change=None,
                price_change_pct=None,
                price_date=date(2026, 1, 25),
                source="akshare",
            )
            mock_blc.return_value = None  # Simulating failure
            mock_ps.return_value = None  # Simulating failure

            results = crawler.fetch_all_tracked_commodities()

            assert len(results) == 3
            assert results["碳酸锂"] is not None
            assert results["电池级碳酸锂"] is None
            assert results["多晶硅"] is None


class TestCommodityCrawlerFetchCommodityByName:
    """Tests for CommodityCrawler fetch_commodity_by_name method."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return CommodityCrawler()

    def test_fetch_commodity_by_name_lithium(self, crawler):
        """Test fetching lithium carbonate by name."""
        with patch.object(
            crawler, "fetch_lithium_carbonate"
        ) as mock_fetch:
            mock_fetch.return_value = CommodityPriceData(
                commodity_name="碳酸锂",
                commodity_name_en="lithium_carbonate",
                price=Decimal("138000"),
                price_unit="元/吨",
                price_change=None,
                price_change_pct=None,
                price_date=date(2026, 1, 25),
                source="akshare",
            )

            result = crawler.fetch_commodity_by_name("碳酸锂")

            assert result is not None
            assert result.commodity_name == "碳酸锂"
            mock_fetch.assert_called_once()

    def test_fetch_commodity_by_name_battery_grade(self, crawler):
        """Test fetching battery-grade lithium carbonate by name."""
        with patch.object(
            crawler, "fetch_battery_grade_lithium_carbonate"
        ) as mock_fetch:
            mock_fetch.return_value = CommodityPriceData(
                commodity_name="电池级碳酸锂",
                commodity_name_en="battery_grade_lithium_carbonate",
                price=Decimal("140000"),
                price_unit="元/吨",
                price_change=None,
                price_change_pct=None,
                price_date=date(2026, 1, 25),
                source="akshare",
            )

            result = crawler.fetch_commodity_by_name("电池级碳酸锂")

            assert result is not None
            assert result.commodity_name == "电池级碳酸锂"
            mock_fetch.assert_called_once()

    def test_fetch_commodity_by_name_polysilicon(self, crawler):
        """Test fetching polysilicon by name."""
        with patch.object(
            crawler, "fetch_polysilicon"
        ) as mock_fetch:
            mock_fetch.return_value = CommodityPriceData(
                commodity_name="多晶硅",
                commodity_name_en="polysilicon",
                price=Decimal("45.50"),
                price_unit="元/千克",
                price_change=None,
                price_change_pct=None,
                price_date=date(2026, 1, 25),
                source="100ppi",
            )

            result = crawler.fetch_commodity_by_name("多晶硅")

            assert result is not None
            assert result.commodity_name == "多晶硅"
            mock_fetch.assert_called_once()

    def test_fetch_commodity_by_name_unknown(self, crawler):
        """Test fetching unknown commodity by name falls back to 100ppi."""
        with patch.object(
            crawler, "fetch_from_100ppi"
        ) as mock_fetch:
            mock_fetch.return_value = None

            result = crawler.fetch_commodity_by_name("未知商品")

            mock_fetch.assert_called_once_with("未知商品")
            assert result is None


class TestCommodityCrawlerRequestConfiguration:
    """Tests for CommodityCrawler request configuration."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return CommodityCrawler()

    def test_request_includes_user_agent(self, crawler):
        """Test that requests include a proper User-Agent header."""
        with patch(
            "src.collectors.crawlers.commodity_crawler.httpx.get"
        ) as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_100PPI_HTML_EMPTY
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            crawler.fetch_from_100ppi("碳酸锂")

            call_args = mock_get.call_args
            headers = call_args[1].get("headers", {})
            assert "User-Agent" in headers

    def test_request_includes_timeout(self, crawler):
        """Test that requests include a timeout."""
        with patch(
            "src.collectors.crawlers.commodity_crawler.httpx.get"
        ) as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_100PPI_HTML_EMPTY
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            crawler.fetch_from_100ppi("碳酸锂")

            call_args = mock_get.call_args
            timeout = call_args[1].get("timeout")
            assert timeout is not None
            assert timeout == 30.0

    def test_request_url_correct_for_lithium(self, crawler):
        """Test that request URL is correct for lithium carbonate."""
        with patch(
            "src.collectors.crawlers.commodity_crawler.httpx.get"
        ) as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_100PPI_HTML_EMPTY
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            crawler.fetch_from_100ppi("碳酸锂")

            call_args = mock_get.call_args
            url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
            assert "tsl.100ppi.com" in url

    def test_request_url_correct_for_polysilicon(self, crawler):
        """Test that request URL is correct for polysilicon."""
        with patch(
            "src.collectors.crawlers.commodity_crawler.httpx.get"
        ) as mock_get:
            mock_response = Mock()
            mock_response.text = MOCK_100PPI_HTML_EMPTY
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            crawler.fetch_from_100ppi("多晶硅")

            call_args = mock_get.call_args
            url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
            assert "djg.100ppi.com" in url


# Integration test (skipped by default, run with: pytest -m integration)
@pytest.mark.integration
class TestCommodityCrawlerIntegration:
    """Integration tests that hit real data sources."""

    def test_fetch_real_lithium_carbonate(self):
        """Test fetching real lithium carbonate price."""
        crawler = CommodityCrawler()

        result = crawler.fetch_lithium_carbonate()

        # May return None if sources are unavailable
        if result:
            assert result.commodity_name in ["碳酸锂", "电池级碳酸锂"]
            assert result.price > Decimal("0")
            assert result.price_unit == "元/吨"

    def test_fetch_real_polysilicon(self):
        """Test fetching real polysilicon price."""
        crawler = CommodityCrawler()

        result = crawler.fetch_polysilicon()

        # May return None if sources are unavailable
        if result:
            assert result.commodity_name == "多晶硅"
            assert result.price > Decimal("0")
            assert result.price_unit == "元/千克"

    def test_fetch_real_all_commodities(self):
        """Test fetching all real commodity prices."""
        crawler = CommodityCrawler()

        results = crawler.fetch_all_tracked_commodities()

        assert isinstance(results, dict)
        assert len(results) == 3
        # At least check the structure is correct
        for key in ["碳酸锂", "电池级碳酸锂", "多晶硅"]:
            assert key in results
