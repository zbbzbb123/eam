"""Crawlers for unstructured data sources."""
from src.collectors.crawlers.openinsider_crawler import (
    OpenInsiderCrawler,
    InsiderTradeData,
    TradeType,
)
from src.collectors.crawlers.jisilu_crawler import (
    JisiluCrawler,
    ETFPremiumData,
)

__all__ = [
    "OpenInsiderCrawler",
    "InsiderTradeData",
    "TradeType",
    "JisiluCrawler",
    "ETFPremiumData",
]
