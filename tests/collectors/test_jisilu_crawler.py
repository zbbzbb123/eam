"""Tests for Jisilu ETF Premium Crawler."""
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import patch, Mock

from src.collectors.crawlers.jisilu_crawler import (
    JisiluCrawler,
    ETFPremiumData,
)


# Sample JSON response for mocking (based on jisilu API format)
MOCK_JSON_RESPONSE = {
    "rows": [
        {
            "id": "510050",
            "cell": {
                "fund_id": "510050",
                "fund_nm": "50ETF",
                "price": "2.500",
                "increase_rt": "1.50%",
                "volume": "1500000000",
                "amount": "3750000000",
                "fund_nav": "2.4800",
                "nav_dt": "2026-01-25",
                "estimate_value": "2.4900",
                "discount_rt": "0.80%",
                "index_id": "000016",
                "index_nm": "上证50",
                "creation_unit": "900000",
                "purchase_fee": "0.50%",
                "redemption_fee": "0.50%",
                "manager": "华夏基金",
            },
        },
        {
            "id": "159915",
            "cell": {
                "fund_id": "159915",
                "fund_nm": "创业板ETF",
                "price": "1.200",
                "increase_rt": "-2.00%",
                "volume": "800000000",
                "amount": "960000000",
                "fund_nav": "1.1500",
                "nav_dt": "2026-01-25",
                "estimate_value": "1.1600",
                "discount_rt": "4.35%",
                "index_id": "399006",
                "index_nm": "创业板指",
                "creation_unit": "1000000",
                "purchase_fee": "0.50%",
                "redemption_fee": "0.50%",
                "manager": "易方达基金",
            },
        },
        {
            "id": "513100",
            "cell": {
                "fund_id": "513100",
                "fund_nm": "纳指ETF",
                "price": "1.800",
                "increase_rt": "3.00%",
                "volume": "500000000",
                "amount": "900000000",
                "fund_nav": "1.7000",
                "nav_dt": "2026-01-25",
                "estimate_value": "1.7100",
                "discount_rt": "5.88%",
                "index_id": "NDX100",
                "index_nm": "纳斯达克100",
                "creation_unit": "500000",
                "purchase_fee": "0.50%",
                "redemption_fee": "0.50%",
                "manager": "国泰基金",
            },
        },
        {
            "id": "159605",
            "cell": {
                "fund_id": "159605",
                "fund_nm": "中概互联ETF",
                "price": "0.850",
                "increase_rt": "-1.00%",
                "volume": "300000000",
                "amount": "255000000",
                "fund_nav": "0.9000",
                "nav_dt": "2026-01-25",
                "estimate_value": "0.8950",
                "discount_rt": "-5.56%",
                "index_id": "H30533",
                "index_nm": "中概互联",
                "creation_unit": "200000",
                "purchase_fee": "0.50%",
                "redemption_fee": "0.50%",
                "manager": "易方达基金",
            },
        },
        {
            "id": "513050",
            "cell": {
                "fund_id": "513050",
                "fund_nm": "中概互联网ETF",
                "price": "0.720",
                "increase_rt": "-0.50%",
                "volume": "200000000",
                "amount": "144000000",
                "fund_nav": "0.7800",
                "nav_dt": "2026-01-25",
                "estimate_value": "0.7750",
                "discount_rt": "-7.69%",
                "index_id": "H30533",
                "index_nm": "中概互联",
                "creation_unit": "200000",
                "purchase_fee": "0.50%",
                "redemption_fee": "0.50%",
                "manager": "华夏基金",
            },
        },
    ],
}

MOCK_EMPTY_JSON_RESPONSE = {"rows": []}


