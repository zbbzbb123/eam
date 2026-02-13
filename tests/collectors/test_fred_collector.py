"""Tests for FRED collector."""
import pytest
from datetime import date
from unittest.mock import Mock, patch, AsyncMock
from decimal import Decimal

import httpx

from src.collectors.structured.fred_collector import FREDCollector, MacroDataPoint, YieldSpread


class TestFREDCollectorProperties:
    """Tests for FREDCollector properties."""

    @pytest.fixture
    def collector(self):
        """Create collector instance with mock API key."""
        with patch("src.collectors.structured.fred_collector.get_settings") as mock_settings:
            mock_settings.return_value.fred_api_key = "test_api_key"
            return FREDCollector()

    def test_name_property(self, collector):
        """Test that name property returns 'fred_collector'."""
        assert collector.name == "fred_collector"

    def test_source_property(self, collector):
        """Test that source property returns 'fred'."""
        assert collector.source == "fred"

    def test_configured_series(self, collector):
        """Test that configured series contains expected data points."""
        expected_series = ["DFII10", "CPIAUCSL", "GDP", "UNRATE", "FEDFUNDS", "DGS2", "DGS10"]
        assert all(series in collector.configured_series for series in expected_series)


class TestFREDCollectorFetchSeries:
    """Tests for FREDCollector fetch_series method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance with mock API key."""
        with patch("src.collectors.structured.fred_collector.get_settings") as mock_settings:
            mock_settings.return_value.fred_api_key = "test_api_key"
            return FREDCollector()

    @pytest.fixture
    def mock_fred_response(self):
        """Create mock FRED API response."""
        return {
            "observations": [
                {"date": "2025-01-20", "value": "2.35"},
                {"date": "2025-01-21", "value": "2.40"},
                {"date": "2025-01-22", "value": "2.38"},
            ]
        }

    @pytest.mark.asyncio
    async def test_fetch_series_returns_data_points(self, collector, mock_fred_response):
        """Test that fetch_series returns MacroDataPoint objects."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_fred_response
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            data_points = await collector.fetch_series(
                series_id="DFII10",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 22),
            )

            assert len(data_points) == 3
            assert all(isinstance(dp, MacroDataPoint) for dp in data_points)
            assert data_points[0].series_id == "DFII10"
            assert data_points[0].date == date(2025, 1, 20)
            assert data_points[0].value == Decimal("2.35")

    @pytest.mark.asyncio
    async def test_fetch_series_handles_missing_values(self, collector):
        """Test that fetch_series skips observations with '.' value."""
        mock_response_data = {
            "observations": [
                {"date": "2025-01-20", "value": "2.35"},
                {"date": "2025-01-21", "value": "."},  # Missing value
                {"date": "2025-01-22", "value": "2.38"},
            ]
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            data_points = await collector.fetch_series(
                series_id="DFII10",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 22),
            )

            assert len(data_points) == 2
            assert all(dp.value != "." for dp in data_points)

    @pytest.mark.asyncio
    async def test_fetch_series_empty_response(self, collector):
        """Test handling of empty response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"observations": []}
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            data_points = await collector.fetch_series(
                series_id="DFII10",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 22),
            )

            assert data_points == []

    @pytest.mark.asyncio
    async def test_fetch_series_api_error(self, collector):
        """Test that fetch_series handles API errors gracefully."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "API error",
                    request=Mock(),
                    response=Mock(status_code=500),
                )
            )

            data_points = await collector.fetch_series(
                series_id="DFII10",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 22),
            )

            assert data_points == []

    @pytest.mark.asyncio
    async def test_fetch_series_network_error(self, collector):
        """Test that fetch_series handles network errors gracefully."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(
                side_effect=httpx.RequestError("Network error")
            )

            data_points = await collector.fetch_series(
                series_id="DFII10",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 22),
            )

            assert data_points == []

    @pytest.mark.asyncio
    async def test_fetch_series_correct_api_call(self, collector):
        """Test that fetch_series makes correct API call."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"observations": []}
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            await collector.fetch_series(
                series_id="DFII10",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 22),
            )

            mock_client.return_value.get.assert_called_once()
            call_args = mock_client.return_value.get.call_args
            assert "https://api.stlouisfed.org/fred/series/observations" in str(call_args)


class TestFREDCollectorFetchAllSeries:
    """Tests for FREDCollector fetch_all_series method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance with mock API key."""
        with patch("src.collectors.structured.fred_collector.get_settings") as mock_settings:
            mock_settings.return_value.fred_api_key = "test_api_key"
            return FREDCollector()

    @pytest.mark.asyncio
    async def test_fetch_all_series_returns_dict(self, collector):
        """Test that fetch_all_series returns dictionary mapping series to data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "observations": [
                {"date": "2025-01-20", "value": "2.35"},
            ]
        }
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            result = await collector.fetch_all_series(
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 22),
            )

            assert isinstance(result, dict)
            # Should have entries for all configured series
            for series_id in collector.configured_series:
                assert series_id in result

    @pytest.mark.asyncio
    async def test_fetch_all_series_with_specific_series(self, collector):
        """Test fetch_all_series with specific series list."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "observations": [
                {"date": "2025-01-20", "value": "2.35"},
            ]
        }
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            series_to_fetch = ["DFII10", "UNRATE"]
            result = await collector.fetch_all_series(
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 22),
                series_ids=series_to_fetch,
            )

            assert len(result) == 2
            assert "DFII10" in result
            assert "UNRATE" in result
            assert "CPIAUCSL" not in result


class TestFREDCollectorLatestValue:
    """Tests for FREDCollector fetch_latest_value method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance with mock API key."""
        with patch("src.collectors.structured.fred_collector.get_settings") as mock_settings:
            mock_settings.return_value.fred_api_key = "test_api_key"
            return FREDCollector()

    @pytest.mark.asyncio
    async def test_fetch_latest_value_returns_single_point(self, collector):
        """Test that fetch_latest_value returns most recent data point."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "observations": [
                {"date": "2025-01-22", "value": "2.38"},
            ]
        }
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            data_point = await collector.fetch_latest_value("DFII10")

            assert data_point is not None
            assert isinstance(data_point, MacroDataPoint)
            assert data_point.series_id == "DFII10"

    @pytest.mark.asyncio
    async def test_fetch_latest_value_returns_none_on_error(self, collector):
        """Test that fetch_latest_value returns None on error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(
                side_effect=httpx.RequestError("Network error")
            )

            data_point = await collector.fetch_latest_value("DFII10")

            assert data_point is None


class TestMacroDataPoint:
    """Tests for MacroDataPoint data class."""

    def test_macro_data_point_creation(self):
        """Test MacroDataPoint can be created with required fields."""
        dp = MacroDataPoint(
            series_id="DFII10",
            date=date(2025, 1, 20),
            value=Decimal("2.35"),
        )

        assert dp.series_id == "DFII10"
        assert dp.date == date(2025, 1, 20)
        assert dp.value == Decimal("2.35")

    def test_macro_data_point_to_dict(self):
        """Test MacroDataPoint to_dict method."""
        dp = MacroDataPoint(
            series_id="DFII10",
            date=date(2025, 1, 20),
            value=Decimal("2.35"),
        )

        d = dp.to_dict()

        assert d["series_id"] == "DFII10"
        assert d["date"] == date(2025, 1, 20)
        assert d["value"] == Decimal("2.35")


class TestYieldSpread:
    """Tests for YieldSpread data class."""

    def test_yield_spread_creation(self):
        """Test YieldSpread can be created with required fields."""
        ys = YieldSpread(
            date=date(2025, 1, 20),
            dgs2=Decimal("4.20"),
            dgs10=Decimal("4.58"),
            spread=Decimal("0.38"),
        )

        assert ys.date == date(2025, 1, 20)
        assert ys.dgs2 == Decimal("4.20")
        assert ys.dgs10 == Decimal("4.58")
        assert ys.spread == Decimal("0.38")

    def test_yield_spread_to_dict(self):
        """Test YieldSpread to_dict method."""
        ys = YieldSpread(
            date=date(2025, 1, 20),
            dgs2=Decimal("4.20"),
            dgs10=Decimal("4.58"),
            spread=Decimal("0.38"),
        )

        d = ys.to_dict()

        assert d["date"] == date(2025, 1, 20)
        assert d["dgs2"] == Decimal("4.20")
        assert d["dgs10"] == Decimal("4.58")
        assert d["spread"] == Decimal("0.38")

    def test_yield_spread_inverted(self):
        """Test YieldSpread with negative spread (inverted curve)."""
        ys = YieldSpread(
            date=date(2025, 1, 20),
            dgs2=Decimal("4.80"),
            dgs10=Decimal("4.20"),
            spread=Decimal("-0.60"),
        )

        assert ys.spread < 0


class TestFREDCollectorFetchYieldSpread:
    """Tests for FREDCollector fetch_yield_spread method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance with mock API key."""
        with patch("src.collectors.structured.fred_collector.get_settings") as mock_settings:
            mock_settings.return_value.fred_api_key = "test_api_key"
            return FREDCollector()

    def _make_mock_response(self, value):
        """Helper to create a mock FRED API response with a single observation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "observations": [
                {"date": "2025-01-22", "value": value},
            ]
        }
        mock_response.raise_for_status = Mock()
        return mock_response

    @pytest.mark.asyncio
    async def test_fetch_yield_spread_positive(self, collector):
        """Test fetch_yield_spread returns positive spread (normal curve)."""
        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            series_id = kwargs.get("params", {}).get("series_id", "")
            if series_id == "DGS10":
                return self._make_mock_response("4.58")
            elif series_id == "DGS2":
                return self._make_mock_response("4.20")
            return self._make_mock_response("0.00")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)

            result = await collector.fetch_yield_spread()

            assert result is not None
            assert isinstance(result, YieldSpread)
            assert result.dgs10 == Decimal("4.58")
            assert result.dgs2 == Decimal("4.20")
            assert result.spread == Decimal("0.38")
            assert result.date == date(2025, 1, 22)

    @pytest.mark.asyncio
    async def test_fetch_yield_spread_inverted(self, collector):
        """Test fetch_yield_spread with inverted yield curve."""
        async def mock_get(*args, **kwargs):
            series_id = kwargs.get("params", {}).get("series_id", "")
            if series_id == "DGS10":
                return self._make_mock_response("3.90")
            elif series_id == "DGS2":
                return self._make_mock_response("4.50")
            return self._make_mock_response("0.00")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)

            result = await collector.fetch_yield_spread()

            assert result is not None
            assert result.spread == Decimal("-0.60")
            assert result.spread < 0

    @pytest.mark.asyncio
    async def test_fetch_yield_spread_returns_none_when_dgs10_missing(self, collector):
        """Test fetch_yield_spread returns None when DGS10 is unavailable."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(
                side_effect=httpx.RequestError("Network error")
            )

            result = await collector.fetch_yield_spread()

            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_yield_spread_returns_none_when_dgs2_missing(self, collector):
        """Test fetch_yield_spread returns None when DGS2 is unavailable."""
        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            series_id = kwargs.get("params", {}).get("series_id", "")
            if series_id == "DGS10":
                return self._make_mock_response("4.58")
            # DGS2 returns missing data
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"observations": [{"date": "2025-01-22", "value": "."}]}
            mock_response.raise_for_status = Mock()
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)

            result = await collector.fetch_yield_spread()

            assert result is None


# Integration test (skipped by default, run with: pytest -m integration)
@pytest.mark.integration
class TestFREDCollectorIntegration:
    """Integration tests that hit real FRED API."""

    @pytest.mark.asyncio
    async def test_fetch_real_series(self):
        """Test fetching real data from FRED API."""
        from src.config import get_settings

        settings = get_settings()
        if not settings.fred_api_key:
            pytest.skip("FRED_API_KEY not configured")

        collector = FREDCollector()
        data_points = await collector.fetch_series(
            series_id="DFII10",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 20),
        )

        assert len(data_points) > 0
        assert all(dp.series_id == "DFII10" for dp in data_points)
