"""Automatic CGG risk classification for holdings."""
from __future__ import annotations

from typing import Optional

from src.db.models import AssetType, Market, Tier


LARGE_CAP_SYMBOLS = {
    # US mega-cap AI infrastructure and application platforms.
    "AAPL", "MSFT", "NVDA", "GOOG", "GOOGL", "AMZN", "META", "TSLA",
    "AVGO", "AMD", "ORCL", "CRM", "IBM", "NFLX", "TSM", "ASML", "ADBE",
    # China/HK large platform companies.
    "BABA", "BIDU", "JD", "PDD", "TCEHY", "TME", "TCOM", "NTES",
    "00700", "0700", "700",      # Tencent
    "09988", "9988",             # Alibaba HK
    "09888", "9888",             # Baidu HK
    "09618", "9618",             # JD HK
    "03690", "3690",             # Meituan
    "01810", "1810",             # Xiaomi
    "01024", "1024",             # Kuaishou
    "09866", "9866",             # NIO HK
}

CN_ETF_PREFIXES = ("15", "16", "50", "51", "52", "56", "58")
CASH_SYMBOLS = {"CASH", "CNY", "USD", "HKD"}


def _normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper().split(".")[0]


def _is_etf(symbol: str, market: Market, asset_type: AssetType, strategy_sub_bucket: Optional[str]) -> bool:
    if asset_type == AssetType.ETF:
        return True

    sub_bucket = (strategy_sub_bucket or "").upper()
    if "ETF" in sub_bucket:
        return True

    normalized = _normalize_symbol(symbol)
    return market == Market.CN and normalized.startswith(CN_ETF_PREFIXES)


def derive_cgg_tier(
    symbol: str,
    market: Market,
    asset_type: AssetType,
    strategy_sub_bucket: Optional[str] = None,
) -> Tier:
    """Derive Core/Growth/Gamble risk lens from asset type and symbol.

    Rule:
    - ETF and cash positions are Core.
    - Large platform/mega-cap stocks are Growth.
    - Other individual stocks are Gamble.
    """
    normalized = _normalize_symbol(symbol)

    if asset_type == AssetType.CASH or normalized in CASH_SYMBOLS:
        return Tier.CORE
    if _is_etf(symbol, market, asset_type, strategy_sub_bucket):
        return Tier.CORE
    if normalized in LARGE_CAP_SYMBOLS:
        return Tier.GROWTH
    return Tier.GAMBLE
