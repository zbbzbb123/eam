"""Tests for fundamentals collector."""
import pytest
from unittest.mock import Mock, patch, MagicMock

import pandas as pd

from src.collectors.structured.fundamentals_collector import (
    FundamentalsCollector,
    FundamentalData,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def collector():
    """Create collector instance with mocked settings and TuShare."""
    with patch(
        "src.collectors.structured.fundamentals_collector.get_settings"
    ) as mock_settings, patch(
        "src.collectors.structured.fundamentals_collector.ts"
    ) as mock_ts:
        mock_settings.return_value.tushare_token = "test_token"
        mock_ts.pro_api.return_value = MagicMock()
        c = FundamentalsCollector()
        # Expose mock pro api for per-test customization
        c._mock_pro = mock_ts.pro_api.return_value
        return c


@pytest.fixture
def collector_no_tushare():
    """Create collector with no TuShare token."""
    with patch(
        "src.collectors.structured.fundamentals_collector.get_settings"
    ) as mock_settings, patch(
        "src.collectors.structured.fundamentals_collector.ts"
    ):
        mock_settings.return_value.tushare_token = ""
        return FundamentalsCollector()


# ---------------------------------------------------------------------------
# FundamentalData dataclass
# ---------------------------------------------------------------------------

class TestFundamentalData:
    """Tests for FundamentalData dataclass."""

    def test_creation_with_all_fields(self):
        fd = FundamentalData(
            symbol="AAPL",
            market="US",
            name="Apple Inc.",
            market_cap=3_000_000_000_000.0,
            pe_ratio=28.5,
            pb_ratio=45.2,
            revenue=383_000_000_000.0,
            net_income=97_000_000_000.0,
            revenue_growth=0.08,
            profit_margin=0.253,
            analyst_rating="buy",
            target_price=250.0,
        )
        assert fd.symbol == "AAPL"
        assert fd.market == "US"
        assert fd.analyst_rating == "buy"

    def test_creation_minimal(self):
        fd = FundamentalData(symbol="600519", market="CN")
        assert fd.name is None
        assert fd.market_cap is None
        assert fd.analyst_rating is None

    def test_to_dict(self):
        fd = FundamentalData(symbol="AAPL", market="US", pe_ratio=28.5)
        d = fd.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["pe_ratio"] == 28.5
        assert d["name"] is None


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class TestFundamentalsCollectorProperties:

    def test_name(self, collector):
        assert collector.name == "fundamentals_collector"

    def test_source(self, collector):
        assert collector.source == "fundamentals"


# ---------------------------------------------------------------------------
# Symbol conversion helpers
# ---------------------------------------------------------------------------

class TestSymbolConversion:

    def test_convert_hk_symbol_standard(self):
        assert FundamentalsCollector._convert_hk_symbol("01810") == "1810.HK"

    def test_convert_hk_symbol_leading_zeros(self):
        assert FundamentalsCollector._convert_hk_symbol("00700") == "700.HK"

    def test_convert_hk_symbol_no_leading_zeros(self):
        assert FundamentalsCollector._convert_hk_symbol("9988") == "9988.HK"

    def test_convert_cn_symbol_sh_6xx(self):
        assert FundamentalsCollector._convert_cn_symbol("600519") == "600519.SH"

    def test_convert_cn_symbol_sh_5xx(self):
        assert FundamentalsCollector._convert_cn_symbol("512480") == "512480.SH"

    def test_convert_cn_symbol_sz(self):
        assert FundamentalsCollector._convert_cn_symbol("159682") == "159682.SZ"

    def test_convert_cn_symbol_sz_0xx(self):
        assert FundamentalsCollector._convert_cn_symbol("000001") == "000001.SZ"

    def test_convert_cn_symbol_sz_3xx(self):
        assert FundamentalsCollector._convert_cn_symbol("300750") == "300750.SZ"


# ---------------------------------------------------------------------------
# _safe_float
# ---------------------------------------------------------------------------

class TestSafeFloat:

    def test_none(self):
        assert FundamentalsCollector._safe_float(None) is None

    def test_nan(self):
        assert FundamentalsCollector._safe_float(float("nan")) is None

    def test_valid_int(self):
        assert FundamentalsCollector._safe_float(42) == 42.0

    def test_valid_float(self):
        assert FundamentalsCollector._safe_float(3.14) == 3.14

    def test_invalid_string(self):
        assert FundamentalsCollector._safe_float("not_a_number") is None

    def test_numeric_string(self):
        assert FundamentalsCollector._safe_float("28.5") == 28.5


# ---------------------------------------------------------------------------
# US / HK fundamentals (yfinance)
# ---------------------------------------------------------------------------

class TestFetchUSFundamentals:

    MOCK_YF_INFO = {
        "shortName": "Apple Inc.",
        "marketCap": 3_000_000_000_000,
        "trailingPE": 28.5,
        "priceToBook": 45.2,
        "totalRevenue": 383_000_000_000,
        "netIncomeToCommon": 97_000_000_000,
        "revenueGrowth": 0.08,
        "profitMargins": 0.253,
        "recommendationKey": "buy",
        "targetMeanPrice": 250.0,
    }

    @patch("src.collectors.structured.fundamentals_collector.yfinance")
    def test_fetch_us_stock(self, mock_yf, collector):
        mock_ticker = MagicMock()
        mock_ticker.info = self.MOCK_YF_INFO
        mock_yf.Ticker.return_value = mock_ticker

        result = collector.fetch_fundamentals("AAPL", "US")

        mock_yf.Ticker.assert_called_once_with("AAPL")
        assert result is not None
        assert result.symbol == "AAPL"
        assert result.market == "US"
        assert result.name == "Apple Inc."
        assert result.market_cap == 3_000_000_000_000
        assert result.pe_ratio == 28.5
        assert result.pb_ratio == 45.2
        assert result.revenue == 383_000_000_000
        assert result.net_income == 97_000_000_000
        assert result.revenue_growth == 0.08
        assert result.profit_margin == 0.253
        assert result.analyst_rating == "buy"
        assert result.target_price == 250.0

    @patch("src.collectors.structured.fundamentals_collector.yfinance")
    def test_fetch_hk_stock_symbol_conversion(self, mock_yf, collector):
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "shortName": "Xiaomi Corp",
            "marketCap": 500_000_000_000,
            "trailingPE": 20.0,
            "priceToBook": 3.5,
        }
        mock_yf.Ticker.return_value = mock_ticker

        result = collector.fetch_fundamentals("01810", "HK")

        mock_yf.Ticker.assert_called_once_with("1810.HK")
        assert result is not None
        assert result.symbol == "01810"
        assert result.market == "HK"
        assert result.name == "Xiaomi Corp"
        # HK stocks should not have analyst_rating / target_price
        assert result.analyst_rating is None
        assert result.target_price is None

    @patch("src.collectors.structured.fundamentals_collector.yfinance")
    def test_fetch_us_stock_empty_info(self, mock_yf, collector):
        mock_ticker = MagicMock()
        mock_ticker.info = {}
        mock_yf.Ticker.return_value = mock_ticker

        result = collector.fetch_fundamentals("FAKE", "US")
        assert result is None

    @patch("src.collectors.structured.fundamentals_collector.yfinance")
    def test_fetch_us_stock_exception(self, mock_yf, collector):
        mock_yf.Ticker.side_effect = Exception("network error")

        result = collector.fetch_fundamentals("AAPL", "US")
        assert result is None


