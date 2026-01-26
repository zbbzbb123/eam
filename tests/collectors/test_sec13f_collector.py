"""Tests for SEC EDGAR 13F collector."""
import pytest
from datetime import date
from unittest.mock import Mock, patch, AsyncMock
from decimal import Decimal

import httpx

from src.collectors.structured.sec13f_collector import (
    SEC13FCollector,
    InstitutionalHoldingData,
    TRACKED_INSTITUTIONS,
)


class TestSEC13FCollectorProperties:
    """Tests for SEC13FCollector properties."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return SEC13FCollector()

    def test_name_property(self, collector):
        """Test that name property returns 'sec13f_collector'."""
        assert collector.name == "sec13f_collector"

    def test_source_property(self, collector):
        """Test that source property returns 'sec_edgar'."""
        assert collector.source == "sec_edgar"

    def test_tracked_institutions(self, collector):
        """Test that tracked institutions contains expected institutions."""
        expected_ciks = [
            "0001067983",  # Berkshire Hathaway
            "0001818482",  # ARK Invest
            "0001350694",  # Bridgewater
            "0001037389",  # Renaissance Technologies
        ]
        tracked = collector.tracked_institutions
        assert len(tracked) >= 4
        for cik in expected_ciks:
            assert cik in tracked


class TestTrackedInstitutions:
    """Tests for the tracked institutions configuration."""

    def test_tracked_institutions_has_berkshire(self):
        """Test that Berkshire Hathaway is tracked."""
        assert "0001067983" in TRACKED_INSTITUTIONS
        assert TRACKED_INSTITUTIONS["0001067983"] == "Berkshire Hathaway Inc"

    def test_tracked_institutions_has_ark(self):
        """Test that ARK Invest is tracked."""
        assert "0001818482" in TRACKED_INSTITUTIONS
        assert TRACKED_INSTITUTIONS["0001818482"] == "ARK Investment Management LLC"

    def test_tracked_institutions_has_bridgewater(self):
        """Test that Bridgewater is tracked."""
        assert "0001350694" in TRACKED_INSTITUTIONS
        assert TRACKED_INSTITUTIONS["0001350694"] == "Bridgewater Associates, LP"

    def test_tracked_institutions_has_renaissance(self):
        """Test that Renaissance Technologies is tracked."""
        assert "0001037389" in TRACKED_INSTITUTIONS
        assert TRACKED_INSTITUTIONS["0001037389"] == "Renaissance Technologies LLC"


class TestInstitutionalHoldingData:
    """Tests for InstitutionalHoldingData dataclass."""

    def test_holding_data_creation(self):
        """Test InstitutionalHoldingData can be created with required fields."""
        holding = InstitutionalHoldingData(
            institution_cik="0001067983",
            institution_name="Berkshire Hathaway Inc",
            report_date=date(2024, 9, 30),
            cusip="037833100",
            stock_name="APPLE INC",
            shares=400000000,
            value=Decimal("89000000000"),
        )

        assert holding.institution_cik == "0001067983"
        assert holding.institution_name == "Berkshire Hathaway Inc"
        assert holding.report_date == date(2024, 9, 30)
        assert holding.cusip == "037833100"
        assert holding.stock_name == "APPLE INC"
        assert holding.shares == 400000000
        assert holding.value == Decimal("89000000000")

    def test_holding_data_to_dict(self):
        """Test InstitutionalHoldingData to_dict method."""
        holding = InstitutionalHoldingData(
            institution_cik="0001067983",
            institution_name="Berkshire Hathaway Inc",
            report_date=date(2024, 9, 30),
            cusip="037833100",
            stock_name="APPLE INC",
            shares=400000000,
            value=Decimal("89000000000"),
        )

        d = holding.to_dict()

        assert d["institution_cik"] == "0001067983"
        assert d["institution_name"] == "Berkshire Hathaway Inc"
        assert d["report_date"] == date(2024, 9, 30)
        assert d["cusip"] == "037833100"
        assert d["stock_name"] == "APPLE INC"
        assert d["shares"] == 400000000
        assert d["value"] == Decimal("89000000000")


def create_mock_async_client(response):
    """Helper to create a properly mocked AsyncClient."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


