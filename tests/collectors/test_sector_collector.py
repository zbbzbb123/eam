"""Tests for Sina sector collector."""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

import httpx

from src.collectors.structured.sector_collector import (
    SectorCollector,
    SectorData,
    SINA_INDUSTRY_URL,
    SINA_CONCEPT_URL,
)

# Sample JS response mimicking Sina industry API
SAMPLE_INDUSTRY_JS = (
    'var S_Finance_bankuai_sinaindustry = {'
    '"new_ylmy":"new_ylmy,医疗美容,35,42.15,0.88,2.13,4850300,2043826816,'
    'sz300760,42.50,41.62,0.88,迈瑞医疗",'
    '"new_jsyb":"new_jsyb,家用电器,58,28.76,0.35,1.23,6230100,1791524864,'
    'sh600519,25.30,24.95,0.35,格力电器"'
    '}'
)

# Sample JS response mimicking Sina concept API
SAMPLE_CONCEPT_JS = (
    'var S_Finance_bankuai_sinaconcept = {'
    '"new_rgzn":"new_rgzn,人工智能,120,55.80,1.25,2.29,12500000,6975000000,'
    'sz300033,88.20,86.95,1.25,同花顺",'
    '"new_swyl":"new_swyl,生物医药,95,33.40,0.62,1.89,8700000,2905800000,'
    'sh600276,45.10,44.48,0.62,恒瑞医药"'
    '}'
)

# Malformed JS response (no valid var assignment)
MALFORMED_JS = 'some random text without valid JS'

# JS with insufficient fields
INSUFFICIENT_FIELDS_JS = (
    'var S_Finance_bankuai_sinaindustry = {'
    '"bad":"bad,BadSector,10"'
    '}'
)


class TestSectorDataDataclass:
    """Tests for SectorData dataclass."""

    def test_creation(self):
        """Test SectorData can be created with required fields."""
        sd = SectorData(
            code="new_ylmy",
            name="医疗美容",
            stock_count=35,
            avg_price=Decimal("42.15"),
            change_pct=Decimal("2.13"),
            volume=Decimal("4850300"),
            amount=Decimal("2043826816"),
            leading_stock="迈瑞医疗",
        )
        assert sd.code == "new_ylmy"
        assert sd.name == "医疗美容"
        assert sd.stock_count == 35
        assert sd.avg_price == Decimal("42.15")
        assert sd.change_pct == Decimal("2.13")
        assert sd.leading_stock == "迈瑞医疗"

    def test_to_dict(self):
        """Test SectorData to_dict method."""
        sd = SectorData(
            code="new_ylmy",
            name="医疗美容",
            stock_count=35,
            avg_price=Decimal("42.15"),
            change_pct=Decimal("2.13"),
            volume=Decimal("4850300"),
            amount=Decimal("2043826816"),
            leading_stock="迈瑞医疗",
        )
        d = sd.to_dict()
        assert d["code"] == "new_ylmy"
        assert d["name"] == "医疗美容"
        assert d["stock_count"] == 35
        assert d["avg_price"] == Decimal("42.15")
        assert d["leading_stock"] == "迈瑞医疗"


class TestSectorCollectorProperties:
    """Tests for SectorCollector properties."""

    def test_name_property(self):
        """Test that name property returns 'sector_collector'."""
        collector = SectorCollector()
        assert collector.name == "sector_collector"
        collector.close()

    def test_source_property(self):
        """Test that source property returns 'sina'."""
        collector = SectorCollector()
        assert collector.source == "sina"
        collector.close()

    def test_context_manager(self):
        """Test that SectorCollector works as a context manager."""
        with SectorCollector() as collector:
            assert collector.name == "sector_collector"