# ---------------------------------------------------------------------------
# CN fundamentals (tushare)
# ---------------------------------------------------------------------------

class TestFetchCNFundamentals:

    def _make_daily_basic_df(self):
        return pd.DataFrame([{
            "ts_code": "600519.SH",
            "trade_date": "20250130",
            "pe": 30.5,
            "pb": 8.2,
            "total_mv": 2_100_000.0,
        }])

    def _make_fina_indicator_df(self):
        return pd.DataFrame([{
            "ts_code": "600519.SH",
            "ann_date": "20250120",
            "end_date": "20241231",
            "q_gsprofit_yoy": 15.3,
            "netprofit_margin": 48.5,
        }])

    def test_fetch_cn_stock(self, collector):
        collector._pro.daily_basic.return_value = self._make_daily_basic_df()
        collector._pro.fina_indicator.return_value = self._make_fina_indicator_df()

        result = collector.fetch_fundamentals("600519", "CN")

        collector._pro.daily_basic.assert_called_once_with(ts_code="600519.SH", limit=1)
        collector._pro.fina_indicator.assert_called_once_with(ts_code="600519.SH", limit=1)

        assert result is not None
        assert result.symbol == "600519"
        assert result.market == "CN"
        assert result.pe_ratio == 30.5
        assert result.pb_ratio == 8.2
        assert result.market_cap == 2_100_000.0
        assert result.revenue_growth == 15.3
        assert result.profit_margin == 48.5
        # CN stocks should never have analyst fields
        assert result.analyst_rating is None
        assert result.target_price is None

    def test_fetch_cn_stock_sz_symbol(self, collector):
        collector._pro.daily_basic.return_value = pd.DataFrame([{
            "ts_code": "159682.SZ",
            "trade_date": "20250130",
            "pe": 12.0,
            "pb": 1.5,
            "total_mv": 50_000.0,
        }])
        collector._pro.fina_indicator.return_value = pd.DataFrame()

        result = collector.fetch_fundamentals("159682", "CN")

        collector._pro.daily_basic.assert_called_once_with(ts_code="159682.SZ", limit=1)
        assert result is not None
        assert result.pe_ratio == 12.0
        # No fina data -> growth/margin should be None
        assert result.revenue_growth is None
        assert result.profit_margin is None

    def test_fetch_cn_stock_no_daily_basic(self, collector):
        collector._pro.daily_basic.return_value = pd.DataFrame()

        result = collector.fetch_fundamentals("600519", "CN")
        assert result is None

    def test_fetch_cn_stock_exception(self, collector):
        collector._pro.daily_basic.side_effect = Exception("tushare error")

        result = collector.fetch_fundamentals("600519", "CN")
        assert result is None

    def test_fetch_cn_no_tushare(self, collector_no_tushare):
        result = collector_no_tushare.fetch_fundamentals("600519", "CN")
        assert result is None


