"""Sector fund flow collector from EastMoney push2 API."""
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

PUSH2_URL = "https://push2his.eastmoney.com/api/qt/clist/get"
HTTP_TIMEOUT = httpx.Timeout(30.0)

# Field mapping for fund flow data
# f12=code, f14=name, f62=主力净流入, f66=超大单净流入, f72=大单净流入,
# f78=中单净流入, f84=小单净流入, f184=主力净占比
FIELDS = "f12,f14,f62,f66,f72,f78,f84,f184"


@dataclass
class SectorFlowData:
    """Fund flow data for a single sector."""

    code: str
    name: str
    main_net_inflow: Decimal      # 主力净流入 (超大单+大单)
    super_large_inflow: Decimal   # 超大单净流入
    large_inflow: Decimal         # 大单净流入
    medium_inflow: Decimal        # 中单净流入
    small_inflow: Decimal         # 小单净流入
    main_pct: Decimal             # 主力净占比 (%)


class SectorFlowCollector:
    """Collects sector-level fund flow data from EastMoney."""

    @property
    def name(self) -> str:
        return "sector_flow_collector"

    @property
    def source(self) -> str:
        return "eastmoney"

    def _to_decimal(self, value) -> Decimal:
        if value is None:
            return Decimal("0")
        return Decimal(str(value))

    def fetch_all(self) -> Dict[str, List[SectorFlowData]]:
        """Fetch sector fund flow data for industry and concept sectors.

        Returns:
            Dict with 'industry' and 'concept' keys mapping to lists of SectorFlowData.
        """
        result = {}
        # m:90+t:2 = industry sectors, m:90+t:3 = concept sectors
        for sector_type, fs_filter in [("industry", "m:90+t:2"), ("concept", "m:90+t:3")]:
            try:
                data = self._fetch_sector_flows(fs_filter)
                result[sector_type] = data
                logger.info(f"Fetched {len(data)} {sector_type} sector fund flows")
            except Exception as e:
                logger.error(f"Failed to fetch {sector_type} fund flows: {e}")
                result[sector_type] = []
        return result

    def _fetch_sector_flows(self, fs_filter: str) -> List[SectorFlowData]:
        params = {
            "pn": 1,
            "pz": 200,
            "fid": "f62",
            "po": 1,  # descending by main net inflow
            "fs": fs_filter,
            "fields": FIELDS,
        }
        resp = httpx.get(PUSH2_URL, params=params, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if data.get("rc") != 0 or not data.get("data"):
            return []

        diff = data["data"].get("diff", [])
        if isinstance(diff, dict):
            diff = list(diff.values())

        results = []
        for item in diff:
            try:
                results.append(SectorFlowData(
                    code=str(item.get("f12", "")),
                    name=str(item.get("f14", "")),
                    main_net_inflow=self._to_decimal(item.get("f62")),
                    super_large_inflow=self._to_decimal(item.get("f66")),
                    large_inflow=self._to_decimal(item.get("f72")),
                    medium_inflow=self._to_decimal(item.get("f78")),
                    small_inflow=self._to_decimal(item.get("f84")),
                    main_pct=self._to_decimal(item.get("f184")),
                ))
            except Exception as e:
                logger.warning(f"Skipping invalid sector flow row: {e}")
                continue

        return results
