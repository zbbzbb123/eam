"""Tests for AkShare collector."""
import pytest
from datetime import date
from unittest.mock import patch
import pandas as pd

from src.collectors.structured.akshare_collector import AkShareCollector
from src.collectors.base import QuoteData


class TestAkShareCollector:
    """Tests for AkShareCollector."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return AkShareCollector()

    @pytest.fixture
    def mock_cn_data(self):
        """Create mock A-share data."""
        data = {
            "日期": pd.to_datetime(["2025-01-20", "2025-01-21", "2025-01-22"]),
            "开盘": [10.0, 10.5, 10.8],
            "最高": [10.5, 10.8, 11.0],
            "最低": [9.8, 10.2, 10.5],
            "收盘": [10.3, 10.6, 10.9],
            "成交量": [1000000, 1100000, 1200000],
        }
        return pd.DataFrame(data)

    def test_fetch_cn_quotes(self, collector, mock_cn_data):
        """Test fetching A-share quotes."""
        with patch("akshare.stock_zh_a_hist") as mock_fn:
            mock_fn.return_value = mock_cn_data

            quotes = collector.fetch_quotes(
                symbol="000001",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 22),
                market="CN",
            )

            assert len(quotes) == 3
            assert all(isinstance(q, QuoteData) for q in quotes)
            assert quotes[0].symbol == "000001"
            assert quotes[0].close == 10.3

    def test_fetch_quotes_empty_result(self, collector):
        """Test handling of empty result."""
        with patch("akshare.stock_zh_a_hist") as mock_fn:
            mock_fn.return_value = pd.DataFrame()

            quotes = collector.fetch_quotes(
                symbol="000001",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 22),
                market="CN",
            )

            assert quotes == []

    def test_fetch_hk_quotes(self, collector):
        """Test fetching HK stock quotes."""
        mock_hk_data = pd.DataFrame({
            "日期": pd.to_datetime(["2025-01-20"]),
            "开盘": [350.0],
            "最高": [360.0],
            "最低": [345.0],
            "收盘": [355.0],
            "成交量": [5000000],
        })

        with patch("akshare.stock_hk_hist") as mock_fn:
            mock_fn.return_value = mock_hk_data

            quotes = collector.fetch_quotes(
                symbol="00700",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 20),
                market="HK",
            )

            assert len(quotes) == 1
            assert quotes[0].symbol == "00700"
            assert quotes[0].close == 355.0

    def test_invalid_market_raises_error(self, collector):
        """Test that invalid market raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported market"):
            collector.fetch_quotes(
                symbol="AAPL",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 22),
                market="INVALID",
            )

    def test_fetch_quotes_raises_on_api_error(self, collector):
        """Test that API errors are propagated."""
        with patch("akshare.stock_zh_a_hist") as mock_fn:
            mock_fn.side_effect = Exception("API Error")

            with pytest.raises(Exception, match="API Error"):
                collector.fetch_quotes(
                    symbol="000001",
                    start_date=date(2025, 1, 20),
                    end_date=date(2025, 1, 22),
                    market="CN",
                )

    def test_fetch_latest_quote_returns_none_on_error(self, collector):
        """Test that fetch_latest_quote returns None on API errors."""
        with patch("akshare.stock_zh_a_hist") as mock_fn:
            mock_fn.side_effect = Exception("API Error")

            result = collector.fetch_latest_quote("000001", "CN")
            assert result is None


# Integration test (skipped by default)
@pytest.mark.integration
class TestAkShareCollectorIntegration:
    """Integration tests that hit real AkShare API."""

    def test_fetch_real_cn_quotes(self):
        """Test fetching real A-share quotes."""
        collector = AkShareCollector()

        quotes = collector.fetch_quotes(
            symbol="000001",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 10),
            market="CN",
        )

        assert isinstance(quotes, list)
