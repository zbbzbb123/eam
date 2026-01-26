"""Tests for TuShare Pro collector."""
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

# These imports will fail initially - TDD requires test-first
from src.collectors.structured.tushare_collector import (
    TuShareCollector,
    StockValuationData,
    StockFinancialsData,
)


class TestStockValuationData:
    """Tests for StockValuationData dataclass."""

    def test_create_valuation_data_with_all_fields(self):
        """Test creating StockValuationData with all fields."""
        data = StockValuationData(
            ts_code="000001.SZ",
            trade_date=date(2025, 1, 20),
            pe=15.5,
            pe_ttm=16.2,
            pb=1.8,
            ps=2.5,
            ps_ttm=2.3,
            total_mv=Decimal("150000000000"),
            circ_mv=Decimal("120000000000"),
            turnover_rate=1.5,
            turnover_rate_f=1.2,
        )

        assert data.ts_code == "000001.SZ"
        assert data.trade_date == date(2025, 1, 20)
        assert data.pe == 15.5
        assert data.pe_ttm == 16.2
        assert data.pb == 1.8
        assert data.ps == 2.5
        assert data.ps_ttm == 2.3
        assert data.total_mv == Decimal("150000000000")
        assert data.circ_mv == Decimal("120000000000")
        assert data.turnover_rate == 1.5
        assert data.turnover_rate_f == 1.2

    def test_create_valuation_data_with_optional_fields_none(self):
        """Test creating StockValuationData with None for optional fields."""
        data = StockValuationData(
            ts_code="000001.SZ",
            trade_date=date(2025, 1, 20),
            pe=None,
            pe_ttm=None,
            pb=None,
            ps=None,
            ps_ttm=None,
            total_mv=None,
            circ_mv=None,
            turnover_rate=None,
            turnover_rate_f=None,
        )

        assert data.ts_code == "000001.SZ"
        assert data.pe is None
        assert data.pb is None

    def test_valuation_data_to_dict(self):
        """Test StockValuationData to_dict method."""
        data = StockValuationData(
            ts_code="000001.SZ",
            trade_date=date(2025, 1, 20),
            pe=15.5,
            pe_ttm=16.2,
            pb=1.8,
            ps=2.5,
            ps_ttm=2.3,
            total_mv=Decimal("150000000000"),
            circ_mv=Decimal("120000000000"),
            turnover_rate=1.5,
            turnover_rate_f=1.2,
        )

        result = data.to_dict()

        assert result["ts_code"] == "000001.SZ"
        assert result["trade_date"] == date(2025, 1, 20)
        assert result["pe"] == 15.5
        assert result["pb"] == 1.8


class TestStockFinancialsData:
    """Tests for StockFinancialsData dataclass."""

    def test_create_financials_data_with_all_fields(self):
        """Test creating StockFinancialsData with all fields."""
        data = StockFinancialsData(
            ts_code="000001.SZ",
            ann_date=date(2025, 1, 15),
            end_date=date(2024, 12, 31),
            roe=15.5,
            roe_waa=14.8,
            roa=8.2,
            roa2=7.9,
            revenue_yoy=12.5,
            netprofit_yoy=18.3,
            grossprofit_margin=35.5,
            netprofit_margin=25.2,
            fcff=Decimal("5000000000"),
            fcfe=Decimal("4500000000"),
        )

        assert data.ts_code == "000001.SZ"
        assert data.ann_date == date(2025, 1, 15)
        assert data.end_date == date(2024, 12, 31)
        assert data.roe == 15.5
        assert data.roe_waa == 14.8
        assert data.roa == 8.2
        assert data.roa2 == 7.9
        assert data.revenue_yoy == 12.5
        assert data.netprofit_yoy == 18.3
        assert data.grossprofit_margin == 35.5
        assert data.netprofit_margin == 25.2
        assert data.fcff == Decimal("5000000000")
        assert data.fcfe == Decimal("4500000000")

    def test_create_financials_data_with_optional_fields_none(self):
        """Test creating StockFinancialsData with None for optional fields."""
        data = StockFinancialsData(
            ts_code="000001.SZ",
            ann_date=date(2025, 1, 15),
            end_date=date(2024, 12, 31),
            roe=None,
            roe_waa=None,
            roa=None,
            roa2=None,
            revenue_yoy=None,
            netprofit_yoy=None,
            grossprofit_margin=None,
            netprofit_margin=None,
            fcff=None,
            fcfe=None,
        )

        assert data.ts_code == "000001.SZ"
        assert data.roe is None
        assert data.fcff is None

    def test_financials_data_to_dict(self):
        """Test StockFinancialsData to_dict method."""
        data = StockFinancialsData(
            ts_code="000001.SZ",
            ann_date=date(2025, 1, 15),
            end_date=date(2024, 12, 31),
            roe=15.5,
            roe_waa=14.8,
            roa=8.2,
            roa2=7.9,
            revenue_yoy=12.5,
            netprofit_yoy=18.3,
            grossprofit_margin=35.5,
            netprofit_margin=25.2,
            fcff=Decimal("5000000000"),
            fcfe=Decimal("4500000000"),
        )

        result = data.to_dict()

        assert result["ts_code"] == "000001.SZ"
        assert result["roe"] == 15.5
        assert result["revenue_yoy"] == 12.5


