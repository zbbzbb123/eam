"""Tests for Chinese macroeconomic data collector."""
import pytest
from datetime import date
from unittest.mock import Mock, patch, AsyncMock
from decimal import Decimal

import httpx

from src.collectors.structured.cn_macro_collector import (
    CnMacroCollector,
    CnMacroData,
    EASTMONEY_API_BASE_URL,
)


class TestCnMacroDataDataclass:
    """Tests for CnMacroData data class."""

    def test_creation_with_all_fields(self):
        """Test CnMacroData can be created with all fields."""
        dp = CnMacroData(
            indicator="manufacturing_pmi",
            date=date(2025, 1, 31),
            value=Decimal("50.1"),
            yoy_change=Decimal("0.2"),
        )

        assert dp.indicator == "manufacturing_pmi"
        assert dp.date == date(2025, 1, 31)
        assert dp.value == Decimal("50.1")
        assert dp.yoy_change == Decimal("0.2")

    def test_creation_with_none_yoy(self):
        """Test CnMacroData with None yoy_change."""
        dp = CnMacroData(
            indicator="manufacturing_pmi",
            date=date(2025, 1, 31),
            value=Decimal("50.1"),
            yoy_change=None,
        )

        assert dp.yoy_change is None

    def test_to_dict(self):
        """Test CnMacroData to_dict method."""
        dp = CnMacroData(
            indicator="cpi_yoy",
            date=date(2025, 1, 31),
            value=Decimal("0.5"),
            yoy_change=Decimal("0.5"),
        )

        d = dp.to_dict()

        assert d["indicator"] == "cpi_yoy"
        assert d["date"] == date(2025, 1, 31)
        assert d["value"] == Decimal("0.5")
        assert d["yoy_change"] == Decimal("0.5")


class TestCnMacroCollectorProperties:
    """Tests for CnMacroCollector properties."""

    def test_name_property(self):
        """Test that name property returns 'cn_macro_collector'."""
        collector = CnMacroCollector()
        assert collector.name == "cn_macro_collector"

    def test_source_property(self):
        """Test that source property returns 'eastmoney'."""
        collector = CnMacroCollector()
        assert collector.source == "eastmoney"


def _make_mock_client(mock_response):
    """Helper to create a mocked httpx.AsyncClient context manager."""
    mock_client = Mock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)
    return mock_client


def _make_mock_response(json_data):
    """Helper to create a mocked httpx response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = json_data
    mock_response.raise_for_status = Mock()
    return mock_response


class TestCnMacroCollectorFetchPmi:
    """Tests for CnMacroCollector fetch_pmi method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return CnMacroCollector()

    @pytest.fixture
    def mock_pmi_response(self):
        """Create mock PMI API response."""
        return {
            "result": {
                "data": [
                    {
                        "REPORT_DATE": "2025-01-31 00:00:00",
                        "MAKE_INDEX": 50.1,
                        "NMAKE_INDEX": 50.2,
                    },
                    {
                        "REPORT_DATE": "2024-12-31 00:00:00",
                        "MAKE_INDEX": 50.3,
                        "NMAKE_INDEX": 52.2,
                    },
                ]
            }
        }

    @pytest.mark.asyncio
    async def test_fetch_pmi_returns_data_points(self, collector, mock_pmi_response):
        """Test that fetch_pmi returns CnMacroData objects."""
        mock_response = _make_mock_response(mock_pmi_response)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client(mock_response)

            data_points = await collector.fetch_pmi()

            # 2 rows x 2 indicators each = 4 data points
            assert len(data_points) == 4
            assert all(isinstance(dp, CnMacroData) for dp in data_points)

            # First row: manufacturing PMI
            assert data_points[0].indicator == "manufacturing_pmi"
            assert data_points[0].date == date(2025, 1, 31)
            assert data_points[0].value == Decimal("50.1")
            assert data_points[0].yoy_change is None

            # First row: non-manufacturing PMI
            assert data_points[1].indicator == "non_manufacturing_pmi"
            assert data_points[1].date == date(2025, 1, 31)
            assert data_points[1].value == Decimal("50.2")

    @pytest.mark.asyncio
    async def test_fetch_pmi_handles_missing_nmake(self, collector):
        """Test that fetch_pmi handles missing NMAKE_INDEX."""
        response_data = {
            "result": {
                "data": [
                    {
                        "REPORT_DATE": "2025-01-31 00:00:00",
                        "MAKE_INDEX": 50.1,
                        "NMAKE_INDEX": None,
                    },
                ]
            }
        }
        mock_response = _make_mock_response(response_data)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client(mock_response)

            data_points = await collector.fetch_pmi()

            assert len(data_points) == 1
            assert data_points[0].indicator == "manufacturing_pmi"

    @pytest.mark.asyncio
    async def test_fetch_pmi_empty_result(self, collector):
        """Test handling of empty result."""
        response_data = {"result": {"data": []}}
        mock_response = _make_mock_response(response_data)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client(mock_response)

            data_points = await collector.fetch_pmi()

            assert data_points == []


