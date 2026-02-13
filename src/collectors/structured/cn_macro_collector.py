"""Chinese macroeconomic data collector using EastMoney datacenter API."""
import asyncio
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
import logging

import httpx

logger = logging.getLogger(__name__)

# EastMoney datacenter API base URL
EASTMONEY_API_BASE_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

# HTTP client timeout in seconds
HTTP_CLIENT_TIMEOUT = httpx.Timeout(30.0)

# Default page size for API requests
DEFAULT_PAGE_SIZE = 12

# Report name constants
REPORT_PMI = "RPT_ECONOMY_PMI"
REPORT_CPI = "RPT_ECONOMY_CPI"
REPORT_M2 = "RPT_ECONOMY_CURRENCY_SUPPLY"
REPORT_RMB_LOAN = "RPT_ECONOMY_RMB_LOAN"

# Chinamoney Shibor API
CHINAMONEY_SHIBOR_URL = "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-shibor/ShiborHis"

# Shibor tenor mapping
SHIBOR_TENORS = {
    "ON": "shibor_on",
    "1W": "shibor_1w",
    "1M": "shibor_1m",
    "3M": "shibor_3m",
    "6M": "shibor_6m",
    "9M": "shibor_9m",
    "1Y": "shibor_1y",
}


@dataclass
class CnMacroData:
    """Data class for a single Chinese macro data observation."""

    indicator: str
    date: date
    value: Decimal
    yoy_change: Optional[Decimal]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "indicator": self.indicator,
            "date": self.date,
            "value": self.value,
            "yoy_change": self.yoy_change,
        }