class TestSectorCollectorParseJsResponse:
    """Tests for _parse_js_response internal method."""

    def setup_method(self):
        self.collector = SectorCollector()

    def teardown_method(self):
        self.collector.close()

    def test_parse_valid_industry_response(self):
        """Test parsing a valid industry JS response."""
        result = self.collector._parse_js_response(SAMPLE_INDUSTRY_JS)
        assert isinstance(result, dict)
        assert len(result) == 2
        assert "new_ylmy" in result
        assert "new_jsyb" in result

    def test_parse_valid_concept_response(self):
        """Test parsing a valid concept JS response."""
        result = self.collector._parse_js_response(SAMPLE_CONCEPT_JS)
        assert isinstance(result, dict)
        assert len(result) == 2
        assert "new_rgzn" in result

    def test_parse_malformed_response_raises(self):
        """Test that malformed JS raises ValueError."""
        with pytest.raises(ValueError, match="Could not extract JS object"):
            self.collector._parse_js_response(MALFORMED_JS)

    def test_parse_empty_string_raises(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Could not extract JS object"):
            self.collector._parse_js_response("")


class TestSectorCollectorParseSectorEntry:
    """Tests for _parse_sector_entry internal method."""

    def setup_method(self):
        self.collector = SectorCollector()

    def teardown_method(self):
        self.collector.close()

    def test_parse_valid_entry(self):
        """Test parsing a valid sector entry."""
        raw = ("new_ylmy,医疗美容,35,42.15,0.88,2.13,4850300,2043826816,"
               "sz300760,42.50,41.62,0.88,迈瑞医疗")
        result = self.collector._parse_sector_entry("new_ylmy", raw)
        assert result is not None
        assert result.code == "new_ylmy"
        assert result.name == "医疗美容"
        assert result.stock_count == 35
        assert result.avg_price == Decimal("42.15")
        assert result.change_pct == Decimal("2.13")
        assert result.volume == Decimal("4850300")
        assert result.amount == Decimal("2043826816")
        assert result.leading_stock == "迈瑞医疗"

    def test_parse_entry_with_insufficient_fields(self):
        """Test that an entry with too few fields returns None."""
        result = self.collector._parse_sector_entry("bad", "bad,BadSector,10")
        assert result is None

    def test_parse_entry_with_invalid_number(self):
        """Test that an entry with non-numeric values returns None."""
        raw = "code,name,notanumber,42.15,0.88,2.13,4850300,2043826816,sz300760,42.50,41.62,0.88,LeadStock"
        result = self.collector._parse_sector_entry("code", raw)
        assert result is None


class TestSectorCollectorFetchIndustry:
    """Tests for fetch_industry_sectors method."""

    def test_fetch_industry_sectors_success(self):
        """Test successful fetch of industry sectors."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_INDUSTRY_JS
        mock_response.raise_for_status = Mock()

        with patch.object(httpx.Client, "get", return_value=mock_response):
            collector = SectorCollector()
            sectors = collector.fetch_industry_sectors()
            collector.close()

        assert len(sectors) == 2
        assert all(isinstance(s, SectorData) for s in sectors)
        names = [s.name for s in sectors]
        assert "医疗美容" in names
        assert "家用电器" in names

    def test_fetch_industry_sectors_http_error(self):
        """Test that HTTP errors return empty list."""
        with patch.object(
            httpx.Client,
            "get",
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=Mock(),
                response=Mock(status_code=500),
            ),
        ):
            collector = SectorCollector()
            sectors = collector.fetch_industry_sectors()
            collector.close()

        assert sectors == []

    def test_fetch_industry_sectors_network_error(self):
        """Test that network errors return empty list."""
        with patch.object(
            httpx.Client,
            "get",
            side_effect=httpx.RequestError("Connection failed"),
        ):
            collector = SectorCollector()
            sectors = collector.fetch_industry_sectors()
            collector.close()

        assert sectors == []

    def test_fetch_industry_sectors_parse_error(self):
        """Test that malformed responses return empty list."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = MALFORMED_JS
        mock_response.raise_for_status = Mock()

        with patch.object(httpx.Client, "get", return_value=mock_response):
            collector = SectorCollector()
            sectors = collector.fetch_industry_sectors()
            collector.close()

        assert sectors == []

    def test_fetch_industry_sectors_skips_bad_entries(self):
        """Test that entries with insufficient fields are skipped."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = INSUFFICIENT_FIELDS_JS
        mock_response.raise_for_status = Mock()

        with patch.object(httpx.Client, "get", return_value=mock_response):
            collector = SectorCollector()
            sectors = collector.fetch_industry_sectors()
            collector.close()

        assert sectors == []


class TestSectorCollectorFetchConcept:
    """Tests for fetch_concept_sectors method."""

    def test_fetch_concept_sectors_success(self):
        """Test successful fetch of concept sectors."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_CONCEPT_JS
        mock_response.raise_for_status = Mock()

        with patch.object(httpx.Client, "get", return_value=mock_response):
            collector = SectorCollector()
            sectors = collector.fetch_concept_sectors()
            collector.close()

        assert len(sectors) == 2
        assert all(isinstance(s, SectorData) for s in sectors)
        names = [s.name for s in sectors]
        assert "人工智能" in names
        assert "生物医药" in names

    def test_fetch_concept_sectors_passes_params(self):
        """Test that concept fetch includes param=class."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_CONCEPT_JS
        mock_response.raise_for_status = Mock()

        with patch.object(httpx.Client, "get", return_value=mock_response) as mock_get:
            collector = SectorCollector()
            collector.fetch_concept_sectors()
            collector.close()

            mock_get.assert_called_once_with(
                SINA_CONCEPT_URL,
                params={"param": "class"},
            )


class TestSectorCollectorFetchAll:
    """Tests for fetch_all method."""

    def test_fetch_all_returns_both_categories(self):
        """Test that fetch_all returns dict with industry and concept keys."""
        mock_industry_response = Mock()
        mock_industry_response.status_code = 200
        mock_industry_response.text = SAMPLE_INDUSTRY_JS
        mock_industry_response.raise_for_status = Mock()

        mock_concept_response = Mock()
        mock_concept_response.status_code = 200
        mock_concept_response.text = SAMPLE_CONCEPT_JS
        mock_concept_response.raise_for_status = Mock()

        def side_effect(url, **kwargs):
            if url == SINA_INDUSTRY_URL:
                return mock_industry_response
            return mock_concept_response

        with patch.object(httpx.Client, "get", side_effect=side_effect):
            collector = SectorCollector()
            result = collector.fetch_all()
            collector.close()

        assert "industry" in result
        assert "concept" in result
        assert len(result["industry"]) == 2
        assert len(result["concept"]) == 2

    def test_fetch_all_partial_failure(self):
        """Test fetch_all when one category fails."""
        mock_industry_response = Mock()
        mock_industry_response.status_code = 200
        mock_industry_response.text = SAMPLE_INDUSTRY_JS
        mock_industry_response.raise_for_status = Mock()

        call_count = 0

        def side_effect(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if url == SINA_CONCEPT_URL:
                raise httpx.RequestError("Connection failed")
            return mock_industry_response

        with patch.object(httpx.Client, "get", side_effect=side_effect):
            collector = SectorCollector()
            result = collector.fetch_all()
            collector.close()

        assert len(result["industry"]) == 2
        assert result["concept"] == []