class TestCnMacroCollectorFetchCpi:
    """Tests for CnMacroCollector fetch_cpi method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return CnMacroCollector()

    @pytest.fixture
    def mock_cpi_response(self):
        """Create mock CPI API response."""
        return {
            "result": {
                "data": [
                    {
                        "REPORT_DATE": "2025-01-31 00:00:00",
                        "NATIONAL_SAME": 0.5,
                        "NATIONAL_BASE": 100.5,
                        "NATIONAL_SEQUENTIAL": 0.2,
                    },
                    {
                        "REPORT_DATE": "2024-12-31 00:00:00",
                        "NATIONAL_SAME": 0.1,
                        "NATIONAL_BASE": 100.1,
                        "NATIONAL_SEQUENTIAL": -0.1,
                    },
                ]
            }
        }

    @pytest.mark.asyncio
    async def test_fetch_cpi_returns_data_points(self, collector, mock_cpi_response):
        """Test that fetch_cpi returns CnMacroData objects."""
        mock_response = _make_mock_response(mock_cpi_response)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client(mock_response)

            data_points = await collector.fetch_cpi()

            # 2 rows x 2 indicators (yoy + mom) = 4 data points
            assert len(data_points) == 4
            assert all(isinstance(dp, CnMacroData) for dp in data_points)

            # First row: CPI YoY
            yoy_points = [dp for dp in data_points if dp.indicator == "cpi_yoy"]
            assert len(yoy_points) == 2
            assert yoy_points[0].value == Decimal("0.5")
            assert yoy_points[0].yoy_change == Decimal("0.5")

            # First row: CPI MoM
            mom_points = [dp for dp in data_points if dp.indicator == "cpi_mom"]
            assert len(mom_points) == 2
            assert mom_points[0].value == Decimal("0.2")
            assert mom_points[0].yoy_change is None


class TestCnMacroCollectorFetchM2:
    """Tests for CnMacroCollector fetch_m2 method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return CnMacroCollector()

    @pytest.fixture
    def mock_m2_response(self):
        """Create mock M2 API response."""
        return {
            "result": {
                "data": [
                    {
                        "REPORT_DATE": "2025-01-31 00:00:00",
                        "BASIC_CURRENCY": 3134500.0,
                        "BASIC_CURRENCY_SAME": 7.0,
                        "BASIC_CURRENCY_SEQUENTIAL": 0.5,
                    },
                    {
                        "REPORT_DATE": "2024-12-31 00:00:00",
                        "BASIC_CURRENCY": 3095200.0,
                        "BASIC_CURRENCY_SAME": 7.3,
                        "BASIC_CURRENCY_SEQUENTIAL": 0.8,
                    },
                ]
            }
        }

    @pytest.mark.asyncio
    async def test_fetch_m2_returns_data_points(self, collector, mock_m2_response):
        """Test that fetch_m2 returns CnMacroData objects."""
        mock_response = _make_mock_response(mock_m2_response)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client(mock_response)

            data_points = await collector.fetch_m2()

            # 2 rows x 1 indicator = 2 data points
            assert len(data_points) == 2
            assert all(isinstance(dp, CnMacroData) for dp in data_points)

            assert data_points[0].indicator == "m2_balance"
            assert data_points[0].date == date(2025, 1, 31)
            assert data_points[0].value == Decimal("3134500.0")
            assert data_points[0].yoy_change == Decimal("7.0")

    @pytest.mark.asyncio
    async def test_fetch_m2_missing_yoy(self, collector):
        """Test M2 with missing year-over-year data."""
        response_data = {
            "result": {
                "data": [
                    {
                        "REPORT_DATE": "2025-01-31 00:00:00",
                        "BASIC_CURRENCY": 3134500.0,
                        "BASIC_CURRENCY_SAME": None,
                        "BASIC_CURRENCY_SEQUENTIAL": None,
                    },
                ]
            }
        }
        mock_response = _make_mock_response(response_data)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client(mock_response)

            data_points = await collector.fetch_m2()

            assert len(data_points) == 1
            assert data_points[0].yoy_change is None