class TestTuShareCollectorProperties:
    """Tests for TuShareCollector properties."""

    @pytest.fixture
    def collector(self):
        """Create collector instance with mock token."""
        with patch("src.collectors.structured.tushare_collector.get_settings") as mock_settings:
            mock_settings.return_value.tushare_token = "test_token"
            return TuShareCollector()

    def test_name_property(self, collector):
        """Test that name property returns 'tushare_collector'."""
        assert collector.name == "tushare_collector"

    def test_source_property(self, collector):
        """Test that source property returns 'tushare'."""
        assert collector.source == "tushare"


class TestTuShareCollectorTokenValidation:
    """Tests for TuShareCollector token validation."""

    def test_collector_warns_when_token_missing(self):
        """Test that collector logs warning when token is not configured."""
        with patch("src.collectors.structured.tushare_collector.get_settings") as mock_settings:
            mock_settings.return_value.tushare_token = ""
            with patch("src.collectors.structured.tushare_collector.logger") as mock_logger:
                TuShareCollector()
                mock_logger.warning.assert_called()

    def test_collector_initializes_with_token(self):
        """Test that collector initializes successfully with token."""
        with patch("src.collectors.structured.tushare_collector.get_settings") as mock_settings:
            mock_settings.return_value.tushare_token = "valid_token"
            with patch("src.collectors.structured.tushare_collector.ts") as mock_ts:
                mock_ts.pro_api.return_value = MagicMock()
                collector = TuShareCollector()
                assert collector._token == "valid_token"


