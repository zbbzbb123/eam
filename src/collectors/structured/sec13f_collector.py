"""SEC EDGAR 13F collector for institutional holdings data."""
import asyncio
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
import logging

import httpx

logger = logging.getLogger(__name__)

# SEC EDGAR API base URLs
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_number}"

# HTTP client timeout in seconds
HTTP_CLIENT_TIMEOUT = httpx.Timeout(60.0)

# SEC requires User-Agent header with contact information
SEC_USER_AGENT = "EAM Project contact@example.com"

# Default number of filings to fetch
DEFAULT_FILING_LIMIT = 10

# Tracked institutions (CIK -> Name)
TRACKED_INSTITUTIONS: Dict[str, str] = {
    "0001067983": "Berkshire Hathaway Inc",
    "0001818482": "ARK Investment Management LLC",
    "0001350694": "Bridgewater Associates, LP",
    "0001037389": "Renaissance Technologies LLC",
}

# XML namespace for 13F information table
NS_13F = {"ns": "http://www.sec.gov/edgar/document/thirteenf/informationtable"}


@dataclass
class InstitutionalHoldingData:
    """Data class for a single institutional holding from 13F filing."""

    institution_cik: str
    institution_name: str
    report_date: date
    cusip: str
    stock_name: str
    shares: int
    value: Decimal

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "institution_cik": self.institution_cik,
            "institution_name": self.institution_name,
            "report_date": self.report_date,
            "cusip": self.cusip,
            "stock_name": self.stock_name,
            "shares": self.shares,
            "value": self.value,
        }