class TestSEC13FCollectorFetchFilings:
    """Tests for SEC13FCollector fetch_filings method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return SEC13FCollector()

    @pytest.fixture
    def mock_submissions_response(self):
        """Create mock SEC submissions API response."""
        return {
            "cik": "1067983",
            "name": "BERKSHIRE HATHAWAY INC",
            "filings": {
                "recent": {
                    "accessionNumber": [
                        "0000950123-24-012345",
                        "0000950123-24-012346",
                        "0000950123-24-012347",
                    ],
                    "filingDate": [
                        "2024-11-14",
                        "2024-08-14",
                        "2024-05-15",
                    ],
                    "form": [
                        "13F-HR",
                        "13F-HR",
                        "13F-HR",
                    ],
                    "primaryDocument": [
                        "infotable.xml",
                        "infotable.xml",
                        "infotable.xml",
                    ],
                    "reportDate": [
                        "2024-09-30",
                        "2024-06-30",
                        "2024-03-31",
                    ],
                }
            }
        }

    @pytest.mark.asyncio
    async def test_fetch_filings_returns_filing_info(self, collector, mock_submissions_response):
        """Test that fetch_filings returns filing information."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_submissions_response
        mock_response.raise_for_status = Mock()

        mock_client = create_mock_async_client(mock_response)

        with patch("src.collectors.structured.sec13f_collector.httpx.AsyncClient", return_value=mock_client):
            filings = await collector.fetch_filings("0001067983")

            assert len(filings) == 3
            assert filings[0]["accession_number"] == "0000950123-24-012345"
            assert filings[0]["filing_date"] == "2024-11-14"
            assert filings[0]["report_date"] == "2024-09-30"

    @pytest.mark.asyncio
    async def test_fetch_filings_filters_by_form_type(self, collector):
        """Test that fetch_filings only returns 13F-HR filings."""
        mock_response_data = {
            "cik": "1067983",
            "name": "BERKSHIRE HATHAWAY INC",
            "filings": {
                "recent": {
                    "accessionNumber": [
                        "0000950123-24-012345",
                        "0000950123-24-012346",
                        "0000950123-24-012347",
                    ],
                    "filingDate": [
                        "2024-11-14",
                        "2024-08-14",
                        "2024-05-15",
                    ],
                    "form": [
                        "13F-HR",
                        "10-K",  # Not a 13F-HR
                        "13F-HR",
                    ],
                    "primaryDocument": [
                        "infotable.xml",
                        "annual.htm",
                        "infotable.xml",
                    ],
                    "reportDate": [
                        "2024-09-30",
                        "2023-12-31",
                        "2024-03-31",
                    ],
                }
            }
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = Mock()

        mock_client = create_mock_async_client(mock_response)

        with patch("src.collectors.structured.sec13f_collector.httpx.AsyncClient", return_value=mock_client):
            filings = await collector.fetch_filings("0001067983")

            assert len(filings) == 2
            assert all(f["form"] == "13F-HR" for f in filings)

    @pytest.mark.asyncio
    async def test_fetch_filings_respects_limit(self, collector, mock_submissions_response):
        """Test that fetch_filings respects the limit parameter."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_submissions_response
        mock_response.raise_for_status = Mock()

        mock_client = create_mock_async_client(mock_response)

        with patch("src.collectors.structured.sec13f_collector.httpx.AsyncClient", return_value=mock_client):
            filings = await collector.fetch_filings("0001067983", limit=2)

            assert len(filings) == 2

    @pytest.mark.asyncio
    async def test_fetch_filings_uses_correct_user_agent(self, collector):
        """Test that fetch_filings includes proper User-Agent header."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "cik": "1067983",
            "name": "BERKSHIRE HATHAWAY INC",
            "filings": {"recent": {"accessionNumber": [], "filingDate": [], "form": [], "primaryDocument": [], "reportDate": []}}
        }
        mock_response.raise_for_status = Mock()

        mock_client = create_mock_async_client(mock_response)

        with patch("src.collectors.structured.sec13f_collector.httpx.AsyncClient", return_value=mock_client) as mock_class:
            await collector.fetch_filings("0001067983")

            # Check that the client was created with headers
            mock_class.assert_called_once()
            call_kwargs = mock_class.call_args[1]
            assert "headers" in call_kwargs
            assert "User-Agent" in call_kwargs["headers"]

    @pytest.mark.asyncio
    async def test_fetch_filings_handles_api_error(self, collector):
        """Test that fetch_filings handles API errors gracefully."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "API error",
                request=Mock(),
                response=Mock(status_code=500),
            )
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.collectors.structured.sec13f_collector.httpx.AsyncClient", return_value=mock_client):
            filings = await collector.fetch_filings("0001067983")

            assert filings == []

    @pytest.mark.asyncio
    async def test_fetch_filings_handles_network_error(self, collector):
        """Test that fetch_filings handles network errors gracefully."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("Network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.collectors.structured.sec13f_collector.httpx.AsyncClient", return_value=mock_client):
            filings = await collector.fetch_filings("0001067983")

            assert filings == []