class TestTuShareCollectorFetchDailyValuation:
    """Tests for TuShareCollector fetch_daily_valuation method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance with mock token."""
        with patch("src.collectors.structured.tushare_collector.get_settings") as mock_settings:
            mock_settings.return_value.tushare_token = "test_token"
            with patch("src.collectors.structured.tushare_collector.ts") as mock_ts:
                mock_ts.pro_api.return_value = MagicMock()
                return TuShareCollector()

    @pytest.fixture
    def mock_daily_basic_df(self):
        """Create mock daily_basic DataFrame."""
        return pd.DataFrame({
            "ts_code": ["000001.SZ", "000001.SZ", "000001.SZ"],
            "trade_date": ["20250120", "20250121", "20250122"],
            "pe": [15.5, 15.8, 16.0],
            "pe_ttm": [16.2, 16.5, 16.8],
            "pb": [1.8, 1.85, 1.9],
            "ps": [2.5, 2.6, 2.7],
            "ps_ttm": [2.3, 2.4, 2.5],
            "total_mv": [150000000000.0, 152000000000.0, 154000000000.0],
            "circ_mv": [120000000000.0, 122000000000.0, 124000000000.0],
            "turnover_rate": [1.5, 1.6, 1.7],
            "turnover_rate_f": [1.2, 1.3, 1.4],
        })

    def test_fetch_daily_valuation_returns_list_of_valuation_data(
        self, collector, mock_daily_basic_df
    ):
        """Test that fetch_daily_valuation returns list of StockValuationData."""
        collector._pro.daily_basic = MagicMock(return_value=mock_daily_basic_df)

        result = collector.fetch_daily_valuation(
            ts_code="000001.SZ",
            start_date=date(2025, 1, 20),
            end_date=date(2025, 1, 22),
        )

        assert len(result) == 3
        assert all(isinstance(item, StockValuationData) for item in result)
        assert result[0].ts_code == "000001.SZ"
        assert result[0].pe == 15.5
        assert result[0].pb == 1.8

    def test_fetch_daily_valuation_handles_empty_response(self, collector):
        """Test that fetch_daily_valuation handles empty DataFrame."""
        collector._pro.daily_basic = MagicMock(return_value=pd.DataFrame())

        result = collector.fetch_daily_valuation(
            ts_code="000001.SZ",
            start_date=date(2025, 1, 20),
            end_date=date(2025, 1, 22),
        )

        assert result == []

    def test_fetch_daily_valuation_handles_none_response(self, collector):
        """Test that fetch_daily_valuation handles None response."""
        collector._pro.daily_basic = MagicMock(return_value=None)

        result = collector.fetch_daily_valuation(
            ts_code="000001.SZ",
            start_date=date(2025, 1, 20),
            end_date=date(2025, 1, 22),
        )

        assert result == []

    def test_fetch_daily_valuation_api_error_returns_empty(self, collector):
        """Test that fetch_daily_valuation returns empty list on API error."""
        collector._pro.daily_basic = MagicMock(side_effect=Exception("API Error"))

        result = collector.fetch_daily_valuation(
            ts_code="000001.SZ",
            start_date=date(2025, 1, 20),
            end_date=date(2025, 1, 22),
        )

        assert result == []

    def test_fetch_daily_valuation_handles_nan_values(self, collector):
        """Test that fetch_daily_valuation handles NaN values in DataFrame."""
        df_with_nan = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20250120"],
            "pe": [float("nan")],
            "pe_ttm": [16.2],
            "pb": [float("nan")],
            "ps": [2.5],
            "ps_ttm": [2.3],
            "total_mv": [150000000000.0],
            "circ_mv": [float("nan")],
            "turnover_rate": [1.5],
            "turnover_rate_f": [1.2],
        })
        collector._pro.daily_basic = MagicMock(return_value=df_with_nan)

        result = collector.fetch_daily_valuation(
            ts_code="000001.SZ",
            start_date=date(2025, 1, 20),
            end_date=date(2025, 1, 20),
        )

        assert len(result) == 1
        assert result[0].pe is None
        assert result[0].pb is None
        assert result[0].pe_ttm == 16.2
        assert result[0].circ_mv is None

    def test_fetch_daily_valuation_correct_api_call(self, collector):
        """Test that fetch_daily_valuation makes correct TuShare API call."""
        collector._pro.daily_basic = MagicMock(return_value=pd.DataFrame())

        collector.fetch_daily_valuation(
            ts_code="000001.SZ",
            start_date=date(2025, 1, 20),
            end_date=date(2025, 1, 22),
        )

        collector._pro.daily_basic.assert_called_once_with(
            ts_code="000001.SZ",
            start_date="20250120",
            end_date="20250122",
        )