class SEC13FCollector:
    """Collector for institutional holdings data from SEC EDGAR 13F filings."""

    def __init__(self):
        """Initialize the SEC 13F collector."""
        self._tracked_institutions = TRACKED_INSTITUTIONS.copy()

    @property
    def name(self) -> str:
        """Return collector name."""
        return "sec13f_collector"

    @property
    def source(self) -> str:
        """Return data source name."""
        return "sec_edgar"

    @property
    def tracked_institutions(self) -> Dict[str, str]:
        """Return dictionary of tracked institution CIKs and names."""
        return self._tracked_institutions

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for SEC EDGAR API requests."""
        return {
            "User-Agent": SEC_USER_AGENT,
            "Accept": "application/json",
        }

    def _format_cik(self, cik: str) -> str:
        """Format CIK to 10 digits with leading zeros."""
        return cik.lstrip("0").zfill(10)

    def _format_accession_for_url(self, accession_number: str) -> str:
        """Format accession number for URL (remove dashes)."""
        return accession_number.replace("-", "")

    async def fetch_filings(
        self,
        cik: str,
        limit: int = DEFAULT_FILING_LIMIT,
    ) -> List[Dict]:
        """
        Fetch recent 13F-HR filings for an institution.

        Args:
            cik: Institution CIK number (with or without leading zeros)
            limit: Maximum number of filings to return

        Returns:
            List of filing information dictionaries with keys:
            - accession_number
            - filing_date
            - form
            - primary_document
            - report_date

        Note:
            This method handles API errors gracefully and returns an empty
            list on error.
        """
        try:
            formatted_cik = self._format_cik(cik)
            url = SEC_SUBMISSIONS_URL.format(cik=formatted_cik)

            async with httpx.AsyncClient(
                timeout=HTTP_CLIENT_TIMEOUT,
                headers=self._get_headers(),
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            filings = []
            recent = data.get("filings", {}).get("recent", {})

            accession_numbers = recent.get("accessionNumber", [])
            filing_dates = recent.get("filingDate", [])
            forms = recent.get("form", [])
            primary_docs = recent.get("primaryDocument", [])
            report_dates = recent.get("reportDate", [])

            for i in range(len(accession_numbers)):
                if forms[i] == "13F-HR":
                    filings.append({
                        "accession_number": accession_numbers[i],
                        "filing_date": filing_dates[i],
                        "form": forms[i],
                        "primary_document": primary_docs[i],
                        "report_date": report_dates[i],
                    })

                    if len(filings) >= limit:
                        break

            return filings

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching filings for CIK {cik}: {e}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Network error fetching filings for CIK {cik}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching filings for CIK {cik}: {e}")
            return []

    async def fetch_holdings(
        self,
        cik: str,
        accession_number: str,
        report_date: str,
    ) -> List[InstitutionalHoldingData]:
        """
        Fetch holdings from a specific 13F filing.

        Args:
            cik: Institution CIK number
            accession_number: Filing accession number
            report_date: Report date in YYYY-MM-DD format

        Returns:
            List of InstitutionalHoldingData objects

        Note:
            This method handles API errors gracefully and returns an empty
            list on error.
        """
        try:
            formatted_cik = cik.lstrip("0")
            formatted_accession = self._format_accession_for_url(accession_number)

            # Try to find the information table XML file
            # Common patterns: infotable.xml, primary_doc.xml
            base_url = SEC_ARCHIVES_URL.format(
                cik=formatted_cik,
                accession_number=formatted_accession,
            )

            # Get institution name
            institution_name = self._tracked_institutions.get(
                cik, f"Institution CIK {cik}"
            )

            # Parse report date
            report_date_obj = date.fromisoformat(report_date)

            async with httpx.AsyncClient(
                timeout=HTTP_CLIENT_TIMEOUT,
                headers={
                    "User-Agent": SEC_USER_AGENT,
                    "Accept": "application/xml, text/xml",
                },
            ) as client:
                # Try to fetch the infotable.xml
                xml_url = f"{base_url}/infotable.xml"
                response = await client.get(xml_url)
                response.raise_for_status()
                xml_content = response.text

            return self._parse_holdings_xml(
                xml_content=xml_content,
                institution_cik=cik,
                institution_name=institution_name,
                report_date=report_date_obj,
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error fetching holdings for CIK {cik}, "
                f"accession {accession_number}: {e}"
            )
            return []
        except httpx.RequestError as e:
            logger.error(
                f"Network error fetching holdings for CIK {cik}, "
                f"accession {accession_number}: {e}"
            )
            return []
        except Exception as e:
            logger.error(
                f"Unexpected error fetching holdings for CIK {cik}, "
                f"accession {accession_number}: {e}"
            )
            return []

    def _parse_holdings_xml(
        self,
        xml_content: str,
        institution_cik: str,
        institution_name: str,
        report_date: date,
    ) -> List[InstitutionalHoldingData]:
        """
        Parse 13F holdings from XML content.

        Args:
            xml_content: Raw XML content from infotable.xml
            institution_cik: Institution CIK
            institution_name: Institution name
            report_date: Report date

        Returns:
            List of InstitutionalHoldingData objects
        """
        holdings = []

        try:
            root = ET.fromstring(xml_content)

            # Detect if namespace is used by checking root tag
            ns_prefix = ""
            if root.tag.startswith("{"):
                # Extract namespace from root tag
                ns_end = root.tag.find("}")
                ns_prefix = root.tag[: ns_end + 1]

            # Find all infoTable elements (holdings)
            info_tables = root.findall(f".//{ns_prefix}infoTable")

            for info_table in info_tables:
                try:
                    # Extract data using detected namespace prefix
                    name_elem = info_table.find(f"{ns_prefix}nameOfIssuer")
                    cusip_elem = info_table.find(f"{ns_prefix}cusip")
                    value_elem = info_table.find(f"{ns_prefix}value")
                    shares_elem = info_table.find(
                        f"{ns_prefix}shrsOrPrnAmt/{ns_prefix}sshPrnamt"
                    )

                    # Note: XML Element with no children evaluates to False
                    # in boolean context, so we must use explicit None check
                    if all([
                        name_elem is not None,
                        cusip_elem is not None,
                        value_elem is not None,
                        shares_elem is not None,
                    ]):
                        # Value in 13F is in thousands of dollars
                        value_thousands = int(value_elem.text or "0")
                        value_dollars = Decimal(str(value_thousands * 1000))

                        holding = InstitutionalHoldingData(
                            institution_cik=institution_cik,
                            institution_name=institution_name,
                            report_date=report_date,
                            cusip=cusip_elem.text or "",
                            stock_name=name_elem.text or "",
                            shares=int(shares_elem.text or "0"),
                            value=value_dollars,
                        )
                        holdings.append(holding)

                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping invalid holding entry: {e}")
                    continue

        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
            return []

        return holdings

    async def fetch_latest_holdings(
        self,
        cik: str,
    ) -> List[InstitutionalHoldingData]:
        """
        Fetch holdings from the most recent 13F filing for an institution.

        Args:
            cik: Institution CIK number

        Returns:
            List of InstitutionalHoldingData objects from the latest filing
        """
        filings = await self.fetch_filings(cik, limit=1)

        if not filings:
            logger.info(f"No 13F-HR filings found for CIK {cik}")
            return []

        latest_filing = filings[0]
        return await self.fetch_holdings(
            cik=cik,
            accession_number=latest_filing["accession_number"],
            report_date=latest_filing["report_date"],
        )

    async def fetch_all_tracked_holdings(
        self,
    ) -> Dict[str, List[InstitutionalHoldingData]]:
        """
        Fetch latest holdings for all tracked institutions.

        Returns:
            Dictionary mapping CIK to list of holdings
        """
        tasks = [
            self.fetch_latest_holdings(cik)
            for cik in self._tracked_institutions.keys()
        ]
        results = await asyncio.gather(*tasks)

        return dict(zip(self._tracked_institutions.keys(), results))