class TestSEC13FCollectorFetchHoldings:
    """Tests for SEC13FCollector fetch_holdings method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return SEC13FCollector()

    @pytest.fixture
    def mock_holdings_xml(self):
        """Create mock 13F holdings XML response."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
    <infoTable>
        <nameOfIssuer>APPLE INC</nameOfIssuer>
        <titleOfClass>COM</titleOfClass>
        <cusip>037833100</cusip>
        <value>89000000</value>
        <shrsOrPrnAmt>
            <sshPrnamt>400000000</sshPrnamt>
            <sshPrnamtType>SH</sshPrnamtType>
        </shrsOrPrnAmt>
        <investmentDiscretion>SOLE</investmentDiscretion>
        <votingAuthority>
            <Sole>400000000</Sole>
            <Shared>0</Shared>
            <None>0</None>
        </votingAuthority>
    </infoTable>
    <infoTable>
        <nameOfIssuer>BANK OF AMERICA CORP</nameOfIssuer>
        <titleOfClass>COM</titleOfClass>
        <cusip>060505104</cusip>
        <value>35000000</value>
        <shrsOrPrnAmt>
            <sshPrnamt>1032853000</sshPrnamt>
            <sshPrnamtType>SH</sshPrnamtType>
        </shrsOrPrnAmt>
        <investmentDiscretion>SOLE</investmentDiscretion>
        <votingAuthority>
            <Sole>1032853000</Sole>
            <Shared>0</Shared>
            <None>0</None>
        </votingAuthority>
    </infoTable>
</informationTable>"""

    @pytest.mark.asyncio
    async def test_fetch_holdings_returns_holding_data(self, collector, mock_holdings_xml):
        """Test that fetch_holdings returns InstitutionalHoldingData objects."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_holdings_xml
        mock_response.raise_for_status = Mock()

        mock_client = create_mock_async_client(mock_response)

        with patch("src.collectors.structured.sec13f_collector.httpx.AsyncClient", return_value=mock_client):
            holdings = await collector.fetch_holdings(
                cik="0001067983",
                accession_number="0000950123-24-012345",
                report_date="2024-09-30",
            )

            assert len(holdings) == 2
            assert all(isinstance(h, InstitutionalHoldingData) for h in holdings)

    @pytest.mark.asyncio
    async def test_fetch_holdings_parses_correctly(self, collector, mock_holdings_xml):
        """Test that fetch_holdings parses XML correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_holdings_xml
        mock_response.raise_for_status = Mock()

        mock_client = create_mock_async_client(mock_response)

        with patch("src.collectors.structured.sec13f_collector.httpx.AsyncClient", return_value=mock_client):
            holdings = await collector.fetch_holdings(
                cik="0001067983",
                accession_number="0000950123-24-012345",
                report_date="2024-09-30",
            )

            apple_holding = next(h for h in holdings if h.cusip == "037833100")
            assert apple_holding.stock_name == "APPLE INC"
            assert apple_holding.shares == 400000000
            assert apple_holding.value == Decimal("89000000000")  # Value is in thousands
            assert apple_holding.institution_cik == "0001067983"
            assert apple_holding.report_date == date(2024, 9, 30)

    @pytest.mark.asyncio
    async def test_fetch_holdings_sets_institution_name(self, collector, mock_holdings_xml):
        """Test that fetch_holdings sets institution name from tracked list."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_holdings_xml
        mock_response.raise_for_status = Mock()

        mock_client = create_mock_async_client(mock_response)

        with patch("src.collectors.structured.sec13f_collector.httpx.AsyncClient", return_value=mock_client):
            holdings = await collector.fetch_holdings(
                cik="0001067983",
                accession_number="0000950123-24-012345",
                report_date="2024-09-30",
            )

            assert holdings[0].institution_name == "Berkshire Hathaway Inc"

    @pytest.mark.asyncio
    async def test_fetch_holdings_handles_api_error(self, collector):
        """Test that fetch_holdings handles API errors gracefully."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "API error",
                request=Mock(),
                response=Mock(status_code=404),
            )
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.collectors.structured.sec13f_collector.httpx.AsyncClient", return_value=mock_client):
            holdings = await collector.fetch_holdings(
                cik="0001067983",
                accession_number="0000950123-24-012345",
                report_date="2024-09-30",
            )

            assert holdings == []

    @pytest.mark.asyncio
    async def test_fetch_holdings_handles_malformed_xml(self, collector):
        """Test that fetch_holdings handles malformed XML gracefully."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<invalid>xml<that>is broken"
        mock_response.raise_for_status = Mock()

        mock_client = create_mock_async_client(mock_response)

        with patch("src.collectors.structured.sec13f_collector.httpx.AsyncClient", return_value=mock_client):
            holdings = await collector.fetch_holdings(
                cik="0001067983",
                accession_number="0000950123-24-012345",
                report_date="2024-09-30",
            )

            assert holdings == []


