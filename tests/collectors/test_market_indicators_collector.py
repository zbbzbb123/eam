"""Tests for market indicators collector."""
import pytest
from datetime import date
from unittest.mock import patch
import pandas as pd

from src.collectors.structured.market_indicators_collector import (
    MarketIndicator,
    MarketIndicatorsCollector,
    TRACKED_INDICATORS,
)


class TestMarketIndicatorsCollector:
    """Tests for MarketIndicatorsCollector."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return MarketIndicatorsCollector()

    @pytest.fixture
    def mock_5d_data(self):
        """Create mock 5-day history data."""
        dates = pd.date_range(start="2025-01-20", periods=5, freq="B")
        data = {
            "Open": [18.0, 19.0, 20.0, 21.0, 22.0],
            "High": [19.0, 20.0, 21.0, 22.0, 23.0],
            "Low": [17.0, 18.0, 19.0, 20.0, 21.0],
            "Close": [18.5, 19.5, 20.5, 21.5, 22.5],
            "Volume": [100, 200, 300, 400, 500],
        }
        return pd.DataFrame(data, index=dates)

    def test_fetch_indicator_returns_market_indicator(self, collector, mock_5d_data):
        """Test that fetch_indicator returns a MarketIndicator."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = mock_5d_data

            result = collector.fetch_indicator("^VIX")

            assert isinstance(result, MarketIndicator)
            assert result.symbol == "^VIX"
            assert result.name == "VIX恐慌指数"
            assert result.value == 22.5
            assert result.date == date(2025, 1, 24)

    def test_fetch_indicator_calculates_change_pct(self, collector, mock_5d_data):
        """Test that change_pct is calculated from previous close."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = mock_5d_data

            result = collector.fetch_indicator("^VIX")

            # change_pct = (22.5 - 21.5) / 21.5 * 100
            expected_pct = round((22.5 - 21.5) / 21.5 * 100, 4)
            assert result.change_pct == expected_pct

    def test_fetch_indicator_empty_data(self, collector):
        """Test handling of empty result."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = pd.DataFrame()

            result = collector.fetch_indicator("^VIX")

            assert result.symbol == "^VIX"
            assert result.value is None
            assert result.change_pct is None
            assert result.date is None

    def test_fetch_indicator_single_row(self, collector):
        """Test with only one day of data (no previous close for change_pct)."""
        dates = pd.date_range(start="2025-01-24", periods=1, freq="B")
        data = {
            "Open": [22.0],
            "High": [23.0],
            "Low": [21.0],
            "Close": [22.5],
            "Volume": [500],
        }
        df = pd.DataFrame(data, index=dates)

        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = df

            result = collector.fetch_indicator("^VIX")

            assert result.value == 22.5
            assert result.change_pct is None

    def test_fetch_indicator_api_error(self, collector):
        """Test graceful handling of API errors."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.side_effect = Exception("API error")

            result = collector.fetch_indicator("^VIX")

            assert result.symbol == "^VIX"
            assert result.name == "VIX恐慌指数"
            assert result.value is None
            assert result.change_pct is None

    def test_fetch_indicator_unknown_symbol(self):
        """Test fetching a symbol not in the tracked list."""
        collector = MarketIndicatorsCollector()

        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = pd.DataFrame()

            result = collector.fetch_indicator("UNKNOWN")

            # Name falls back to symbol when not in indicators dict
            assert result.name == "UNKNOWN"

    def test_fetch_all_returns_all_indicators(self, collector, mock_5d_data):
        """Test that fetch_all returns indicators for all tracked symbols."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = mock_5d_data

            results = collector.fetch_all()

            assert len(results) == len(TRACKED_INDICATORS)
            symbols = {r.symbol for r in results}
            assert symbols == set(TRACKED_INDICATORS.keys())

    def test_fetch_all_partial_failure(self, collector, mock_5d_data):
        """Test that fetch_all handles partial failures gracefully."""
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("API error")
            return mock_5d_data

        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.side_effect = side_effect

            results = collector.fetch_all()

            # All indicators returned, even the failed one
            assert len(results) == len(TRACKED_INDICATORS)
            # One should have None values due to the error
            none_results = [r for r in results if r.value is None]
            assert len(none_results) == 1

    def test_custom_indicators(self, mock_5d_data):
        """Test collector with custom indicator mapping."""
        custom = {"CL=F": "原油期货"}
        collector = MarketIndicatorsCollector(indicators=custom)

        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = mock_5d_data

            results = collector.fetch_all()

            assert len(results) == 1
            assert results[0].symbol == "CL=F"
            assert results[0].name == "原油期货"

    def test_tracked_indicators_contains_expected_symbols(self):
        """Test that TRACKED_INDICATORS has the expected symbols."""
        assert "^VIX" in TRACKED_INDICATORS
        assert "SI=F" in TRACKED_INDICATORS
        assert "HG=F" in TRACKED_INDICATORS
        assert "GC=F" in TRACKED_INDICATORS