# ---------------------------------------------------------------------------
# Unsupported market
# ---------------------------------------------------------------------------

class TestUnsupportedMarket:

    def test_unsupported_market(self, collector):
        result = collector.fetch_fundamentals("AAPL", "JP")
        assert result is None


# ---------------------------------------------------------------------------
# fetch_all_holdings_fundamentals
# ---------------------------------------------------------------------------

class TestFetchAllHoldingsFundamentals:

    @patch("src.collectors.structured.fundamentals_collector.yfinance")
    def test_fetch_multiple_holdings(self, mock_yf, collector):
        # Setup yfinance mock
        mock_ticker_us = MagicMock()
        mock_ticker_us.info = {
            "shortName": "Apple",
            "marketCap": 3_000_000_000_000,
            "trailingPE": 28.5,
        }
        mock_ticker_hk = MagicMock()
        mock_ticker_hk.info = {
            "shortName": "Xiaomi",
            "marketCap": 500_000_000_000,
        }
        mock_yf.Ticker.side_effect = [mock_ticker_us, mock_ticker_hk]

        # Setup tushare mock
        collector._pro.daily_basic.return_value = pd.DataFrame([{
            "ts_code": "600519.SH",
            "pe": 30.5,
            "pb": 8.2,
            "total_mv": 2_100_000.0,
        }])
        collector._pro.fina_indicator.return_value = pd.DataFrame()

        holdings = [("AAPL", "US"), ("01810", "HK"), ("600519", "CN")]
        results = collector.fetch_all_holdings_fundamentals(holdings)

        assert len(results) == 3
        assert results[0].symbol == "AAPL"
        assert results[0].market == "US"
        assert results[1].symbol == "01810"
        assert results[1].market == "HK"
        assert results[2].symbol == "600519"
        assert results[2].market == "CN"

    @patch("src.collectors.structured.fundamentals_collector.yfinance")
    def test_partial_failure(self, mock_yf, collector):
        """One stock fails, others should still succeed."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"shortName": "Apple", "marketCap": 3e12}
        mock_yf.Ticker.side_effect = [mock_ticker, Exception("boom")]

        holdings = [("AAPL", "US"), ("BAD", "US")]
        results = collector.fetch_all_holdings_fundamentals(holdings)

        assert len(results) == 2
        assert results[0] is not None
        assert results[0].symbol == "AAPL"
        assert results[1] is None

    def test_empty_holdings(self, collector):
        results = collector.fetch_all_holdings_fundamentals([])
        assert results == []