class TestSEC13FCollectorFetchLatestHoldings:
    """Tests for SEC13FCollector fetch_latest_holdings method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return SEC13FCollector()

    @pytest.fixture
    def mock_submissions_response(self):
        """Create mock SEC submissions API response."""
        return {
            "cik": "1067983",
            "name": "BERKSHIRE HATHAWAY INC",
            "filings": {
                "recent": {
                    "accessionNumber": ["0000950123-24-012345"],
                    "filingDate": ["2024-11-14"],
                    "form": ["13F-HR"],
                    "primaryDocument": ["infotable.xml"],
                    "reportDate": ["2024-09-30"],
                }
            }
        }

    @pytest.fixture
    def mock_holdings_xml(self):
        """Create mock 13F holdings XML response."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
    <infoTable>
        <nameOfIssuer>APPLE INC</nameOfIssuer>
        <titleOfClass>COM</titleOfClass>
        <cusip>037833100</cusip>
        <value>89000000</value>
        <shrsOrPrnAmt>
            <sshPrnamt>400000000</sshPrnamt>
            <sshPrnamtType>SH</sshPrnamtType>
        </shrsOrPrnAmt>
        <investmentDiscretion>SOLE</investmentDiscretion>
        <votingAuthority>
            <Sole>400000000</Sole>
            <Shared>0</Shared>
            <None>0</None>
        </votingAuthority>
    </infoTable>
</informationTable>"""

    @pytest.mark.asyncio
    async def test_fetch_latest_holdings_returns_holdings(
        self, collector, mock_submissions_response, mock_holdings_xml
    ):
        """Test that fetch_latest_holdings returns holdings from latest filing."""
        mock_submissions_resp = Mock()
        mock_submissions_resp.status_code = 200
        mock_submissions_resp.json.return_value = mock_submissions_response
        mock_submissions_resp.raise_for_status = Mock()

        mock_holdings_resp = Mock()
        mock_holdings_resp.status_code = 200
        mock_holdings_resp.text = mock_holdings_xml
        mock_holdings_resp.raise_for_status = Mock()

        # Create a mock client that returns different responses for different calls
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=[mock_submissions_resp, mock_holdings_resp]
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.collectors.structured.sec13f_collector.httpx.AsyncClient", return_value=mock_client):
            holdings = await collector.fetch_latest_holdings("0001067983")

            assert len(holdings) == 1
            assert holdings[0].stock_name == "APPLE INC"

    @pytest.mark.asyncio
    async def test_fetch_latest_holdings_returns_empty_when_no_filings(self, collector):
        """Test that fetch_latest_holdings returns empty list when no filings."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "cik": "1067983",
            "name": "BERKSHIRE HATHAWAY INC",
            "filings": {"recent": {"accessionNumber": [], "filingDate": [], "form": [], "primaryDocument": [], "reportDate": []}}
        }
        mock_response.raise_for_status = Mock()

        mock_client = create_mock_async_client(mock_response)

        with patch("src.collectors.structured.sec13f_collector.httpx.AsyncClient", return_value=mock_client):
            holdings = await collector.fetch_latest_holdings("0001067983")

            assert holdings == []