class TestCnMacroCollectorFetchAll:
    """Tests for CnMacroCollector fetch_all method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return CnMacroCollector()

    @pytest.mark.asyncio
    async def test_fetch_all_returns_dict(self, collector):
        """Test that fetch_all returns dictionary with all categories."""
        mock_response_data = {
            "result": {
                "data": [
                    {
                        "REPORT_DATE": "2025-01-31 00:00:00",
                        "MAKE_INDEX": 50.1,
                        "NMAKE_INDEX": 50.2,
                        "NATIONAL_SAME": 0.5,
                        "NATIONAL_BASE": 100.5,
                        "NATIONAL_SEQUENTIAL": 0.2,
                        "BASIC_CURRENCY": 3134500.0,
                        "BASIC_CURRENCY_SAME": 7.0,
                        "BASIC_CURRENCY_SEQUENTIAL": 0.5,
                    },
                ]
            }
        }
        mock_response = _make_mock_response(mock_response_data)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client(mock_response)

            result = await collector.fetch_all()

            assert isinstance(result, dict)
            assert "pmi" in result
            assert "cpi" in result
            assert "m2" in result
            assert all(isinstance(v, list) for v in result.values())


class TestCnMacroCollectorErrorHandling:
    """Tests for error handling in CnMacroCollector."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return CnMacroCollector()

    @pytest.mark.asyncio
    async def test_http_error_returns_empty(self, collector):
        """Test that HTTP errors return empty list."""
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = Mock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Server error",
                    request=Mock(),
                    response=Mock(status_code=500),
                )
            )
            mock_cls.return_value = mock_client

            data_points = await collector.fetch_pmi()

            assert data_points == []

    @pytest.mark.asyncio
    async def test_network_error_returns_empty(self, collector):
        """Test that network errors return empty list."""
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = Mock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(
                side_effect=httpx.RequestError("Connection refused")
            )
            mock_cls.return_value = mock_client

            data_points = await collector.fetch_cpi()

            assert data_points == []

    @pytest.mark.asyncio
    async def test_null_result_returns_empty(self, collector):
        """Test handling of null result in response."""
        response_data = {"result": None}
        mock_response = _make_mock_response(response_data)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client(mock_response)

            data_points = await collector.fetch_m2()

            assert data_points == []

    @pytest.mark.asyncio
    async def test_api_call_uses_correct_url(self, collector):
        """Test that API calls use the correct EastMoney URL."""
        response_data = {"result": {"data": []}}
        mock_response = _make_mock_response(response_data)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = _make_mock_client(mock_response)
            mock_cls.return_value = mock_client

            await collector.fetch_pmi()

            mock_client.get.assert_called_once()
            call_args = mock_client.get.call_args
            assert call_args[0][0] == EASTMONEY_API_BASE_URL
            params = call_args[1].get("params", call_args[0][1] if len(call_args[0]) > 1 else {})
            assert params["reportName"] == "RPT_ECONOMY_PMI"
