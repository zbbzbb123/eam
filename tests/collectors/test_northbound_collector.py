"""Tests for Northbound Flow Collector."""
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import patch
import pandas as pd

from src.collectors.structured.northbound_collector import (
    NorthboundCollector,
    NorthboundFlowData,
    HoldingChangeData,
)


class TestNorthboundCollectorProperties:
    """Tests for NorthboundCollector properties."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return NorthboundCollector()

    def test_name_property(self, collector):
        """Test that name property returns 'northbound_collector'."""
        assert collector.name == "northbound_collector"

    def test_source_property(self, collector):
        """Test that source property returns 'akshare'."""
        assert collector.source == "akshare"


class TestNorthboundCollectorFetchDailyNetFlow:
    """Tests for NorthboundCollector fetch_daily_net_flow method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return NorthboundCollector()

    @pytest.fixture
    def mock_net_flow_data(self):
        """Create mock net flow DataFrame matching actual API response."""
        return pd.DataFrame({
            "日期": pd.to_datetime(["2025-01-20", "2025-01-21", "2025-01-22"]),
            "当日成交净买额": [100.5, -50.2, 75.8],
            "当日余额": [520.0, 520.0, 520.0],
        })

    def test_fetch_daily_net_flow_returns_list(self, collector, mock_net_flow_data):
        """Test that fetch_daily_net_flow returns list of NorthboundFlowData."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hist_em") as mock_fn:
            mock_fn.return_value = mock_net_flow_data

            result = collector.fetch_daily_net_flow()

            assert isinstance(result, list)
            assert len(result) == 3
            assert all(isinstance(item, NorthboundFlowData) for item in result)

    def test_fetch_daily_net_flow_correct_data(self, collector, mock_net_flow_data):
        """Test that fetch_daily_net_flow parses data correctly."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hist_em") as mock_fn:
            mock_fn.return_value = mock_net_flow_data

            result = collector.fetch_daily_net_flow()

            assert result[0].trade_date == date(2025, 1, 20)
            assert result[0].net_flow == Decimal("100.5")

    def test_fetch_daily_net_flow_with_date_filter(self, collector, mock_net_flow_data):
        """Test that fetch_daily_net_flow respects date filter."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hist_em") as mock_fn:
            mock_fn.return_value = mock_net_flow_data

            result = collector.fetch_daily_net_flow(
                start_date=date(2025, 1, 21),
                end_date=date(2025, 1, 22),
            )

            assert len(result) == 2
            assert result[0].trade_date == date(2025, 1, 21)

    def test_fetch_daily_net_flow_empty_response(self, collector):
        """Test handling of empty response."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hist_em") as mock_fn:
            mock_fn.return_value = pd.DataFrame()

            result = collector.fetch_daily_net_flow()

            assert result == []

    def test_fetch_daily_net_flow_api_error(self, collector):
        """Test that API errors are handled gracefully."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hist_em") as mock_fn:
            mock_fn.side_effect = Exception("API Error")

            result = collector.fetch_daily_net_flow()

            assert result == []

    def test_fetch_daily_net_flow_calls_correct_api(self, collector):
        """Test that correct AkShare API is called."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hist_em") as mock_fn:
            mock_fn.return_value = pd.DataFrame()

            collector.fetch_daily_net_flow()

            mock_fn.assert_called_once_with(symbol="北向资金")


