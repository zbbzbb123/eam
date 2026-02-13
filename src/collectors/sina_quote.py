"""Sina Finance real-time quote fetcher for A-shares and HK stocks."""
import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

SINA_URL = "https://hq.sinajs.cn/list="
HEADERS = {"Referer": "https://finance.sina.com.cn"}


@dataclass
class SinaQuote:
    symbol: str
    name: str
    close: Decimal
    open: Optional[Decimal]
    high: Optional[Decimal]
    low: Optional[Decimal]
    volume: Optional[int]
    trade_date: date


def _to_sina_code(symbol: str, market: str) -> str:
    """Convert symbol+market to Sina code format."""
    if market == "CN":
        # Shanghai (sh): 60xxxx stocks, 68xxxx STAR, 5xxxxx ETF/funds, 11xxxx bonds
        # Shenzhen (sz): 00xxxx stocks, 30xxxx ChiNext, 159xxx ETF, 12xxxx bonds
        if symbol.startswith(("5", "6", "9", "110", "113")):
            return f"sh{symbol}"
        else:
            return f"sz{symbol}"
    elif market == "HK":
        return f"hk{symbol}"
    return symbol


def fetch_sina_quote(symbol: str, market: str) -> Optional[SinaQuote]:
    """Fetch latest quote from Sina Finance API.

    Args:
        symbol: Stock code (e.g. '512480', '01810')
        market: 'CN' or 'HK'

    Returns:
        SinaQuote or None if failed.
    """
    sina_code = _to_sina_code(symbol, market)

    try:
        r = httpx.get(f"{SINA_URL}{sina_code}", headers=HEADERS, timeout=10)
        r.raise_for_status()
        text = r.text.strip()

        if not text or '=""' in text:
            logger.warning("Empty Sina response for %s", sina_code)
            return None

        # Parse: var hq_str_xxxx="field1,field2,...";
        data_str = text.split('"')[1]
        if not data_str:
            return None

        fields = data_str.split(",")

        if market == "CN":
            return _parse_cn(symbol, fields)
        elif market == "HK":
            return _parse_hk(symbol, fields)

    except Exception as e:
        logger.warning("Sina quote error for %s/%s: %s", symbol, market, e)
        return None


def _parse_cn(symbol: str, fields: list) -> Optional[SinaQuote]:
    """Parse A-share Sina format.

    Fields: 名称,今开,昨收,最新价,最高,最低,...,日期,时间,...
    Index:  0     1    2    3     4   5       30   31
    """
    try:
        name = fields[0]
        current = Decimal(fields[3])
        if current <= 0:
            return None
        return SinaQuote(
            symbol=symbol,
            name=name,
            close=current,
            open=Decimal(fields[1]) if fields[1] else None,
            high=Decimal(fields[4]) if fields[4] else None,
            low=Decimal(fields[5]) if fields[5] else None,
            volume=int(float(fields[8])) if fields[8] else None,
            trade_date=date.fromisoformat(fields[30]),
        )
    except (IndexError, ValueError) as e:
        logger.warning("Failed to parse CN quote for %s: %s", symbol, e)
        return None


def _parse_hk(symbol: str, fields: list) -> Optional[SinaQuote]:
    """Parse HK stock Sina format.

    Fields: EN_NAME,CN_NAME,OPEN,PREV_CLOSE,HIGH,LOW,LAST,...,DATE
    Index:  0       1       2    3          4    5   6         17
    """
    try:
        name = fields[1]
        current = Decimal(fields[6])
        if current <= 0:
            return None
        # HK date format: 2026/01/30
        trade_date_str = fields[17].strip()
        trade_date = date.fromisoformat(trade_date_str.replace("/", "-"))
        return SinaQuote(
            symbol=symbol,
            name=name,
            close=current,
            open=Decimal(fields[2]) if fields[2] else None,
            high=Decimal(fields[4]) if fields[4] and float(fields[4]) > 0 else None,
            low=Decimal(fields[5]) if fields[5] and float(fields[5]) > 0 else None,
            volume=int(float(fields[11])) if len(fields) > 11 and fields[11] else None,
            trade_date=trade_date,
        )
    except (IndexError, ValueError) as e:
        logger.warning("Failed to parse HK quote for %s: %s", symbol, e)
        return None