class CnMacroCollector:
    """Collector for Chinese macroeconomic data from EastMoney datacenter API."""

    def __init__(self):
        """Initialize the Chinese macro collector."""
        pass

    @property
    def name(self) -> str:
        """Return collector name."""
        return "cn_macro_collector"

    @property
    def source(self) -> str:
        """Return data source name."""
        return "eastmoney"

    async def _fetch_report(
        self,
        report_name: str,
        columns: str,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> List[dict]:
        """
        Fetch data from EastMoney datacenter API.

        Args:
            report_name: The report identifier (e.g., RPT_ECONOMY_PMI)
            columns: Comma-separated column names to retrieve
            page_size: Number of records to fetch

        Returns:
            List of data dictionaries from the API response

        Raises:
            Returns empty list on any error.
        """
        try:
            params = {
                "reportName": report_name,
                "columns": columns,
                "pageSize": page_size,
                "sortColumns": "REPORT_DATE",
                "sortTypes": "-1",
            }

            async with httpx.AsyncClient(timeout=HTTP_CLIENT_TIMEOUT) as client:
                response = await client.get(EASTMONEY_API_BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

            result = data.get("result", {})
            if result is None:
                logger.warning(f"No result in response for report {report_name}")
                return []

            rows = result.get("data", [])
            if rows is None:
                return []

            return rows

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching {report_name}: {e}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Network error fetching {report_name}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching {report_name}: {e}")
            return []

    @staticmethod
    def _parse_date(date_str: str) -> date:
        """Parse date string from API response (e.g., '2025-01-31 00:00:00')."""
        return date.fromisoformat(date_str.split(" ")[0])

    @staticmethod
    def _to_decimal(value) -> Optional[Decimal]:
        """Safely convert a value to Decimal."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None

    async def fetch_pmi(self) -> List[CnMacroData]:
        """
        Fetch PMI (Purchasing Managers' Index) data.

        Returns:
            List of CnMacroData with manufacturing and non-manufacturing PMI.
        """
        columns = "REPORT_DATE,MAKE_INDEX,NMAKE_INDEX"
        rows = await self._fetch_report(REPORT_PMI, columns)

        data_points = []
        for row in rows:
            try:
                report_date = self._parse_date(row["REPORT_DATE"])

                make_index = self._to_decimal(row.get("MAKE_INDEX"))
                if make_index is not None:
                    data_points.append(CnMacroData(
                        indicator="manufacturing_pmi",
                        date=report_date,
                        value=make_index,
                        yoy_change=None,
                    ))

                nmake_index = self._to_decimal(row.get("NMAKE_INDEX"))
                if nmake_index is not None:
                    data_points.append(CnMacroData(
                        indicator="non_manufacturing_pmi",
                        date=report_date,
                        value=nmake_index,
                        yoy_change=None,
                    ))

            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping invalid PMI row: {e}")
                continue

        return data_points

    async def fetch_cpi(self) -> List[CnMacroData]:
        """
        Fetch CPI (Consumer Price Index) data.

        Returns:
            List of CnMacroData with CPI year-over-year and month-over-month.
        """
        columns = "REPORT_DATE,NATIONAL_SAME,NATIONAL_BASE,NATIONAL_SEQUENTIAL"
        rows = await self._fetch_report(REPORT_CPI, columns)

        data_points = []
        for row in rows:
            try:
                report_date = self._parse_date(row["REPORT_DATE"])

                national_same = self._to_decimal(row.get("NATIONAL_SAME"))
                national_sequential = self._to_decimal(row.get("NATIONAL_SEQUENTIAL"))

                if national_same is not None:
                    data_points.append(CnMacroData(
                        indicator="cpi_yoy",
                        date=report_date,
                        value=national_same,
                        yoy_change=national_same,
                    ))

                if national_sequential is not None:
                    data_points.append(CnMacroData(
                        indicator="cpi_mom",
                        date=report_date,
                        value=national_sequential,
                        yoy_change=None,
                    ))

            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping invalid CPI row: {e}")
                continue

        return data_points

    async def fetch_m2(self) -> List[CnMacroData]:
        """
        Fetch M2 money supply data.

        Returns:
            List of CnMacroData with M2 balance and year-over-year growth.
        """
        columns = "REPORT_DATE,BASIC_CURRENCY,BASIC_CURRENCY_SAME,BASIC_CURRENCY_SEQUENTIAL"
        rows = await self._fetch_report(REPORT_M2, columns)

        data_points = []
        for row in rows:
            try:
                report_date = self._parse_date(row["REPORT_DATE"])

                basic_currency = self._to_decimal(row.get("BASIC_CURRENCY"))
                basic_currency_same = self._to_decimal(row.get("BASIC_CURRENCY_SAME"))

                if basic_currency is not None:
                    data_points.append(CnMacroData(
                        indicator="m2_balance",
                        date=report_date,
                        value=basic_currency,
                        yoy_change=basic_currency_same,
                    ))

            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping invalid M2 row: {e}")
                continue

        return data_points

    async def fetch_shibor(self) -> List[CnMacroData]:
        """Fetch Shibor (Shanghai Interbank Offered Rate) data from Chinamoney.

        Returns:
            List of CnMacroData with Shibor rates for various tenors.
        """
        try:
            params = {
                "lang": "CN",
                "pageSize": 10,
                "pageNo": 1,
            }
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            }
            async with httpx.AsyncClient(timeout=HTTP_CLIENT_TIMEOUT) as client:
                response = await client.get(
                    CHINAMONEY_SHIBOR_URL, params=params, headers=headers,
                )
                response.raise_for_status()
                data = response.json()

            records = data.get("records", [])
            if not records:
                logger.warning("No Shibor records returned")
                return []

            data_points = []
            for record in records:
                try:
                    show_date_str = record.get("showDateCN", "")
                    if not show_date_str:
                        continue
                    # Format: "2026-01-23"
                    record_date = date.fromisoformat(show_date_str)

                    for tenor_key, indicator_name in SHIBOR_TENORS.items():
                        value_str = record.get(tenor_key)
                        if value_str is None or value_str == "":
                            continue
                        value = self._to_decimal(value_str)
                        if value is not None:
                            data_points.append(CnMacroData(
                                indicator=indicator_name,
                                date=record_date,
                                value=value,
                                yoy_change=None,
                            ))
                except (ValueError, KeyError) as e:
                    logger.warning(f"Skipping invalid Shibor row: {e}")
                    continue

            return data_points

        except Exception as e:
            logger.error(f"Error fetching Shibor data: {e}")
            return []

    async def fetch_rmb_loan(self) -> List[CnMacroData]:
        """Fetch new RMB loan (新增人民币贷款) data from EastMoney.

        Returns:
            List of CnMacroData with monthly new RMB loan amounts.
        """
        columns = "REPORT_DATE,RMB_LOAN,RMB_LOAN_SAME,RMB_LOAN_SEQUENTIAL"
        rows = await self._fetch_report(REPORT_RMB_LOAN, columns)

        data_points = []
        for row in rows:
            try:
                report_date = self._parse_date(row["REPORT_DATE"])

                loan_amount = self._to_decimal(row.get("RMB_LOAN"))
                loan_yoy = self._to_decimal(row.get("RMB_LOAN_SAME"))

                if loan_amount is not None:
                    data_points.append(CnMacroData(
                        indicator="rmb_new_loan",
                        date=report_date,
                        value=loan_amount,
                        yoy_change=loan_yoy,
                    ))
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping invalid RMB loan row: {e}")
                continue

        return data_points

    async def fetch_all(self) -> Dict[str, List[CnMacroData]]:
        """
        Fetch all Chinese macro indicators concurrently.

        Returns:
            Dictionary mapping indicator category to list of CnMacroData objects.
        """
        pmi_task, cpi_task, m2_task, shibor_task, loan_task = await asyncio.gather(
            self.fetch_pmi(),
            self.fetch_cpi(),
            self.fetch_m2(),
            self.fetch_shibor(),
            self.fetch_rmb_loan(),
        )

        return {
            "pmi": pmi_task,
            "cpi": cpi_task,
            "m2": m2_task,
            "shibor": shibor_task,
            "rmb_loan": loan_task,
        }