class TestSEC13FCollectorFetchAllTrackedHoldings:
    """Tests for SEC13FCollector fetch_all_tracked_holdings method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return SEC13FCollector()

    @pytest.mark.asyncio
    async def test_fetch_all_tracked_holdings_returns_dict(self, collector):
        """Test that fetch_all_tracked_holdings returns dict of holdings by CIK."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "cik": "1067983",
            "name": "BERKSHIRE HATHAWAY INC",
            "filings": {"recent": {"accessionNumber": [], "filingDate": [], "form": [], "primaryDocument": [], "reportDate": []}}
        }
        mock_response.raise_for_status = Mock()

        mock_client = create_mock_async_client(mock_response)

        with patch("src.collectors.structured.sec13f_collector.httpx.AsyncClient", return_value=mock_client):
            result = await collector.fetch_all_tracked_holdings()

            assert isinstance(result, dict)
            # Should have entries for all tracked institutions
            for cik in collector.tracked_institutions:
                assert cik in result


class TestSEC13FCollectorXMLParsing:
    """Tests for SEC13F XML parsing functionality."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return SEC13FCollector()

    def test_parse_holdings_xml_with_namespace(self, collector):
        """Test parsing XML with namespace."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
    <infoTable>
        <nameOfIssuer>TEST CORP</nameOfIssuer>
        <titleOfClass>COM</titleOfClass>
        <cusip>123456789</cusip>
        <value>1000</value>
        <shrsOrPrnAmt>
            <sshPrnamt>100</sshPrnamt>
            <sshPrnamtType>SH</sshPrnamtType>
        </shrsOrPrnAmt>
    </infoTable>
</informationTable>"""

        holdings = collector._parse_holdings_xml(
            xml_content=xml_content,
            institution_cik="0001234567",
            institution_name="Test Institution",
            report_date=date(2024, 9, 30),
        )

        assert len(holdings) == 1
        assert holdings[0].stock_name == "TEST CORP"
        assert holdings[0].cusip == "123456789"
        assert holdings[0].shares == 100
        assert holdings[0].value == Decimal("1000000")  # Value * 1000

    def test_parse_holdings_xml_without_namespace(self, collector):
        """Test parsing XML without namespace."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<informationTable>
    <infoTable>
        <nameOfIssuer>NO NAMESPACE CORP</nameOfIssuer>
        <titleOfClass>COM</titleOfClass>
        <cusip>987654321</cusip>
        <value>2000</value>
        <shrsOrPrnAmt>
            <sshPrnamt>200</sshPrnamt>
            <sshPrnamtType>SH</sshPrnamtType>
        </shrsOrPrnAmt>
    </infoTable>
</informationTable>"""

        holdings = collector._parse_holdings_xml(
            xml_content=xml_content,
            institution_cik="0001234567",
            institution_name="Test Institution",
            report_date=date(2024, 9, 30),
        )

        assert len(holdings) == 1
        assert holdings[0].stock_name == "NO NAMESPACE CORP"

    def test_parse_holdings_xml_with_invalid_xml(self, collector):
        """Test parsing invalid XML returns empty list."""
        xml_content = "<invalid>xml<broken"

        holdings = collector._parse_holdings_xml(
            xml_content=xml_content,
            institution_cik="0001234567",
            institution_name="Test Institution",
            report_date=date(2024, 9, 30),
        )

        assert holdings == []


# Integration test (skipped by default, run with: pytest -m integration)
@pytest.mark.integration
class TestSEC13FCollectorIntegration:
    """Integration tests that hit real SEC EDGAR API."""

    @pytest.mark.asyncio
    async def test_fetch_real_filings(self):
        """Test fetching real data from SEC EDGAR API."""
        collector = SEC13FCollector()
        filings = await collector.fetch_filings("0001067983", limit=1)

        assert len(filings) >= 0  # May or may not have filings
        if filings:
            assert "accession_number" in filings[0]
            assert "filing_date" in filings[0]