class TestETFPremiumData:
    """Tests for ETFPremiumData dataclass."""

    def test_etf_premium_data_creation(self):
        """Test ETFPremiumData can be created with required fields."""
        data = ETFPremiumData(
            fund_id="510050",
            fund_name="50ETF",
            price=Decimal("2.500"),
            net_value=Decimal("2.4800"),
            estimate_value=Decimal("2.4900"),
            premium_rate=Decimal("0.80"),
            volume=1500000000,
            turnover=Decimal("3750000000"),
            nav_date=date(2026, 1, 25),
            index_id="000016",
            index_name="上证50",
        )

        assert data.fund_id == "510050"
        assert data.fund_name == "50ETF"
        assert data.price == Decimal("2.500")
        assert data.net_value == Decimal("2.4800")
        assert data.estimate_value == Decimal("2.4900")
        assert data.premium_rate == Decimal("0.80")
        assert data.volume == 1500000000
        assert data.turnover == Decimal("3750000000")
        assert data.nav_date == date(2026, 1, 25)
        assert data.index_id == "000016"
        assert data.index_name == "上证50"

    def test_etf_premium_data_to_dict(self):
        """Test ETFPremiumData to_dict method."""
        data = ETFPremiumData(
            fund_id="510050",
            fund_name="50ETF",
            price=Decimal("2.500"),
            net_value=Decimal("2.4800"),
            estimate_value=Decimal("2.4900"),
            premium_rate=Decimal("0.80"),
            volume=1500000000,
            turnover=Decimal("3750000000"),
            nav_date=date(2026, 1, 25),
            index_id="000016",
            index_name="上证50",
        )

        d = data.to_dict()

        assert d["fund_id"] == "510050"
        assert d["fund_name"] == "50ETF"
        assert d["price"] == Decimal("2.500")
        assert d["net_value"] == Decimal("2.4800")
        assert d["premium_rate"] == Decimal("0.80")

    def test_etf_premium_data_is_premium(self):
        """Test is_premium property."""
        premium = ETFPremiumData(
            fund_id="510050",
            fund_name="50ETF",
            price=Decimal("2.500"),
            net_value=Decimal("2.4800"),
            estimate_value=Decimal("2.4900"),
            premium_rate=Decimal("0.80"),
            volume=1500000000,
            turnover=Decimal("3750000000"),
            nav_date=date(2026, 1, 25),
            index_id="000016",
            index_name="上证50",
        )

        discount = ETFPremiumData(
            fund_id="159605",
            fund_name="中概互联ETF",
            price=Decimal("0.850"),
            net_value=Decimal("0.9000"),
            estimate_value=Decimal("0.8950"),
            premium_rate=Decimal("-5.56"),
            volume=300000000,
            turnover=Decimal("255000000"),
            nav_date=date(2026, 1, 25),
            index_id="H30533",
            index_name="中概互联",
        )

        assert premium.is_premium is True
        assert discount.is_premium is False

    def test_etf_premium_data_is_discount(self):
        """Test is_discount property."""
        premium = ETFPremiumData(
            fund_id="510050",
            fund_name="50ETF",
            price=Decimal("2.500"),
            net_value=Decimal("2.4800"),
            estimate_value=Decimal("2.4900"),
            premium_rate=Decimal("0.80"),
            volume=1500000000,
            turnover=Decimal("3750000000"),
            nav_date=date(2026, 1, 25),
            index_id="000016",
            index_name="上证50",
        )

        discount = ETFPremiumData(
            fund_id="159605",
            fund_name="中概互联ETF",
            price=Decimal("0.850"),
            net_value=Decimal("0.9000"),
            estimate_value=Decimal("0.8950"),
            premium_rate=Decimal("-5.56"),
            volume=300000000,
            turnover=Decimal("255000000"),
            nav_date=date(2026, 1, 25),
            index_id="H30533",
            index_name="中概互联",
        )

        assert premium.is_discount is False
        assert discount.is_discount is True