class TestNorthboundCollectorFetchTopHoldingChanges:
    """Tests for NorthboundCollector fetch_top_holding_changes method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return NorthboundCollector()

    @pytest.fixture
    def mock_holding_data(self):
        """Create mock holding change DataFrame."""
        return pd.DataFrame({
            "代码": ["000001", "000002", "000003", "000004", "000005",
                   "000006", "000007", "000008", "000009", "000010", "000011"],
            "名称": ["平安银行", "万科A", "国农科技", "深振业A", "世纪星源",
                   "深科技", "全新好", "神州高铁", "中国宝安", "美丽生态", "深物业A"],
            "今日持股-Loss": [100.0, 95.0, 88.0, 82.0, 76.0,
                           70.0, 65.0, 60.0, 55.0, 50.0, 45.0],
            "今日参考市值-Loss": [1000.0, 950.0, 880.0, 820.0, 760.0,
                             700.0, 650.0, 600.0, 550.0, 500.0, 450.0],
            "今日持股变化-Loss": [10.5, -8.2, 5.0, -3.5, 2.0,
                             -1.5, 1.0, -0.5, 0.3, -0.2, 0.1],
        })

    def test_fetch_top_holding_changes_returns_list(self, collector, mock_holding_data):
        """Test that fetch_top_holding_changes returns list of HoldingChangeData."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hold_stock_em") as mock_fn:
            mock_fn.return_value = mock_holding_data

            result = collector.fetch_top_holding_changes()

            assert isinstance(result, list)
            assert all(isinstance(item, HoldingChangeData) for item in result)

    def test_fetch_top_holding_changes_default_top_10(self, collector, mock_holding_data):
        """Test that fetch_top_holding_changes returns top 10 by default."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hold_stock_em") as mock_fn:
            mock_fn.return_value = mock_holding_data

            result = collector.fetch_top_holding_changes()

            assert len(result) == 10

    def test_fetch_top_holding_changes_custom_limit(self, collector, mock_holding_data):
        """Test that fetch_top_holding_changes respects custom limit."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hold_stock_em") as mock_fn:
            mock_fn.return_value = mock_holding_data

            result = collector.fetch_top_holding_changes(top_n=5)

            assert len(result) == 5

    def test_fetch_top_holding_changes_correct_data(self, collector, mock_holding_data):
        """Test that fetch_top_holding_changes parses data correctly."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hold_stock_em") as mock_fn:
            mock_fn.return_value = mock_holding_data

            result = collector.fetch_top_holding_changes(top_n=1)

            assert result[0].symbol == "000001"
            assert result[0].name == "平安银行"
            assert result[0].holding_change == Decimal("10.5")

    def test_fetch_top_holding_changes_sorted_by_change(self, collector, mock_holding_data):
        """Test that results are sorted by absolute holding change."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hold_stock_em") as mock_fn:
            mock_fn.return_value = mock_holding_data

            result = collector.fetch_top_holding_changes(top_n=3)

            # Should be sorted by absolute value of change (descending)
            abs_changes = [abs(item.holding_change) for item in result]
            assert abs_changes == sorted(abs_changes, reverse=True)

    def test_fetch_top_holding_changes_empty_response(self, collector):
        """Test handling of empty response."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hold_stock_em") as mock_fn:
            mock_fn.return_value = pd.DataFrame()

            result = collector.fetch_top_holding_changes()

            assert result == []

    def test_fetch_top_holding_changes_api_error(self, collector):
        """Test that API errors are handled gracefully."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hold_stock_em") as mock_fn:
            mock_fn.side_effect = Exception("API Error")

            result = collector.fetch_top_holding_changes()

            assert result == []

    def test_fetch_top_holding_changes_calls_correct_api(self, collector):
        """Test that correct AkShare API is called."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hold_stock_em") as mock_fn:
            mock_fn.return_value = pd.DataFrame()

            collector.fetch_top_holding_changes(market="沪股通")

            mock_fn.assert_called_once_with(market="沪股通")

    def test_fetch_top_holding_changes_different_markets(self, collector, mock_holding_data):
        """Test fetching data for different markets."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hold_stock_em") as mock_fn:
            mock_fn.return_value = mock_holding_data

            # Test 沪股通
            collector.fetch_top_holding_changes(market="沪股通")
            mock_fn.assert_called_with(market="沪股通")

            # Test 深股通
            collector.fetch_top_holding_changes(market="深股通")
            mock_fn.assert_called_with(market="深股通")


