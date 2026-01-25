"""Tests for yfinance collector."""
import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch
import pandas as pd

from src.collectors.structured.yfinance_collector import YFinanceCollector
from src.collectors.base import QuoteData


class TestYFinanceCollector:
    """Tests for YFinanceCollector."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return YFinanceCollector()

    @pytest.fixture
    def mock_history_data(self):
        """Create mock yfinance history data."""
        dates = pd.date_range(start="2025-01-20", end="2025-01-24", freq="B")
        data = {
            "Open": [880.0, 890.0, 900.0, 910.0],
            "High": [895.0, 905.0, 915.0, 925.0],
            "Low": [875.0, 885.0, 895.0, 905.0],
            "Close": [890.0, 900.0, 910.0, 920.0],
            "Volume": [1000000, 1100000, 1200000, 1300000],
        }
        return pd.DataFrame(data, index=dates[:4])

    def test_fetch_quotes_returns_quote_data(self, collector, mock_history_data):
        """Test that fetch_quotes returns QuoteData objects."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = mock_history_data

            quotes = collector.fetch_quotes(
                symbol="NVDA",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 24),
            )

            assert len(quotes) == 4
            assert all(isinstance(q, QuoteData) for q in quotes)
            assert quotes[0].symbol == "NVDA"
            assert quotes[0].close == 890.0

    def test_fetch_quotes_empty_result(self, collector):
        """Test handling of empty result."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = pd.DataFrame()

            quotes = collector.fetch_quotes(
                symbol="INVALID",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 24),
            )

            assert quotes == []

    def test_fetch_latest_quote(self, collector, mock_history_data):
        """Test fetching latest quote."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = mock_history_data.iloc[[-1]]

            quote = collector.fetch_latest_quote("NVDA")

            assert quote is not None
            assert quote.symbol == "NVDA"
            assert quote.close == 920.0

    def test_fetch_latest_quote_none_when_empty(self, collector):
        """Test that None is returned when no data."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = pd.DataFrame()

            quote = collector.fetch_latest_quote("INVALID")

            assert quote is None

    def test_fetch_multiple_quotes(self, collector, mock_history_data):
        """Test fetching quotes for multiple symbols."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = mock_history_data

            result = collector.fetch_multiple_quotes(
                symbols=["NVDA", "VOO"],
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 24),
            )

            assert "NVDA" in result
            assert "VOO" in result
            assert len(result["NVDA"]) == 4


# Integration test (skipped by default, run with: pytest -m integration)
@pytest.mark.integration
class TestYFinanceCollectorIntegration:
    """Integration tests that hit real Yahoo Finance API."""

    def test_fetch_real_quotes(self):
        """Test fetching real quotes from Yahoo Finance."""
        collector = YFinanceCollector()
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        quotes = collector.fetch_quotes("AAPL", start_date, end_date)

        assert len(quotes) > 0
        assert all(q.symbol == "AAPL" for q in quotes)
        assert all(q.close is not None for q in quotes)