class TestJisiluCrawlerProperties:
    """Tests for JisiluCrawler properties."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return JisiluCrawler()

    def test_name_property(self, crawler):
        """Test that name property returns 'jisilu_crawler'."""
        assert crawler.name == "jisilu_crawler"

    def test_source_property(self, crawler):
        """Test that source property returns 'jisilu'."""
        assert crawler.source == "jisilu"


class TestJisiluCrawlerFetchETFPremiumData:
    """Tests for JisiluCrawler fetch_etf_premium_data method."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return JisiluCrawler()

    def test_fetch_etf_premium_data_returns_list(self, crawler):
        """Test that fetch_etf_premium_data returns list of ETFPremiumData."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_etf_premium_data()

            assert isinstance(result, list)
            assert all(isinstance(item, ETFPremiumData) for item in result)

    def test_fetch_etf_premium_data_parses_correctly(self, crawler):
        """Test that fetch_etf_premium_data parses data correctly."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_etf_premium_data()

            assert len(result) == 5
            # Find the 50ETF entry
            etf_50 = next(item for item in result if item.fund_id == "510050")
            assert etf_50.fund_name == "50ETF"
            assert etf_50.price == Decimal("2.500")
            assert etf_50.net_value == Decimal("2.4800")
            assert etf_50.premium_rate == Decimal("0.80")

    def test_fetch_etf_premium_data_empty_response(self, crawler):
        """Test handling of empty response."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_EMPTY_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_etf_premium_data()

            assert result == []

    def test_fetch_etf_premium_data_api_error(self, crawler):
        """Test that API errors are handled gracefully."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_get.side_effect = Exception("Network Error")

            result = crawler.fetch_etf_premium_data()

            assert result == []

    def test_fetch_etf_premium_data_http_error(self, crawler):
        """Test that HTTP errors are handled gracefully."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = Exception("HTTP 403 Forbidden")
            mock_get.return_value = mock_response

            result = crawler.fetch_etf_premium_data()

            assert result == []


class TestJisiluCrawlerFilterHighPremium:
    """Tests for JisiluCrawler filter_high_premium method."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return JisiluCrawler()

    def test_filter_high_premium_returns_list(self, crawler):
        """Test that filter_high_premium returns list of ETFPremiumData."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.filter_high_premium()

            assert isinstance(result, list)
            assert all(isinstance(item, ETFPremiumData) for item in result)

    def test_filter_high_premium_default_threshold(self, crawler):
        """Test filter_high_premium with default 5% threshold."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.filter_high_premium()

            # Only 纳指ETF (5.88%) should be returned with >5% premium
            assert len(result) == 1
            assert result[0].fund_id == "513100"
            assert result[0].premium_rate == Decimal("5.88")

    def test_filter_high_premium_custom_threshold(self, crawler):
        """Test filter_high_premium with custom threshold."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # Filter with 4% threshold
            result = crawler.filter_high_premium(threshold=Decimal("4.0"))

            # Both 创业板ETF (4.35%) and 纳指ETF (5.88%) should be returned
            assert len(result) == 2
            fund_ids = {item.fund_id for item in result}
            assert "159915" in fund_ids  # 创业板ETF
            assert "513100" in fund_ids  # 纳指ETF

    def test_filter_high_premium_empty_response(self, crawler):
        """Test filter_high_premium with empty response."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_EMPTY_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.filter_high_premium()

            assert result == []