class TestNorthboundFlowData:
    """Tests for NorthboundFlowData data class."""

    def test_northbound_flow_data_creation(self):
        """Test NorthboundFlowData can be created with required fields."""
        data = NorthboundFlowData(
            trade_date=date(2025, 1, 20),
            net_flow=Decimal("100.5"),
            quota_remaining=Decimal("520.0"),
        )

        assert data.trade_date == date(2025, 1, 20)
        assert data.net_flow == Decimal("100.5")
        assert data.quota_remaining == Decimal("520.0")

    def test_northbound_flow_data_to_dict(self):
        """Test NorthboundFlowData to_dict method."""
        data = NorthboundFlowData(
            trade_date=date(2025, 1, 20),
            net_flow=Decimal("100.5"),
            quota_remaining=Decimal("520.0"),
        )

        d = data.to_dict()

        assert d["trade_date"] == date(2025, 1, 20)
        assert d["net_flow"] == Decimal("100.5")
        assert d["quota_remaining"] == Decimal("520.0")


class TestHoldingChangeData:
    """Tests for HoldingChangeData data class."""

    def test_holding_change_data_creation(self):
        """Test HoldingChangeData can be created with required fields."""
        data = HoldingChangeData(
            symbol="000001",
            name="平安银行",
            holding=Decimal("100.0"),
            market_value=Decimal("1000.0"),
            holding_change=Decimal("10.5"),
        )

        assert data.symbol == "000001"
        assert data.name == "平安银行"
        assert data.holding == Decimal("100.0")
        assert data.market_value == Decimal("1000.0")
        assert data.holding_change == Decimal("10.5")

    def test_holding_change_data_to_dict(self):
        """Test HoldingChangeData to_dict method."""
        data = HoldingChangeData(
            symbol="000001",
            name="平安银行",
            holding=Decimal("100.0"),
            market_value=Decimal("1000.0"),
            holding_change=Decimal("10.5"),
        )

        d = data.to_dict()

        assert d["symbol"] == "000001"
        assert d["name"] == "平安银行"
        assert d["holding"] == Decimal("100.0")
        assert d["market_value"] == Decimal("1000.0")
        assert d["holding_change"] == Decimal("10.5")


class TestNorthboundCollectorGetLatestFlow:
    """Tests for NorthboundCollector get_latest_flow method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return NorthboundCollector()

    @pytest.fixture
    def mock_net_flow_data(self):
        """Create mock net flow DataFrame matching actual API response."""
        return pd.DataFrame({
            "日期": pd.to_datetime(["2025-01-20", "2025-01-21", "2025-01-22"]),
            "当日成交净买额": [100.5, -50.2, 75.8],
            "当日余额": [520.0, 520.0, 520.0],
        })

    def test_get_latest_flow_returns_most_recent(self, collector, mock_net_flow_data):
        """Test that get_latest_flow returns the most recent data point."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hist_em") as mock_fn:
            mock_fn.return_value = mock_net_flow_data

            result = collector.get_latest_flow()

            assert result is not None
            assert result.trade_date == date(2025, 1, 22)
            assert result.net_flow == Decimal("75.8")

    def test_get_latest_flow_empty_response(self, collector):
        """Test get_latest_flow with empty response."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hist_em") as mock_fn:
            mock_fn.return_value = pd.DataFrame()

            result = collector.get_latest_flow()

            assert result is None

    def test_get_latest_flow_api_error(self, collector):
        """Test get_latest_flow handles API errors gracefully."""
        with patch("src.collectors.structured.northbound_collector.ak.stock_hsgt_hist_em") as mock_fn:
            mock_fn.side_effect = Exception("API Error")

            result = collector.get_latest_flow()

            assert result is None


# Integration test (skipped by default, run with: pytest -m integration)
@pytest.mark.integration
class TestNorthboundCollectorIntegration:
    """Integration tests that hit real AkShare API."""

    def test_fetch_real_daily_net_flow(self):
        """Test fetching real northbound flow data."""
        collector = NorthboundCollector()

        result = collector.fetch_daily_net_flow()

        assert isinstance(result, list)
        if result:  # API may return empty on non-trading days
            assert all(isinstance(item, NorthboundFlowData) for item in result)

    def test_fetch_real_top_holding_changes(self):
        """Test fetching real holding changes data."""
        collector = NorthboundCollector()

        result = collector.fetch_top_holding_changes()

        assert isinstance(result, list)
        if result:  # API may return empty on non-trading days
            assert all(isinstance(item, HoldingChangeData) for item in result)
            assert len(result) <= 10