class TestTuShareCollectorFetchFinancialIndicators:
    """Tests for TuShareCollector fetch_financial_indicators method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance with mock token."""
        with patch("src.collectors.structured.tushare_collector.get_settings") as mock_settings:
            mock_settings.return_value.tushare_token = "test_token"
            with patch("src.collectors.structured.tushare_collector.ts") as mock_ts:
                mock_ts.pro_api.return_value = MagicMock()
                return TuShareCollector()

    @pytest.fixture
    def mock_fina_indicator_df(self):
        """Create mock fina_indicator DataFrame."""
        return pd.DataFrame({
            "ts_code": ["000001.SZ", "000001.SZ"],
            "ann_date": ["20250115", "20241015"],
            "end_date": ["20241231", "20240930"],
            "roe": [15.5, 14.8],
            "roe_waa": [14.8, 14.2],
            "roa": [8.2, 7.9],
            "roa2": [7.9, 7.6],
            "q_gsprofit_yoy": [12.5, 11.2],  # revenue growth
            "q_profit_yoy": [18.3, 16.5],  # net profit growth
            "grossprofit_margin": [35.5, 34.8],
            "netprofit_margin": [25.2, 24.5],
            "fcff": [5000000000.0, 4800000000.0],
            "fcfe": [4500000000.0, 4300000000.0],
        })

    def test_fetch_financial_indicators_returns_list_of_financials_data(
        self, collector, mock_fina_indicator_df
    ):
        """Test that fetch_financial_indicators returns list of StockFinancialsData."""
        collector._pro.fina_indicator = MagicMock(return_value=mock_fina_indicator_df)

        result = collector.fetch_financial_indicators(ts_code="000001.SZ")

        assert len(result) == 2
        assert all(isinstance(item, StockFinancialsData) for item in result)
        assert result[0].ts_code == "000001.SZ"
        assert result[0].roe == 15.5
        assert result[0].roa == 8.2

    def test_fetch_financial_indicators_handles_empty_response(self, collector):
        """Test that fetch_financial_indicators handles empty DataFrame."""
        collector._pro.fina_indicator = MagicMock(return_value=pd.DataFrame())

        result = collector.fetch_financial_indicators(ts_code="000001.SZ")

        assert result == []

    def test_fetch_financial_indicators_api_error_returns_empty(self, collector):
        """Test that fetch_financial_indicators returns empty list on API error."""
        collector._pro.fina_indicator = MagicMock(side_effect=Exception("API Error"))

        result = collector.fetch_financial_indicators(ts_code="000001.SZ")

        assert result == []

    def test_fetch_financial_indicators_handles_nan_values(self, collector):
        """Test that fetch_financial_indicators handles NaN values in DataFrame."""
        df_with_nan = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "ann_date": ["20250115"],
            "end_date": ["20241231"],
            "roe": [float("nan")],
            "roe_waa": [14.8],
            "roa": [float("nan")],
            "roa2": [7.9],
            "q_gsprofit_yoy": [12.5],
            "q_profit_yoy": [float("nan")],
            "grossprofit_margin": [35.5],
            "netprofit_margin": [25.2],
            "fcff": [float("nan")],
            "fcfe": [4500000000.0],
        })
        collector._pro.fina_indicator = MagicMock(return_value=df_with_nan)

        result = collector.fetch_financial_indicators(ts_code="000001.SZ")

        assert len(result) == 1
        assert result[0].roe is None
        assert result[0].roa is None
        assert result[0].roe_waa == 14.8
        assert result[0].fcff is None

    def test_fetch_financial_indicators_correct_api_call(self, collector):
        """Test that fetch_financial_indicators makes correct TuShare API call."""
        collector._pro.fina_indicator = MagicMock(return_value=pd.DataFrame())

        collector.fetch_financial_indicators(ts_code="000001.SZ")

        collector._pro.fina_indicator.assert_called_once()
        call_kwargs = collector._pro.fina_indicator.call_args[1]
        assert call_kwargs["ts_code"] == "000001.SZ"