class TestJisiluCrawlerFilterHighDiscount:
    """Tests for JisiluCrawler filter_high_discount method."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return JisiluCrawler()

    def test_filter_high_discount_returns_list(self, crawler):
        """Test that filter_high_discount returns list of ETFPremiumData."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.filter_high_discount()

            assert isinstance(result, list)
            assert all(isinstance(item, ETFPremiumData) for item in result)

    def test_filter_high_discount_default_threshold(self, crawler):
        """Test filter_high_discount with default -5% threshold."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.filter_high_discount()

            # Both 中概互联ETF (-5.56%) and 中概互联网ETF (-7.69%) should be returned
            assert len(result) == 2
            fund_ids = {item.fund_id for item in result}
            assert "159605" in fund_ids  # 中概互联ETF
            assert "513050" in fund_ids  # 中概互联网ETF

    def test_filter_high_discount_custom_threshold(self, crawler):
        """Test filter_high_discount with custom threshold."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # Filter with -7% threshold
            result = crawler.filter_high_discount(threshold=Decimal("-7.0"))

            # Only 中概互联网ETF (-7.69%) should be returned
            assert len(result) == 1
            assert result[0].fund_id == "513050"
            assert result[0].premium_rate == Decimal("-7.69")

    def test_filter_high_discount_empty_response(self, crawler):
        """Test filter_high_discount with empty response."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_EMPTY_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.filter_high_discount()

            assert result == []


class TestJisiluCrawlerParsing:
    """Tests for JisiluCrawler parsing edge cases."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return JisiluCrawler()

    def test_parse_percentage_with_percent_sign(self, crawler):
        """Test that percentage values with % sign are parsed correctly."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_etf_premium_data()

            # Check that premium rates are parsed correctly
            etf_50 = next(item for item in result if item.fund_id == "510050")
            assert etf_50.premium_rate == Decimal("0.80")

    def test_parse_volume_large_numbers(self, crawler):
        """Test that large volume numbers are parsed correctly."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_etf_premium_data()

            etf_50 = next(item for item in result if item.fund_id == "510050")
            assert etf_50.volume == 1500000000
            assert etf_50.turnover == Decimal("3750000000")

    def test_parse_nav_date(self, crawler):
        """Test that nav_date is parsed correctly."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_etf_premium_data()

            etf_50 = next(item for item in result if item.fund_id == "510050")
            assert etf_50.nav_date == date(2026, 1, 25)

    def test_parse_negative_premium_rate(self, crawler):
        """Test that negative premium rates (discount) are parsed correctly."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = crawler.fetch_etf_premium_data()

            discount_etf = next(item for item in result if item.fund_id == "159605")
            assert discount_etf.premium_rate == Decimal("-5.56")
            assert discount_etf.is_discount is True

    def test_parse_missing_fields_gracefully(self, crawler):
        """Test that missing or malformed fields are handled gracefully."""
        malformed_response = {
            "rows": [
                {
                    "id": "999999",
                    "cell": {
                        "fund_id": "999999",
                        "fund_nm": "Test ETF",
                        # Missing most fields
                    },
                },
            ],
        }
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = malformed_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # Should not raise exception, may return empty list or skip invalid items
            result = crawler.fetch_etf_premium_data()
            assert isinstance(result, list)


class TestJisiluCrawlerRequestConfiguration:
    """Tests for JisiluCrawler request configuration."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return JisiluCrawler()

    def test_request_includes_user_agent(self, crawler):
        """Test that requests include a proper User-Agent header."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_EMPTY_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            crawler.fetch_etf_premium_data()

            call_args = mock_get.call_args
            headers = call_args[1].get("headers", {})
            assert "User-Agent" in headers

    def test_request_includes_timeout(self, crawler):
        """Test that requests include a timeout."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_EMPTY_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            crawler.fetch_etf_premium_data()

            call_args = mock_get.call_args
            timeout = call_args[1].get("timeout")
            assert timeout is not None

    def test_request_url_contains_timestamp(self, crawler):
        """Test that request URL contains timestamp parameter."""
        with patch("src.collectors.crawlers.jisilu_crawler.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = MOCK_EMPTY_JSON_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            crawler.fetch_etf_premium_data()

            call_args = mock_get.call_args
            url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
            # URL should contain timestamp parameter to bypass cache
            assert "___" in url or "t=" in url


# Integration test (skipped by default, run with: pytest -m integration)
@pytest.mark.integration
class TestJisiluCrawlerIntegration:
    """Integration tests that hit real Jisilu website."""

    def test_fetch_real_etf_data(self):
        """Test fetching real ETF premium data."""
        crawler = JisiluCrawler()

        result = crawler.fetch_etf_premium_data()

        assert isinstance(result, list)
        if result:
            assert all(isinstance(item, ETFPremiumData) for item in result)
            # Check first item has required fields
            first_item = result[0]
            assert first_item.fund_id
            assert first_item.fund_name

    def test_filter_real_high_premium(self):
        """Test filtering real high premium ETFs."""
        crawler = JisiluCrawler()

        result = crawler.filter_high_premium()

        assert isinstance(result, list)
        if result:
            assert all(item.premium_rate > Decimal("5") for item in result)

    def test_filter_real_high_discount(self):
        """Test filtering real high discount ETFs."""
        crawler = JisiluCrawler()

        result = crawler.filter_high_discount()

        assert isinstance(result, list)
        if result:
            assert all(item.premium_rate < Decimal("-5") for item in result)
