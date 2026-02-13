"""Real-time quote fetcher for A-shares and HK stocks.

Uses East Money push2 API as primary source (works from cloud servers).
Falls back to Sina Finance API if East Money fails.
"""
import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


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


# ===== East Money (primary) =====

_EM_URL = "https://push2.eastmoney.com/api/qt/stock/get"

def _to_em_secid(symbol: str, market: str) -> str:
    """Convert symbol+market to East Money secid format."""
    if market == "CN":
        # 1=SH, 0=SZ
        if symbol.startswith(("5", "6", "9", "110", "113")):
            return f"1.{symbol}"
        else:
            return f"0.{symbol}"
    elif market == "HK":
        return f"116.{symbol}"
    return symbol


def _fetch_em_quote(symbol: str, market: str) -> Optional[SinaQuote]:
    """Fetch quote from East Money push2 API."""
    secid = _to_em_secid(symbol, market)
    params = {
        "secid": secid,
        "fields": "f43,f44,f45,f46,f47,f48,f57,f58,f60,f170,f171",
        "ut": "fa5fd1943c7b386f172d6893dbbd1",
    }
    try:
        r = httpx.get(_EM_URL, params=params, headers={"User-Agent": _UA}, timeout=10)
        r.raise_for_status()
        data = r.json().get("data")
        if not data:
            return None

        # f43=最新价(分), f44=最高(分), f45=最低(分), f46=今开(分)
        # f47=成交量, f48=成交额, f57=代码, f58=名称, f60=昨收(分)
        # f170=涨跌幅(%), f171=涨跌额
        price = data.get("f43")
        if price is None or price == "-":
            return None

        # East Money returns prices in cents for CN, actual price for HK
        divisor = 100 if market == "CN" else 1000
        close = Decimal(str(price)) / divisor
        if close <= 0:
            return None

        open_p = data.get("f46")
        high_p = data.get("f44")
        low_p = data.get("f45")
        vol = data.get("f47")

        today = date.today()

        return SinaQuote(
            symbol=symbol,
            name=data.get("f58", ""),
            close=close,
            open=Decimal(str(open_p)) / divisor if open_p and open_p != "-" else None,
            high=Decimal(str(high_p)) / divisor if high_p and high_p != "-" else None,
            low=Decimal(str(low_p)) / divisor if low_p and low_p != "-" else None,
            volume=int(vol) if vol and vol != "-" else None,
            trade_date=today,
        )
    except Exception as e:
        logger.debug("East Money quote error for %s/%s: %s", symbol, market, e)
        return None


# ===== Sina Finance (fallback) =====

_SINA_URL = "https://hq.sinajs.cn/list="
_SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": _UA,
}


def _to_sina_code(symbol: str, market: str) -> str:
    if market == "CN":
        if symbol.startswith(("5", "6", "9", "110", "113")):
            return f"sh{symbol}"
        else:
            return f"sz{symbol}"
    elif market == "HK":
        return f"hk{symbol}"
    return symbol


def _fetch_sina_quote(symbol: str, market: str) -> Optional[SinaQuote]:
    """Fetch quote from Sina Finance API."""
    sina_code = _to_sina_code(symbol, market)
    try:
        r = httpx.get(f"{_SINA_URL}{sina_code}", headers=_SINA_HEADERS, timeout=10)
        r.raise_for_status()
        text = r.text.strip()
        if not text or '=""' in text:
            return None
        data_str = text.split('"')[1]
        if not data_str:
            return None
        fields = data_str.split(",")
        if market == "CN":
            return _parse_cn(symbol, fields)
        elif market == "HK":
            return _parse_hk(symbol, fields)
    except Exception as e:
        logger.debug("Sina quote error for %s/%s: %s", symbol, market, e)
        return None


def _parse_cn(symbol: str, fields: list) -> Optional[SinaQuote]:
    try:
        name = fields[0]
        current = Decimal(fields[3])
        if current <= 0:
            return None
        return SinaQuote(
            symbol=symbol, name=name, close=current,
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
    try:
        name = fields[1]
        current = Decimal(fields[6])
        if current <= 0:
            return None
        trade_date_str = fields[17].strip()
        trade_date_val = date.fromisoformat(trade_date_str.replace("/", "-"))
        return SinaQuote(
            symbol=symbol, name=name, close=current,
            open=Decimal(fields[2]) if fields[2] else None,
            high=Decimal(fields[4]) if fields[4] and float(fields[4]) > 0 else None,
            low=Decimal(fields[5]) if fields[5] and float(fields[5]) > 0 else None,
            volume=int(float(fields[11])) if len(fields) > 11 and fields[11] else None,
            trade_date=trade_date_val,
        )
    except (IndexError, ValueError) as e:
        logger.warning("Failed to parse HK quote for %s: %s", symbol, e)
        return None


# ===== Public API =====

def fetch_sina_quote(symbol: str, market: str) -> Optional[SinaQuote]:
    """Fetch latest quote. Tries East Money first, falls back to Sina.

    Args:
        symbol: Stock code (e.g. '512480', '01810')
        market: 'CN' or 'HK'

    Returns:
        SinaQuote or None if all sources failed.
    """
    # Try East Money first (works from cloud servers)
    result = _fetch_em_quote(symbol, market)
    if result:
        return result

    # Fallback to Sina (works from residential IPs)
    result = _fetch_sina_quote(symbol, market)
    if result:
        return result

    logger.warning("All quote sources failed for %s/%s", symbol, market)
    return None
