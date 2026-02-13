"""A-share market breadth (advance/decline) collector from EastMoney."""
import logging
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

PUSH2_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
HTTP_TIMEOUT = httpx.Timeout(30.0)

# Major A-share indices
INDICES = {
    "1.000001": "上证指数",
    "0.399001": "深证成指",
    "0.399006": "创业板指",
}


@dataclass
class MarketBreadthData:
    """Market breadth snapshot for an index."""

    index_code: str
    index_name: str
    close: float
    change_pct: float
    advancing: int     # 上涨家数
    declining: int     # 下跌家数
    unchanged: int     # 平盘家数


class MarketBreadthCollector:
    """Collects A-share market breadth data (advance/decline counts)."""

    @property
    def name(self) -> str:
        return "market_breadth_collector"

    @property
    def source(self) -> str:
        return "eastmoney"

    def fetch_all(self) -> List[MarketBreadthData]:
        """Fetch market breadth for major A-share indices.

        Returns:
            List of MarketBreadthData for each tracked index.
        """
        try:
            secids = ",".join(INDICES.keys())
            params = {
                "fltt": 2,
                "fields": "f1,f2,f3,f4,f12,f13,f14,f104,f105,f106",
                "secids": secids,
            }
            resp = httpx.get(PUSH2_URL, params=params, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            if data.get("rc") != 0 or not data.get("data"):
                logger.warning(f"Market breadth API returned rc={data.get('rc')}")
                return []

            results = []
            for item in data["data"].get("diff", []):
                try:
                    results.append(MarketBreadthData(
                        index_code=str(item.get("f12", "")),
                        index_name=str(item.get("f14", "")),
                        close=float(item.get("f2", 0)),
                        change_pct=float(item.get("f3", 0)),
                        advancing=int(item.get("f104", 0)),
                        declining=int(item.get("f105", 0)),
                        unchanged=int(item.get("f106", 0)),
                    ))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping invalid breadth row: {e}")
                    continue

            return results

        except Exception as e:
            logger.error(f"Error fetching market breadth: {e}")
            return []