class TestTuShareCollectorCalculatePercentile:
    """Tests for TuShareCollector calculate_percentile method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance with mock token."""
        with patch("src.collectors.structured.tushare_collector.get_settings") as mock_settings:
            mock_settings.return_value.tushare_token = "test_token"
            with patch("src.collectors.structured.tushare_collector.ts") as mock_ts:
                mock_ts.pro_api.return_value = MagicMock()
                return TuShareCollector()

    @pytest.fixture
    def mock_historical_valuation_df(self):
        """Create mock historical valuation DataFrame for percentile calculation."""
        # Create 100 days of historical data with varying PE/PB
        import numpy as np
        np.random.seed(42)

        pe_values = np.random.uniform(8.0, 25.0, 100)
        pb_values = np.random.uniform(0.8, 3.0, 100)

        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        trade_dates = [d.strftime("%Y%m%d") for d in dates]

        return pd.DataFrame({
            "ts_code": ["000001.SZ"] * 100,
            "trade_date": trade_dates,
            "pe": pe_values,
            "pe_ttm": pe_values * 1.02,
            "pb": pb_values,
            "ps": np.random.uniform(1.5, 4.0, 100),
            "ps_ttm": np.random.uniform(1.4, 3.8, 100),
            "total_mv": np.random.uniform(100e9, 200e9, 100),
            "circ_mv": np.random.uniform(80e9, 160e9, 100),
            "turnover_rate": np.random.uniform(0.5, 3.0, 100),
            "turnover_rate_f": np.random.uniform(0.4, 2.5, 100),
        })

    def test_calculate_pe_percentile_returns_valid_value(
        self, collector, mock_historical_valuation_df
    ):
        """Test that calculate_percentile returns valid percentile for PE."""
        collector._pro.daily_basic = MagicMock(return_value=mock_historical_valuation_df)

        result = collector.calculate_percentile(
            ts_code="000001.SZ",
            metric="pe",
            current_value=15.0,
            lookback_days=100,
        )

        assert result is not None
        assert 0.0 <= result <= 100.0

    def test_calculate_pb_percentile_returns_valid_value(
        self, collector, mock_historical_valuation_df
    ):
        """Test that calculate_percentile returns valid percentile for PB."""
        collector._pro.daily_basic = MagicMock(return_value=mock_historical_valuation_df)

        result = collector.calculate_percentile(
            ts_code="000001.SZ",
            metric="pb",
            current_value=1.5,
            lookback_days=100,
        )

        assert result is not None
        assert 0.0 <= result <= 100.0

    def test_calculate_percentile_low_value(self, collector, mock_historical_valuation_df):
        """Test that very low value results in low percentile."""
        collector._pro.daily_basic = MagicMock(return_value=mock_historical_valuation_df)

        result = collector.calculate_percentile(
            ts_code="000001.SZ",
            metric="pe",
            current_value=5.0,  # Very low PE
            lookback_days=100,
        )

        assert result is not None
        assert result < 20.0  # Should be in the low percentile range

    def test_calculate_percentile_high_value(self, collector, mock_historical_valuation_df):
        """Test that very high value results in high percentile."""
        collector._pro.daily_basic = MagicMock(return_value=mock_historical_valuation_df)

        result = collector.calculate_percentile(
            ts_code="000001.SZ",
            metric="pe",
            current_value=30.0,  # Very high PE
            lookback_days=100,
        )

        assert result is not None
        assert result > 80.0  # Should be in the high percentile range

    def test_calculate_percentile_handles_empty_historical_data(self, collector):
        """Test that calculate_percentile returns None when no historical data."""
        collector._pro.daily_basic = MagicMock(return_value=pd.DataFrame())

        result = collector.calculate_percentile(
            ts_code="000001.SZ",
            metric="pe",
            current_value=15.0,
            lookback_days=100,
        )

        assert result is None

    def test_calculate_percentile_handles_api_error(self, collector):
        """Test that calculate_percentile returns None on API error."""
        collector._pro.daily_basic = MagicMock(side_effect=Exception("API Error"))

        result = collector.calculate_percentile(
            ts_code="000001.SZ",
            metric="pe",
            current_value=15.0,
            lookback_days=100,
        )

        assert result is None

    def test_calculate_percentile_invalid_metric(self, collector, mock_historical_valuation_df):
        """Test that calculate_percentile handles invalid metric gracefully."""
        collector._pro.daily_basic = MagicMock(return_value=mock_historical_valuation_df)

        result = collector.calculate_percentile(
            ts_code="000001.SZ",
            metric="invalid_metric",
            current_value=15.0,
            lookback_days=100,
        )

        assert result is None


class TestTuShareCollectorGetValuationWithPercentile:
    """Tests for TuShareCollector get_valuation_with_percentile method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance with mock token."""
        with patch("src.collectors.structured.tushare_collector.get_settings") as mock_settings:
            mock_settings.return_value.tushare_token = "test_token"
            with patch("src.collectors.structured.tushare_collector.ts") as mock_ts:
                mock_ts.pro_api.return_value = MagicMock()
                return TuShareCollector()

    @pytest.fixture
    def mock_latest_valuation_df(self):
        """Create mock latest valuation DataFrame."""
        return pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20250122"],
            "pe": [16.0],
            "pe_ttm": [16.8],
            "pb": [1.9],
            "ps": [2.7],
            "ps_ttm": [2.5],
            "total_mv": [154000000000.0],
            "circ_mv": [124000000000.0],
            "turnover_rate": [1.7],
            "turnover_rate_f": [1.4],
        })

    @pytest.fixture
    def mock_historical_valuation_df(self):
        """Create mock historical valuation DataFrame."""
        import numpy as np
        np.random.seed(42)

        pe_values = np.random.uniform(8.0, 25.0, 100)
        pb_values = np.random.uniform(0.8, 3.0, 100)

        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        trade_dates = [d.strftime("%Y%m%d") for d in dates]

        return pd.DataFrame({
            "ts_code": ["000001.SZ"] * 100,
            "trade_date": trade_dates,
            "pe": pe_values,
            "pe_ttm": pe_values * 1.02,
            "pb": pb_values,
            "ps": np.random.uniform(1.5, 4.0, 100),
            "ps_ttm": np.random.uniform(1.4, 3.8, 100),
            "total_mv": np.random.uniform(100e9, 200e9, 100),
            "circ_mv": np.random.uniform(80e9, 160e9, 100),
            "turnover_rate": np.random.uniform(0.5, 3.0, 100),
            "turnover_rate_f": np.random.uniform(0.4, 2.5, 100),
        })

    def test_get_valuation_with_percentile_returns_dict(
        self, collector, mock_latest_valuation_df, mock_historical_valuation_df
    ):
        """Test that get_valuation_with_percentile returns dict with valuation and percentiles."""
        # First call returns latest valuation, second call returns historical data
        collector._pro.daily_basic = MagicMock(
            side_effect=[mock_latest_valuation_df, mock_historical_valuation_df]
        )

        result = collector.get_valuation_with_percentile(ts_code="000001.SZ")

        assert result is not None
        assert "valuation" in result
        assert "pe_percentile" in result
        assert "pb_percentile" in result
        assert isinstance(result["valuation"], StockValuationData)

    def test_get_valuation_with_percentile_returns_none_when_no_data(self, collector):
        """Test that get_valuation_with_percentile returns None when no current data."""
        collector._pro.daily_basic = MagicMock(return_value=pd.DataFrame())

        result = collector.get_valuation_with_percentile(ts_code="000001.SZ")

        assert result is None


class TestTuShareCollectorMissingToken:
    """Tests for TuShareCollector behavior with missing token."""

    def test_fetch_daily_valuation_returns_empty_without_token(self):
        """Test that fetch_daily_valuation returns empty list when token is missing."""
        with patch("src.collectors.structured.tushare_collector.get_settings") as mock_settings:
            mock_settings.return_value.tushare_token = ""
            collector = TuShareCollector()

            result = collector.fetch_daily_valuation(
                ts_code="000001.SZ",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 22),
            )

            assert result == []

    def test_fetch_financial_indicators_returns_empty_without_token(self):
        """Test that fetch_financial_indicators returns empty list when token is missing."""
        with patch("src.collectors.structured.tushare_collector.get_settings") as mock_settings:
            mock_settings.return_value.tushare_token = ""
            collector = TuShareCollector()

            result = collector.fetch_financial_indicators(ts_code="000001.SZ")

            assert result == []


# Integration test (skipped by default, run with: pytest -m integration)
@pytest.mark.integration
class TestTuShareCollectorIntegration:
    """Integration tests that hit real TuShare API."""

    def test_fetch_real_daily_valuation(self):
        """Test fetching real daily valuation data from TuShare."""
        from src.config import get_settings

        settings = get_settings()
        if not settings.tushare_token:
            pytest.skip("TUSHARE_TOKEN not configured")

        collector = TuShareCollector()
        result = collector.fetch_daily_valuation(
            ts_code="000001.SZ",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 20),
        )

        assert isinstance(result, list)

    def test_fetch_real_financial_indicators(self):
        """Test fetching real financial indicators from TuShare."""
        from src.config import get_settings

        settings = get_settings()
        if not settings.tushare_token:
            pytest.skip("TUSHARE_TOKEN not configured")

        collector = TuShareCollector()
        result = collector.fetch_financial_indicators(ts_code="000001.SZ")

        assert isinstance(result, list)
