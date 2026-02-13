"""Report generator service — creates and stores daily/weekly reports."""
import ast
import asyncio
import json
import logging
import re
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any

from sqlalchemy import desc, func as sa_func
from sqlalchemy.orm import Session

from src.db.models import (
    Holding, HoldingStatus, Market, Tier, DailyQuote, Signal, SignalSeverity,
    Watchlist,
)
from src.db.models_market_data import (
    GeneratedReport, MarketIndicatorSnapshot, FundNavSnapshot,
    FundamentalSnapshot, NorthboundFlow, NorthboundHolding,
    SectorSnapshot, SectorFlowSnapshot, MarketBreadthSnapshot,
    IndexValuationSnapshot, MacroData, CnMacroRecord, YieldSpreadRecord,
)
from src.services.llm_client import LLMClient, ModelChoice, LLMError

logger = logging.getLogger(__name__)

# Tier allocation targets (same as portfolio_health.py)
TIER_TARGETS = {
    Tier.STABLE: Decimal("0.40"),
    Tier.MEDIUM: Decimal("0.30"),
    Tier.GAMBLE: Decimal("0.30"),
}

HKD_CNY_RATE = Decimal("0.93")

# Theme mapping (same as portfolio_health.py)
THEME_MAP = {
    "512480": "半导体", "159682": "电池/新能源", "159875": "新能源",
    "516560": "养老", "BABA": "美股科技", "QQQ": "美股科技",
    "GOOG": "美股科技", "01810": "港股科技", "CASH": "现金",
}

# Opportunity detection thresholds (from watchlist_analyzer.py)
PE_CHEAP = 25
PULLBACK_THRESHOLD = Decimal("-0.10")
GROWTH_OUTSTANDING_VALUE = Decimal("0.25")
OUTSTANDING_PE_CAP = 35
NEAR_TARGET_THRESHOLD = Decimal("0.05")
LOOKBACK_DAYS = 30

DAILY_HOLDING_SYSTEM_PROMPT = """你是一位专业投资顾问。请对以下持仓进行简要点评。

要求严格按JSON格式回复，不要包含任何其他文字：
{
  "ai_comment": "2-3句话的结论+简要理由，结合仓位占比给出建议",
  "action": "hold/add/reduce/sell 之一",
  "ai_detail": "详细分析报告，markdown格式，包含：\\n## 基本面\\n...\\n## 技术面\\n...\\n## 催化剂\\n...\\n## 风险点\\n..."
}"""

DAILY_SUMMARY_SYSTEM_PROMPT = """你是一位专业投资顾问。根据以下持仓数据，生成一句话总结（30字以内），概括今日组合整体表现和需要关注的重点。只返回总结文字，不要任何其他格式。"""

OPPORTUNITY_SYSTEM_PROMPT = """你是一位专业投资顾问。分析以下标的的投资机会。

要求严格按JSON格式回复：
{
  "reason": "1-2句话说明机会原因",
  "detail": "markdown格式详细分析",
  "timeframe": "长期 或 短期",
  "signal_type": "超跌反弹/估值低位/资金流入/技术突破/高成长低估值 之一"
}"""

WEEKLY_HOLDING_SYSTEM_PROMPT = """你是一位专业投资顾问，进行中长期持仓分析。

要求严格按JSON格式回复：
{
  "ai_comment": "2-3句话的中长期观点，持仓逻辑是否还成立，仓位建议",
  "action": "hold/add/reduce/sell 之一",
  "ai_detail": "详细分析报告，markdown格式，包含：\\n## 持仓逻辑回顾\\n...\\n## 中期催化剂\\n...\\n## 风险因素\\n...\\n## 仓位建议\\n..."
}"""

WEEKLY_SUMMARY_SYSTEM_PROMPT = """你是一位专业投资顾问。根据以下本周市场和持仓数据，生成一段总结（100字以内），概括本周市场关键变化和持仓整体表现。只返回总结文字，不要任何其他格式。"""


# ======================================================================
# Module-level shared helpers
# ======================================================================

def _symbol_to_ts_code(symbol: str) -> str:
    """Convert a 6-digit CN symbol to TuShare ts_code format."""
    if symbol.startswith(("5", "6")):
        return f"{symbol}.SH"
    return f"{symbol}.SZ"


def _is_cn_etf(symbol: str) -> bool:
    """Check if symbol looks like a 6-digit CN ETF code."""
    return symbol.isdigit() and len(symbol) == 6


def _strip_markdown_fences(text: str) -> str:
    """Strip markdown code fences from LLM response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]).strip()
    return text


def _parse_llm_json(text: str) -> dict:
    """Parse JSON from LLM response, tolerating common LLM quirks."""
    text = _strip_markdown_fences(text)
    # Extract JSON object if surrounded by other text
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        text = match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fix trailing commas
    fixed = re.sub(r',\s*([}\]])', r'\1', text)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    # LLM may return Python dict literal with single quotes — use ast.literal_eval
    try:
        result = ast.literal_eval(text)
        if isinstance(result, dict):
            return result
    except (ValueError, SyntaxError):
        pass
    # Last resort: try ast on trailing-comma-fixed version
    result = ast.literal_eval(fixed)
    if isinstance(result, dict):
        return result
    raise json.JSONDecodeError("Cannot parse LLM response as JSON", text, 0)


def _get_usd_cny_rate_static(db: Session) -> Decimal:
    """Get latest USD/CNY rate from MarketIndicatorSnapshot."""
    row = (
        db.query(MarketIndicatorSnapshot)
        .filter(MarketIndicatorSnapshot.symbol == "CNY=X")
        .order_by(desc(MarketIndicatorSnapshot.date))
        .first()
    )
    if row and row.value:
        return Decimal(str(row.value))
    return Decimal("7.25")  # sensible fallback


def _get_latest_price_cn_etf_static(db: Session, symbol: str) -> Optional[Decimal]:
    """Try FundNavSnapshot first, then DailyQuote for CN ETFs."""
    ts_code = _symbol_to_ts_code(symbol)
    nav = (
        db.query(FundNavSnapshot)
        .filter(FundNavSnapshot.ts_code == ts_code)
        .order_by(desc(FundNavSnapshot.nav_date))
        .first()
    )
    if nav and nav.unit_nav:
        return Decimal(str(nav.unit_nav))

    quote = (
        db.query(DailyQuote)
        .filter(
            DailyQuote.symbol == symbol,
            DailyQuote.market == Market.CN,
        )
        .order_by(desc(DailyQuote.trade_date))
        .first()
    )
    if quote and quote.close:
        return Decimal(str(quote.close))

    return None


def _get_latest_price_static(db: Session, holding: Holding) -> Decimal:
    """Return latest price for a holding. Fallback to avg_cost."""
    if holding.symbol == "CASH":
        return Decimal("1")

    if holding.market == Market.CN and _is_cn_etf(holding.symbol):
        price = _get_latest_price_cn_etf_static(db, holding.symbol)
        if price is not None:
            return price

    quote = (
        db.query(DailyQuote)
        .filter(
            DailyQuote.symbol == holding.symbol,
            DailyQuote.market == holding.market,
        )
        .order_by(desc(DailyQuote.trade_date))
        .first()
    )
    if quote and quote.close:
        return Decimal(str(quote.close))

    return Decimal(str(holding.avg_cost))


def _to_cny_static(value: Decimal, market: Market, symbol: str, usd_cny: Decimal) -> Decimal:
    """Convert a value in local currency to CNY."""
    if symbol == "CASH" or market == Market.CN:
        return value
    if market == Market.US:
        return value * usd_cny
    if market == Market.HK:
        return value * HKD_CNY_RATE
    return value


def _get_stock_name_static(db: Session, symbol: str, market: Market) -> str:
    """Get stock name from FundamentalSnapshot or fallback to THEME_MAP/symbol."""
    if symbol == "CASH":
        return "现金"

    market_value = market.value if isinstance(market, Market) else market
    fundamental = (
        db.query(FundamentalSnapshot)
        .filter(
            FundamentalSnapshot.symbol == symbol,
            FundamentalSnapshot.market == market_value,
        )
        .order_by(FundamentalSnapshot.snapshot_date.desc())
        .first()
    )
    if fundamental and fundamental.name:
        return fundamental.name

    return THEME_MAP.get(symbol, symbol)


def _get_latest_fundamental_static(
    db: Session, symbol: str, market_value: str
) -> Optional[FundamentalSnapshot]:
    """Get the latest fundamental snapshot for a symbol."""
    return (
        db.query(FundamentalSnapshot)
        .filter(
            FundamentalSnapshot.symbol == symbol,
            FundamentalSnapshot.market == market_value,
        )
        .order_by(FundamentalSnapshot.snapshot_date.desc())
        .first()
    )


def _get_recent_quotes_static(
    db: Session, symbol: str, market: Market
) -> List[DailyQuote]:
    """Get recent quotes (last 30 days) sorted ascending by date."""
    since = date.today() - timedelta(days=LOOKBACK_DAYS)
    return (
        db.query(DailyQuote)
        .filter(
            DailyQuote.symbol == symbol,
            DailyQuote.market == market,
            DailyQuote.trade_date >= since,
        )
        .order_by(DailyQuote.trade_date.asc())
        .all()
    )


def _calc_30d_change(quotes: List[DailyQuote]) -> Optional[float]:
    """Calculate 30-day price change percentage."""
    if len(quotes) < 2:
        return None
    oldest_close = quotes[0].close
    newest_close = quotes[-1].close
    if oldest_close is None or newest_close is None or oldest_close == 0:
        return None
    return float((newest_close - oldest_close) / oldest_close)


def _detect_opportunity(
    pe: Optional[float],
    revenue_growth: Optional[float],
    change_30d: Optional[float],
    upside: Optional[float],
) -> List[str]:
    """Detect opportunity signals. Returns signal text list."""
    signals: List[str] = []

    if change_30d is not None and change_30d < float(PULLBACK_THRESHOLD):
        signals.append("回调关注")

    if pe is not None and 0 < pe < PE_CHEAP:
        signals.append("估值合理")

    if (
        revenue_growth is not None
        and pe is not None
        and revenue_growth > float(GROWTH_OUTSTANDING_VALUE)
        and 0 < pe < OUTSTANDING_PE_CAP
    ):
        signals.append("性价比突出")

    if upside is not None and abs(upside) <= float(NEAR_TARGET_THRESHOLD):
        signals.append("接近目标价")

    return signals


def _scan_opportunities_static(
    db: Session, llm: LLMClient
) -> List[Dict[str, Any]]:
    """Scan watchlist items for investment opportunities."""
    watchlist_items = db.query(Watchlist).all()
    if not watchlist_items:
        return []

    opportunities: List[Dict[str, Any]] = []

    for item in watchlist_items:
        market_value = item.market.value if isinstance(item.market, Market) else item.market
        fundamental = _get_latest_fundamental_static(db, item.symbol, market_value)

        # Get 60-day quotes for more comprehensive analysis
        quotes_60d = _get_quotes_for_period(db, item.symbol, item.market, 60)

        # Current price
        price = None
        if quotes_60d and quotes_60d[-1].close is not None:
            price = float(quotes_60d[-1].close)

        # PE
        pe = float(fundamental.pe_ratio) if fundamental and fundamental.pe_ratio else None

        # Revenue growth
        revenue_growth = (
            float(fundamental.revenue_growth)
            if fundamental and fundamental.revenue_growth is not None
            else None
        )

        # 30d change (use same function logic)
        change_30d = None
        if len(quotes_60d) >= 20:
            oldest_idx = max(0, len(quotes_60d) - 30)
            oldest = quotes_60d[oldest_idx].close
            newest = quotes_60d[-1].close
            if oldest and newest and oldest != 0:
                change_30d = float((newest - oldest) / oldest)

        # Target price / upside
        target_price = float(fundamental.target_price) if fundamental and fundamental.target_price else None
        upside = None
        if price and price > 0 and target_price:
            upside = (target_price - price) / price

        # Detect opportunity signals
        opp_signals = _detect_opportunity(pe, revenue_growth, change_30d, upside)

        if not opp_signals:
            continue

        name = fundamental.name if fundamental and fundamental.name else item.symbol

        # === Enhanced data collection for AI ===

        # Technical indicators
        change_5d = _calc_price_change(quotes_60d, 5)
        change_20d = _calc_price_change(quotes_60d, 20)
        ma20 = _calc_moving_average(quotes_60d, 20)
        ma60 = _calc_moving_average(quotes_60d, 60)
        volume_change = _calc_volume_change(quotes_60d)
        high_60d, low_60d = _get_high_low_60d(quotes_60d)

        # PE percentile
        pe_percentile = None
        if pe and pe > 0:
            pe_percentile = _get_pe_percentile(db, item.symbol, market_value, pe)

        # PB ratio
        pb = float(fundamental.pb_ratio) if fundamental and fundamental.pb_ratio else None

        # Analyst rating
        analyst_rating = fundamental.analyst_rating if fundamental else None

        # Sector data
        sector_name = item.theme  # Use watchlist theme as sector proxy
        sector_perf = _get_sector_performance_static(db, sector_name) if sector_name else None
        sector_flow = _get_sector_flow_static(db, sector_name, days=14) if sector_name else None

        # Northbound holding (for A-shares)
        nb_holding = None
        if item.market == Market.CN:
            nb_holding = _get_northbound_holding_static(db, item.symbol, days=28)

        # Pack enhanced data
        enhanced_data = {
            "change_5d": change_5d,
            "change_20d": change_20d,
            "ma20": ma20,
            "ma60": ma60,
            "volume_change": volume_change,
            "high_60d": high_60d,
            "low_60d": low_60d,
            "pe_percentile": pe_percentile,
            "pb": pb,
            "analyst_rating": analyst_rating,
            "sector_perf": sector_perf,
            "sector_flow": sector_flow,
            "nb_holding": nb_holding,
        }

        opp_entry: Dict[str, Any] = {
            "symbol": item.symbol,
            "name": name,
            "market": market_value,
            "signal_type": ", ".join(opp_signals),
            "timeframe": "长期",
            "reason": "",
            "detail": "",
            "target_price": target_price,
            "current_price": price,
        }

        # Try to enrich with AI
        ai_result = _get_opportunity_ai_static(
            llm, opp_entry, item, fundamental, pe, revenue_growth, change_30d, opp_signals,
            enhanced_data
        )
        if ai_result:
            opp_entry["reason"] = ai_result.get("reason", "")
            opp_entry["detail"] = ai_result.get("detail", "")
            opp_entry["timeframe"] = ai_result.get("timeframe", "长期")
            ai_signal_type = ai_result.get("signal_type", "")
            if ai_signal_type:
                opp_entry["signal_type"] = ai_signal_type

        opportunities.append(opp_entry)

    return opportunities


def _get_opportunity_ai_static(
    llm: LLMClient,
    opp_entry: Dict[str, Any],
    item: Watchlist,
    fundamental: Optional[FundamentalSnapshot],
    pe: Optional[float],
    revenue_growth: Optional[float],
    change_30d: Optional[float],
    opp_signals: List[str],
    enhanced_data: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, str]]:
    """Call LLM for opportunity analysis. Returns parsed dict or None."""
    enhanced = enhanced_data or {}
    price = opp_entry.get("current_price")

    lines = [
        f"标的: {opp_entry['name']} ({opp_entry['symbol']})",
        f"市场: {opp_entry['market']} | 主题: {item.theme}",
    ]

    # Basic price info
    if price:
        lines.append(f"当前价: {price:.2f}")

    # Technical section
    lines.append("")
    lines.append("== 技术面 ==")
    trend_parts = []
    if enhanced.get("change_5d") is not None:
        trend_parts.append(f"5日:{enhanced['change_5d']:+.1f}%")
    if enhanced.get("change_20d") is not None:
        trend_parts.append(f"20日:{enhanced['change_20d']:+.1f}%")
    if change_30d is not None:
        trend_parts.append(f"30日:{change_30d * 100:+.1f}%")
    if trend_parts:
        lines.append("价格走势: " + ", ".join(trend_parts))

    ma20 = enhanced.get("ma20")
    ma60 = enhanced.get("ma60")
    if ma20 is not None and ma60 is not None and price:
        ma_status = "多头排列" if price > ma20 > ma60 else ("空头排列" if price < ma20 < ma60 else "震荡")
        lines.append(f"均线: MA20={ma20:.2f}, MA60={ma60:.2f} ({ma_status})")

    vol_change = enhanced.get("volume_change")
    if vol_change is not None:
        vol_desc = "放量" if vol_change > 30 else ("缩量" if vol_change < -30 else "平稳")
        lines.append(f"成交量: 近5日vs前20日 {vol_change:+.0f}% ({vol_desc})")

    high_60d = enhanced.get("high_60d")
    low_60d = enhanced.get("low_60d")
    if high_60d is not None and low_60d is not None and price:
        position = (price - low_60d) / (high_60d - low_60d) * 100 if high_60d != low_60d else 50
        lines.append(f"60日区间: {low_60d:.2f}-{high_60d:.2f} (当前{position:.0f}%位置)")

    # Fundamental section
    lines.append("")
    lines.append("== 基本面 ==")
    if pe is not None:
        pe_str = f"PE: {pe:.1f}"
        pe_pct = enhanced.get("pe_percentile")
        if pe_pct is not None:
            pe_str += f" (历史{pe_pct}%分位)"
        lines.append(pe_str)

    pb = enhanced.get("pb")
    if pb is not None:
        lines.append(f"PB: {pb:.2f}")

    if revenue_growth is not None:
        lines.append(f"营收增长: {revenue_growth * 100:.1f}%")

    if opp_entry.get("target_price") and price:
        target = opp_entry["target_price"]
        upside = (target - price) / price * 100
        lines.append(f"目标价: {target:.2f} (空间{upside:+.1f}%)")

    analyst_rating = enhanced.get("analyst_rating")
    if analyst_rating:
        lines.append(f"分析师评级: {analyst_rating}")

    # Sector context
    sector_perf = enhanced.get("sector_perf")
    sector_flow = enhanced.get("sector_flow")
    if sector_perf or sector_flow:
        lines.append("")
        lines.append("== 所属板块 ==")
        if sector_perf:
            lines.append(f"板块涨跌: {sector_perf.get('change_pct', 0):.1f}%")
        if sector_flow:
            flow = sector_flow.get("net_inflow", 0)
            direction = sector_flow.get("direction", "")
            consecutive = sector_flow.get("consecutive_weeks", 0)
            lines.append(f"板块资金: {'流入' if flow > 0 else '流出'}{abs(flow):.1f}亿, 连续{consecutive}周{direction}")

    # Northbound
    nb_holding = enhanced.get("nb_holding")
    if nb_holding:
        lines.append("")
        lines.append("== 北向资金 ==")
        if nb_holding.get("holding"):
            lines.append(f"持股量: {nb_holding['holding'] / 10000:.0f}万股")
        if nb_holding.get("change_pct") is not None:
            change_pct = nb_holding["change_pct"]
            lines.append(f"28日变化: {'增持' if change_pct > 0 else '减持'}{abs(change_pct):.1f}%")

    lines.append("")
    lines.append(f"机会信号: {', '.join(opp_signals)}")

    user_msg = "\n".join(lines)

    try:
        raw = asyncio.run(
            llm.chat_with_system(
                OPPORTUNITY_SYSTEM_PROMPT, user_msg, model=ModelChoice.FAST,
                max_tokens=4000,
            )
        )
        return _parse_llm_json(raw)
    except (LLMError, json.JSONDecodeError, ValueError, RuntimeError, SyntaxError) as e:
        logger.warning("Failed to get opportunity AI for %s: %s", opp_entry["symbol"], e)
        return None


# ======================================================================
# Enhanced Data Fetching Helpers
# ======================================================================

def _get_quotes_for_period(
    db: Session, symbol: str, market: Market, days: int
) -> List[DailyQuote]:
    """Get quotes for a specified period, sorted ascending by date."""
    since = date.today() - timedelta(days=days)
    return (
        db.query(DailyQuote)
        .filter(
            DailyQuote.symbol == symbol,
            DailyQuote.market == market,
            DailyQuote.trade_date >= since,
        )
        .order_by(DailyQuote.trade_date.asc())
        .all()
    )


def _calc_price_change(quotes: List[DailyQuote], days: int) -> Optional[float]:
    """Calculate price change over N trading days."""
    if len(quotes) < 2:
        return None
    # Find quote closest to N days ago
    target_idx = max(0, len(quotes) - days - 1)
    old_close = quotes[target_idx].close
    new_close = quotes[-1].close
    if old_close is None or new_close is None or old_close == 0:
        return None
    return float((new_close - old_close) / old_close) * 100


def _calc_moving_average(quotes: List[DailyQuote], period: int) -> Optional[float]:
    """Calculate simple moving average for the last N periods."""
    if len(quotes) < period:
        return None
    recent = quotes[-period:]
    closes = [float(q.close) for q in recent if q.close is not None]
    if len(closes) < period:
        return None
    return sum(closes) / len(closes)


def _calc_volume_change(quotes: List[DailyQuote]) -> Optional[float]:
    """Calculate volume change: recent 5-day avg vs previous 20-day avg."""
    if len(quotes) < 25:
        return None
    recent_5 = quotes[-5:]
    prev_20 = quotes[-25:-5]
    recent_vol = sum(q.volume or 0 for q in recent_5) / 5
    prev_vol = sum(q.volume or 0 for q in prev_20) / 20
    if prev_vol == 0:
        return None
    return float((recent_vol - prev_vol) / prev_vol) * 100


def _get_high_low_60d(quotes: List[DailyQuote]) -> tuple:
    """Get 60-day high and low prices."""
    if not quotes:
        return None, None
    highs = [float(q.high) for q in quotes if q.high is not None]
    lows = [float(q.low) for q in quotes if q.low is not None]
    return (max(highs) if highs else None, min(lows) if lows else None)


def _get_pe_percentile(
    db: Session, symbol: str, market_value: str, current_pe: float
) -> Optional[int]:
    """Calculate PE percentile over the past year."""
    since = date.today() - timedelta(days=365)
    snapshots = (
        db.query(FundamentalSnapshot.pe_ratio)
        .filter(
            FundamentalSnapshot.symbol == symbol,
            FundamentalSnapshot.market == market_value,
            FundamentalSnapshot.snapshot_date >= since,
            FundamentalSnapshot.pe_ratio.isnot(None),
            FundamentalSnapshot.pe_ratio > 0,
        )
        .all()
    )
    if len(snapshots) < 5:
        return None
    pe_values = sorted([float(s.pe_ratio) for s in snapshots])
    count_below = sum(1 for pe in pe_values if pe <= current_pe)
    return int(count_below / len(pe_values) * 100)


def _get_fund_nav_static(db: Session, symbol: str) -> Optional[Dict[str, Any]]:
    """Get latest ETF/fund NAV data."""
    ts_code = _symbol_to_ts_code(symbol)
    nav = (
        db.query(FundNavSnapshot)
        .filter(FundNavSnapshot.ts_code == ts_code)
        .order_by(FundNavSnapshot.nav_date.desc())
        .first()
    )
    if not nav:
        return None
    return {
        "unit_nav": float(nav.unit_nav) if nav.unit_nav else None,
        "accum_nav": float(nav.accum_nav) if nav.accum_nav else None,
        "nav_date": nav.nav_date.isoformat() if nav.nav_date else None,
    }


def _get_northbound_holding_static(
    db: Session, symbol: str, days: int = 14
) -> Optional[Dict[str, Any]]:
    """Get northbound holding data for an A-share stock."""
    since = date.today() - timedelta(days=days)
    holdings = (
        db.query(NorthboundHolding)
        .filter(
            NorthboundHolding.symbol == symbol,
            NorthboundHolding.trade_date >= since,
        )
        .order_by(NorthboundHolding.trade_date.asc())
        .all()
    )
    if not holdings:
        return None
    latest = holdings[-1]
    earliest = holdings[0]
    holding_change = None
    change_pct = None
    if latest.holding and earliest.holding and earliest.holding != 0:
        holding_change = float(latest.holding - earliest.holding)
        change_pct = float((latest.holding - earliest.holding) / earliest.holding) * 100
    return {
        "holding": float(latest.holding) if latest.holding else None,
        "market_value": float(latest.market_value) if latest.market_value else None,
        "holding_change": holding_change,
        "change_pct": change_pct,
    }


def _get_sector_for_holding(db: Session, symbol: str) -> Optional[str]:
    """Get sector/industry for a holding based on theme mapping or sector data."""
    return THEME_MAP.get(symbol)


def _get_sector_performance_static(
    db: Session, sector_name: str
) -> Optional[Dict[str, Any]]:
    """Get sector performance data for the current week."""
    # Find sector by name
    sector = (
        db.query(SectorSnapshot)
        .filter(SectorSnapshot.name.contains(sector_name))
        .order_by(SectorSnapshot.snapshot_date.desc())
        .first()
    )
    if not sector:
        return None
    return {
        "name": sector.name,
        "change_pct": float(sector.change_pct) if sector.change_pct else None,
        "leading_stock": sector.leading_stock,
    }


def _get_sector_flow_static(
    db: Session, sector_name: str, days: int = 14
) -> Optional[Dict[str, Any]]:
    """Get sector fund flow data."""
    since = date.today() - timedelta(days=days)
    flows = (
        db.query(SectorFlowSnapshot)
        .filter(
            SectorFlowSnapshot.name.contains(sector_name),
            SectorFlowSnapshot.snapshot_date >= since,
        )
        .order_by(SectorFlowSnapshot.snapshot_date.desc())
        .all()
    )
    if not flows:
        return None
    latest = flows[0]
    # Count consecutive inflow/outflow weeks
    consecutive = 1
    direction = "inflow" if latest.main_net_inflow > 0 else "outflow"
    for f in flows[1:]:
        if (direction == "inflow" and f.main_net_inflow > 0) or \
           (direction == "outflow" and f.main_net_inflow < 0):
            consecutive += 1
        else:
            break
    return {
        "net_inflow": float(latest.main_net_inflow),
        "direction": direction,
        "consecutive_weeks": consecutive,
    }


def _get_yield_spread_static(db: Session) -> Optional[Dict[str, Any]]:
    """Get latest treasury yield spread data."""
    latest = (
        db.query(YieldSpreadRecord)
        .order_by(YieldSpreadRecord.date.desc())
        .first()
    )
    if not latest:
        return None
    # Get 6-month history for trend
    since = date.today() - timedelta(days=180)
    history = (
        db.query(YieldSpreadRecord)
        .filter(YieldSpreadRecord.date >= since)
        .order_by(YieldSpreadRecord.date.asc())
        .all()
    )
    inverted_months = sum(1 for r in history if r.spread < 0) if history else 0
    return {
        "dgs2": float(latest.dgs2),
        "dgs10": float(latest.dgs10),
        "spread": float(latest.spread),
        "is_inverted": latest.spread < 0,
        "inverted_months": inverted_months // 20,  # Approx trading days per month
    }


def _get_market_breadth_static(db: Session) -> List[Dict[str, Any]]:
    """Get market breadth (advance/decline) data for the week."""
    since = date.today() - timedelta(days=7)
    breadths = (
        db.query(MarketBreadthSnapshot)
        .filter(MarketBreadthSnapshot.snapshot_date >= since)
        .order_by(MarketBreadthSnapshot.snapshot_date.desc())
        .all()
    )
    result = []
    seen_indices = set()
    for b in breadths:
        if b.index_code not in seen_indices:
            seen_indices.add(b.index_code)
            result.append({
                "index_code": b.index_code,
                "index_name": b.index_name,
                "advancing": b.advancing,
                "declining": b.declining,
                "unchanged": b.unchanged,
                "close": float(b.close) if b.close else None,
                "change_pct": float(b.change_pct) if b.change_pct else None,
            })
    return result


def _get_index_valuations_static(db: Session) -> List[Dict[str, Any]]:
    """Get A-share index valuations with historical percentile."""
    indices = ["000300.SH", "399006.SZ"]  # CSI 300, ChiNext
    result = []
    for ts_code in indices:
        latest = (
            db.query(IndexValuationSnapshot)
            .filter(IndexValuationSnapshot.ts_code == ts_code)
            .order_by(IndexValuationSnapshot.trade_date.desc())
            .first()
        )
        if not latest:
            continue
        # Calculate percentile
        since = date.today() - timedelta(days=365)
        history = (
            db.query(IndexValuationSnapshot.pe)
            .filter(
                IndexValuationSnapshot.ts_code == ts_code,
                IndexValuationSnapshot.trade_date >= since,
                IndexValuationSnapshot.pe.isnot(None),
            )
            .all()
        )
        pe_percentile = None
        if history and latest.pe:
            pe_values = sorted([float(h.pe) for h in history if h.pe])
            if pe_values:
                count_below = sum(1 for pe in pe_values if pe <= float(latest.pe))
                pe_percentile = int(count_below / len(pe_values) * 100)
        result.append({
            "ts_code": ts_code,
            "name": latest.name,
            "pe": float(latest.pe) if latest.pe else None,
            "pb": float(latest.pb) if latest.pb else None,
            "pe_percentile": pe_percentile,
        })
    return result


def _get_macro_data_static(db: Session) -> Dict[str, Any]:
    """Get latest macro data for US and China."""
    result = {"us": {}, "cn": {}}

    # US macro from MacroData (FRED)
    us_series = {
        "GDP": "GDP growth",
        "CPIAUCSL": "CPI",
        "UNRATE": "Unemployment",
        "FEDFUNDS": "Fed Funds Rate",
    }
    for series_id, label in us_series.items():
        record = (
            db.query(MacroData)
            .filter(MacroData.series_id == series_id)
            .order_by(MacroData.date.desc())
            .first()
        )
        if record:
            result["us"][series_id] = {
                "label": label,
                "value": float(record.value),
                "date": record.date.isoformat() if record.date else None,
            }

    # China macro from CnMacroRecord
    cn_indicators = ["PMI", "CPI", "M2"]
    for indicator in cn_indicators:
        record = (
            db.query(CnMacroRecord)
            .filter(CnMacroRecord.indicator == indicator)
            .order_by(CnMacroRecord.date.desc())
            .first()
        )
        if record:
            result["cn"][indicator] = {
                "value": float(record.value),
                "yoy_change": float(record.yoy_change) if record.yoy_change else None,
                "date": record.date.isoformat() if record.date else None,
            }

    return result


def _get_northbound_flow_static(db: Session, days: int = 28) -> Dict[str, Any]:
    """Get northbound capital trading volume summary.

    Note: TuShare moneyflow_hsgt provides daily TRADING VOLUME (成交额),
    not net flow (净买入). We present volume data and day-over-day changes
    to indicate activity trends.
    """
    since = date.today() - timedelta(days=days)
    flows = (
        db.query(NorthboundFlow)
        .filter(NorthboundFlow.trade_date >= since)
        .order_by(NorthboundFlow.trade_date.desc())
        .all()
    )
    if not flows:
        return {"today_volume": 0, "today_date": None}

    # flows is desc order, [0] = latest
    latest = flows[0]
    prev = flows[1] if len(flows) > 1 else None

    today_vol = float(latest.net_flow)
    today_hgt = float(latest.hgt or 0)
    today_sgt = float(latest.sgt or 0)
    today_date = latest.trade_date.isoformat()

    # Day-over-day volume change
    vol_change = 0.0
    vol_change_pct = 0.0
    if prev:
        prev_vol = float(prev.net_flow)
        vol_change = today_vol - prev_vol
        vol_change_pct = (vol_change / prev_vol * 100) if prev_vol != 0 else 0

    # 5-day average volume
    recent_5 = flows[:5] if len(flows) >= 5 else flows
    avg_5d_vol = sum(float(f.net_flow) for f in recent_5) / len(recent_5)

    # Activity trend: is latest volume above or below 5-day avg?
    activity = "活跃" if today_vol > avg_5d_vol * 1.1 else ("清淡" if today_vol < avg_5d_vol * 0.9 else "正常")

    # Week total volume (sum of daily volumes)
    week_flows = [f for f in flows if f.trade_date >= date.today() - timedelta(days=7)]
    week_total_vol = sum(float(f.net_flow) for f in week_flows)
    week_avg_vol = week_total_vol / len(week_flows) if week_flows else 0

    # Month total volume
    month_total_vol = sum(float(f.net_flow) for f in flows)
    month_avg_vol = month_total_vol / len(flows) if flows else 0

    return {
        "today_volume": round(today_vol, 2),
        "today_hgt": round(today_hgt, 2),
        "today_sgt": round(today_sgt, 2),
        "today_date": today_date,
        "vol_change": round(vol_change, 2),
        "vol_change_pct": round(vol_change_pct, 1),
        "avg_5d_volume": round(avg_5d_vol, 2),
        "week_avg_volume": round(week_avg_vol, 2),
        "month_avg_volume": round(month_avg_vol, 2),
        "activity": activity,
        "days_count": len(flows),
    }


def _get_commodity_data_static(db: Session) -> List[Dict[str, Any]]:
    """Get commodity data with 60-day percentile."""
    symbols = {
        "GC=F": "黄金",
        "SI=F": "白银",
        "CL=F": "原油",
        "HG=F": "铜",
        "^VIX": "VIX",
    }
    result = []
    for symbol, name in symbols.items():
        # Get latest
        latest = (
            db.query(MarketIndicatorSnapshot)
            .filter(MarketIndicatorSnapshot.symbol == symbol)
            .order_by(MarketIndicatorSnapshot.date.desc())
            .first()
        )
        if not latest:
            continue
        # Get 60-day history for percentile
        since = date.today() - timedelta(days=60)
        history = (
            db.query(MarketIndicatorSnapshot.value)
            .filter(
                MarketIndicatorSnapshot.symbol == symbol,
                MarketIndicatorSnapshot.date >= since,
                MarketIndicatorSnapshot.value.isnot(None),
            )
            .all()
        )
        percentile = None
        if history and latest.value:
            values = sorted([float(h.value) for h in history if h.value])
            if values:
                count_below = sum(1 for v in values if v <= float(latest.value))
                percentile = int(count_below / len(values) * 100)
        result.append({
            "symbol": symbol,
            "name": name,
            "value": float(latest.value) if latest.value else None,
            "change_pct": float(latest.change_pct) if latest.change_pct else None,
            "percentile_60d": percentile,
        })

    # Calculate gold/silver ratio
    gold = next((c for c in result if c["symbol"] == "GC=F"), None)
    silver = next((c for c in result if c["symbol"] == "SI=F"), None)
    if gold and silver and gold["value"] and silver["value"]:
        result.append({
            "symbol": "GOLD_SILVER_RATIO",
            "name": "金银比",
            "value": gold["value"] / silver["value"],
            "change_pct": None,
            "percentile_60d": None,
        })

    return result


# ======================================================================
# DailyReportGenerator
# ======================================================================

class DailyReportGenerator:
    """Generates pre-stored daily reports with per-holding AI commentary."""

    def __init__(self, db: Session):
        self.db = db
        self._llm = LLMClient()
        self._usd_cny: Optional[Decimal] = None

    def generate(self) -> int:
        """Generate a daily report and save to DB. Returns report ID."""
        now = datetime.now()
        self._usd_cny = _get_usd_cny_rate_static(self.db)

        # 1. Build holdings data with P&L
        holdings_data, total_value_cny, cash_pct = self._build_holdings_data()

        # 2. Calculate today's change for each holding
        self._enrich_today_change(holdings_data)

        # 3. Sort by today_change_pct ascending (worst first)
        holdings_data.sort(key=lambda h: h.get("today_change_pct") or 0)

        # 4. AI commentary for each holding
        self._enrich_with_ai(holdings_data, total_value_cny)

        # 5. Scan opportunities (watchlist + related sectors)
        opportunities = _scan_opportunities_static(self.db, self._llm)

        # 6. Generate portfolio summary with AI
        today_pnl = sum(h.get("today_pnl", 0) for h in holdings_data)
        today_pnl_pct = (today_pnl / float(total_value_cny) * 100) if total_value_cny else 0
        total_pnl = sum(h.get("total_pnl", 0) for h in holdings_data)
        total_pnl_pct = (total_pnl / float(total_value_cny) * 100) if total_value_cny else 0

        ai_summary = self._generate_summary(holdings_data, today_pnl, today_pnl_pct)

        content = {
            "portfolio_summary": {
                "total_value_cny": round(float(total_value_cny), 2),
                "today_pnl": round(today_pnl, 2),
                "today_pnl_pct": round(today_pnl_pct, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl_pct, 2),
                "holdings_count": len([h for h in holdings_data if h["symbol"] != "CASH"]),
                "cash_pct": round(cash_pct, 2),
                "ai_summary": ai_summary,
            },
            "holdings": holdings_data,
            "opportunities": opportunities,
        }

        report = GeneratedReport(
            report_type="daily",
            report_date=now.date(),
            generated_at=now,
            summary=ai_summary,
            content=content,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        logger.info(f"Daily report generated, id={report.id}")
        return report.id

    # ------------------------------------------------------------------
    # Holdings data
    # ------------------------------------------------------------------

    def _build_holdings_data(self) -> tuple:
        """Build holdings data with P&L calculations.

        Returns:
            (holdings_list, total_value_cny, cash_pct)
        """
        holdings = (
            self.db.query(Holding)
            .filter(Holding.status == HoldingStatus.ACTIVE)
            .all()
        )

        holdings_data: List[Dict[str, Any]] = []
        total_value_cny = Decimal("0")
        cash_value_cny = Decimal("0")

        # First pass: compute market values
        position_values: List[tuple] = []  # (holding, price, qty, avg_cost, value_cny)
        for h in holdings:
            price = _get_latest_price_static(self.db, h)
            qty = Decimal(str(h.quantity))
            avg_cost = Decimal(str(h.avg_cost))
            local_value = price * qty
            value_cny = _to_cny_static(local_value, h.market, h.symbol, self._usd_cny)
            total_value_cny += value_cny
            if h.symbol == "CASH":
                cash_value_cny += value_cny
            position_values.append((h, price, qty, avg_cost, value_cny))

        if total_value_cny == 0:
            total_value_cny = Decimal("1")

        cash_pct = float(cash_value_cny / total_value_cny * 100)

        # Second pass: build data dicts with weight
        for h, price, qty, avg_cost, value_cny in position_values:
            weight_pct = float(value_cny / total_value_cny * 100)
            pnl_local = (price - avg_cost) * qty
            pnl_pct = float((price - avg_cost) / avg_cost * 100) if avg_cost else 0.0

            # Convert total_pnl to CNY for consistent aggregation
            total_pnl_cny = float(_to_cny_static(pnl_local, h.market, h.symbol, self._usd_cny))

            name = _get_stock_name_static(self.db, h.symbol, h.market)

            near_stop = False
            near_tp = False
            if h.stop_loss_price and float(price) > 0:
                near_stop = float(price) <= float(h.stop_loss_price) * 1.05
            if h.take_profit_price and float(price) > 0:
                near_tp = float(price) >= float(h.take_profit_price) * 0.95

            entry: Dict[str, Any] = {
                "symbol": h.symbol,
                "name": name,
                "market": h.market.value,
                "tier": h.tier.value,
                "weight_pct": round(weight_pct, 2),
                "quantity": float(qty),
                "avg_cost": float(avg_cost),
                "current_price": float(price),
                "today_change_pct": None,  # filled later
                "today_pnl": 0,  # filled later
                "total_pnl": round(total_pnl_cny, 2),
                "total_pnl_pct": round(pnl_pct, 2),
                "action": "hold",  # default, overridden by AI
                "ai_comment": "",
                "ai_detail": "",
                "stop_loss_price": float(h.stop_loss_price) if h.stop_loss_price else None,
                "take_profit_price": float(h.take_profit_price) if h.take_profit_price else None,
                "near_stop_loss": near_stop,
                "near_take_profit": near_tp,
            }
            holdings_data.append(entry)

        return holdings_data, total_value_cny, cash_pct

    # ------------------------------------------------------------------
    # Today's change enrichment
    # ------------------------------------------------------------------

    def _enrich_today_change(self, holdings_data: List[Dict[str, Any]]) -> None:
        """For each holding, compute today_change_pct and today_pnl from latest 2 quotes."""
        for entry in holdings_data:
            if entry["symbol"] == "CASH":
                entry["today_change_pct"] = 0.0
                entry["today_pnl"] = 0.0
                continue

            market_enum = Market(entry["market"])
            quotes = (
                self.db.query(DailyQuote)
                .filter(
                    DailyQuote.symbol == entry["symbol"],
                    DailyQuote.market == market_enum,
                )
                .order_by(desc(DailyQuote.trade_date))
                .limit(2)
                .all()
            )

            if len(quotes) >= 2 and quotes[0].close and quotes[1].close:
                latest_close = Decimal(str(quotes[0].close))
                prev_close = Decimal(str(quotes[1].close))
                if prev_close != 0:
                    change_pct = float((latest_close - prev_close) / prev_close * 100)
                    entry["today_change_pct"] = round(change_pct, 2)
                    # today_pnl = (current - prev) * quantity, converted to CNY
                    pnl_local = (latest_close - prev_close) * Decimal(str(entry["quantity"]))
                    pnl_cny = float(_to_cny_static(pnl_local, market_enum, entry["symbol"], self._usd_cny))
                    entry["today_pnl"] = round(pnl_cny, 2)

    # ------------------------------------------------------------------
    # AI enrichment
    # ------------------------------------------------------------------

    def _enrich_with_ai(self, holdings_data: List[Dict[str, Any]], total_value_cny: Decimal) -> None:
        """Add AI commentary to each non-CASH holding."""
        non_cash = [h for h in holdings_data if h["symbol"] != "CASH"]
        if not non_cash:
            return

        async def _run_all():
            tasks = []
            for entry in non_cash:
                tasks.append(self._get_holding_ai(entry))
            return await asyncio.gather(*tasks, return_exceptions=True)

        try:
            results = asyncio.run(_run_all())
        except RuntimeError:
            # If already in an async context, use a new event loop
            loop = asyncio.new_event_loop()
            try:
                results = loop.run_until_complete(_run_all())
            finally:
                loop.close()

        for entry, result in zip(non_cash, results):
            if isinstance(result, Exception):
                logger.warning("AI enrichment failed for %s: %s", entry["symbol"], result)
                continue
            if result:
                entry["ai_comment"] = result.get("ai_comment", "")
                action = result.get("action", "hold").lower()
                if action in ("hold", "add", "reduce", "sell"):
                    entry["action"] = action
                entry["ai_detail"] = result.get("ai_detail", "")

    async def _get_holding_ai(self, entry: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Call LLM for a single holding and return parsed JSON dict."""
        symbol = entry["symbol"]
        market_enum = Market(entry["market"])
        market_value = entry["market"]

        # Fetch related signals
        signals = (
            self.db.query(Signal)
            .filter(Signal.related_symbols.contains(symbol))
            .limit(5)
            .all()
        )

        # Get 60-day quotes for technical analysis
        quotes = _get_quotes_for_period(self.db, symbol, market_enum, 60)

        # Calculate price changes
        change_5d = _calc_price_change(quotes, 5)
        change_20d = _calc_price_change(quotes, 20)
        ma20 = _calc_moving_average(quotes, 20)
        volume_change = _calc_volume_change(quotes)
        high_60d, low_60d = _get_high_low_60d(quotes)

        # Get fundamentals
        fundamental = _get_latest_fundamental_static(self.db, symbol, market_value)
        pe = float(fundamental.pe_ratio) if fundamental and fundamental.pe_ratio else None
        pb = float(fundamental.pb_ratio) if fundamental and fundamental.pb_ratio else None
        analyst_rating = fundamental.analyst_rating if fundamental else None

        # PE percentile (if we have PE)
        pe_percentile = None
        if pe and pe > 0:
            pe_percentile = _get_pe_percentile(self.db, symbol, market_value, pe)

        # ETF NAV data (for CN ETFs)
        nav_data = None
        if market_enum == Market.CN and _is_cn_etf(symbol):
            nav_data = _get_fund_nav_static(self.db, symbol)

        # Northbound holding (for A-shares)
        nb_holding = None
        if market_enum == Market.CN and not _is_cn_etf(symbol):
            nb_holding = _get_northbound_holding_static(self.db, symbol, days=14)

        # Build user prompt with enriched data
        lines = [
            f"持仓: {entry['name']} ({symbol}.{market_value})",
            f"市场: {market_value} | 层级: {entry['tier']} | 仓位占比: {entry['weight_pct']}%",
            f"数量: {int(entry['quantity'])} | 均成本: {entry['avg_cost']:.2f} | 现价: {entry['current_price']:.2f}",
            f"总盈亏: {'+' if entry['total_pnl'] >= 0 else ''}{entry['total_pnl']:.0f} ({'+' if entry['total_pnl_pct'] >= 0 else ''}{entry['total_pnl_pct']:.1f}%)",
        ]

        # Today's change
        if entry.get("today_change_pct") is not None:
            lines.append(f"今日涨跌: {'+' if entry['today_change_pct'] >= 0 else ''}{entry['today_change_pct']:.1f}%")

        # Technical data
        tech_parts = []
        if change_5d is not None:
            tech_parts.append(f"5日涨跌:{change_5d:+.1f}%")
        if change_20d is not None:
            tech_parts.append(f"20日涨跌:{change_20d:+.1f}%")
        if tech_parts:
            lines.append("短期走势: " + ", ".join(tech_parts))

        if ma20 is not None:
            current = entry['current_price']
            ma_diff = (current - ma20) / ma20 * 100 if ma20 > 0 else 0
            lines.append(f"MA20: {ma20:.2f} (现价{'高于' if ma_diff >= 0 else '低于'}均线{abs(ma_diff):.1f}%)")

        if volume_change is not None:
            lines.append(f"成交量变化: 近5日vs前20日 {volume_change:+.0f}%")

        if high_60d is not None and low_60d is not None:
            current = entry['current_price']
            position = (current - low_60d) / (high_60d - low_60d) * 100 if high_60d != low_60d else 50
            lines.append(f"60日区间: {low_60d:.2f}-{high_60d:.2f} (当前位置{position:.0f}%)")

        # Fundamental data
        fund_parts = []
        if pe is not None:
            pe_str = f"PE:{pe:.1f}"
            if pe_percentile is not None:
                pe_str += f"(历史{pe_percentile}%分位)"
            fund_parts.append(pe_str)
        if pb is not None:
            fund_parts.append(f"PB:{pb:.2f}")
        if analyst_rating:
            fund_parts.append(f"评级:{analyst_rating}")
        if fund_parts:
            lines.append("估值: " + ", ".join(fund_parts))

        # ETF NAV info
        if nav_data:
            nav = nav_data.get("unit_nav")
            if nav:
                current = entry['current_price']
                premium = (current - nav) / nav * 100 if nav > 0 else 0
                lines.append(f"基金净值: {nav:.4f} ({'溢价' if premium >= 0 else '折价'}{abs(premium):.2f}%)")

        # Northbound holding
        if nb_holding:
            if nb_holding.get("change_pct") is not None:
                change_pct = nb_holding["change_pct"]
                direction = "增持" if change_pct > 0 else "减持"
                lines.append(f"北向资金14日: {direction}{abs(change_pct):.1f}%")

        # Stop/Take profit
        if entry.get("stop_loss_price"):
            lines.append(f"止损价: {entry['stop_loss_price']:.2f}")
        if entry.get("take_profit_price"):
            lines.append(f"止盈价: {entry['take_profit_price']:.2f}")

        # Related signals
        if signals:
            lines.append("相关信号:")
            for sig in signals:
                lines.append(f"  - [{sig.severity.value}] {sig.title}: {sig.description}")

        user_msg = "\n".join(lines)

        try:
            raw = await self._llm.chat_with_system(
                DAILY_HOLDING_SYSTEM_PROMPT, user_msg, model=ModelChoice.FAST,
                max_tokens=4000,
            )
            return _parse_llm_json(raw)
        except (LLMError, json.JSONDecodeError, ValueError, SyntaxError) as e:
            logger.warning("Failed to get AI for %s: %s", entry["symbol"], e)
            return None

    # ------------------------------------------------------------------
    # Summary generation
    # ------------------------------------------------------------------

    def _generate_summary(
        self, holdings_data: List[Dict[str, Any]], today_pnl: float, today_pnl_pct: float
    ) -> str:
        """Generate a one-line AI summary for the portfolio. Falls back to template."""
        # Build context for LLM
        lines = [
            f"今日组合盈亏: {'+' if today_pnl >= 0 else ''}{today_pnl:.0f}元 ({'+' if today_pnl_pct >= 0 else ''}{today_pnl_pct:.1f}%)",
            "持仓概况:",
        ]
        for h in holdings_data:
            if h["symbol"] == "CASH":
                continue
            change_str = (
                f"{'+' if h.get('today_change_pct', 0) >= 0 else ''}{h.get('today_change_pct', 0):.1f}%"
                if h.get("today_change_pct") is not None
                else "N/A"
            )
            lines.append(f"  {h['name']}({h['symbol']}): 今日{change_str}, 仓位{h['weight_pct']:.1f}%")

        user_msg = "\n".join(lines)

        try:
            raw = asyncio.run(
                self._llm.chat_with_system(
                    DAILY_SUMMARY_SYSTEM_PROMPT, user_msg, model=ModelChoice.FAST
                )
            )
            summary = raw.strip().strip('"').strip("'")
            if summary:
                return summary
        except (LLMError, RuntimeError) as e:
            logger.warning("Failed to generate AI summary: %s", e)

        # Fallback template
        direction = "上涨" if today_pnl >= 0 else "下跌"
        return f"今日持仓整体{direction}{abs(today_pnl_pct):.1f}%，盈亏{'+' if today_pnl >= 0 else ''}{today_pnl:.0f}元"


# ======================================================================
# WeeklyReportGenerator
# ======================================================================

class WeeklyReportGenerator:
    """Generates pre-stored weekly reports with macro context and strategic analysis."""

    def __init__(self, db: Session):
        self.db = db
        self._llm = LLMClient()
        self._usd_cny: Optional[Decimal] = None

    def generate(self) -> int:
        """Generate a weekly report and save to DB. Returns report ID."""
        now = datetime.now()
        week_end = now.date()
        week_start = week_end - timedelta(days=week_end.weekday())  # Monday

        self._usd_cny = _get_usd_cny_rate_static(self.db)

        # 1. Build week summary
        week_summary = self._build_week_summary(week_start, week_end)

        # 2. Macro + capital flow (run analyzers)
        macro_capital = self._build_macro_capital(week_start, week_end)

        # 3. Holdings medium/long-term review
        holdings = self._build_holdings_review(week_start)

        # 4. Opportunities (reuse shared helper)
        opportunities = _scan_opportunities_static(self.db, self._llm)

        # 5. Risk alerts (from PortfolioHealthAnalyzer)
        risk_alerts = self._build_risk_alerts()

        # 6. Next week events (placeholder)
        next_week_events: List[Dict[str, Any]] = []

        # 7. AI summary for the week
        week_summary["ai_summary"] = self._generate_week_summary_ai(
            week_summary, macro_capital, holdings
        )

        content = {
            "week_summary": week_summary,
            "macro_capital": macro_capital,
            "holdings": holdings,
            "opportunities": opportunities,
            "risk_alerts": risk_alerts,
            "next_week_events": next_week_events,
        }

        # Create one-line summary for list
        summary_text = week_summary.get("ai_summary", "")
        if not summary_text:
            pnl = week_summary.get("week_pnl", 0)
            summary_text = f"本周盈亏 {pnl:+.0f} CNY"

        report = GeneratedReport(
            report_type="weekly",
            report_date=now.date(),
            generated_at=now,
            summary=summary_text,
            content=content,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        logger.info(f"Weekly report generated, id={report.id}")
        return report.id

    # ------------------------------------------------------------------
    # Week summary
    # ------------------------------------------------------------------

    def _build_week_summary(self, week_start: date, week_end: date) -> Dict[str, Any]:
        """Build the week_summary section with P&L and best/worst holdings."""
        holdings = (
            self.db.query(Holding)
            .filter(Holding.status == HoldingStatus.ACTIVE)
            .all()
        )

        total_week_pnl_cny = Decimal("0")
        total_current_value_cny = Decimal("0")
        best_holding: Optional[Dict[str, Any]] = None
        worst_holding: Optional[Dict[str, Any]] = None

        for h in holdings:
            if h.symbol == "CASH":
                qty = Decimal(str(h.quantity))
                total_current_value_cny += qty
                continue

            qty = Decimal(str(h.quantity))
            current_price = _get_latest_price_static(self.db, h)
            current_value_local = current_price * qty
            current_value_cny = _to_cny_static(current_value_local, h.market, h.symbol, self._usd_cny)
            total_current_value_cny += current_value_cny

            # Get price at week_start
            week_start_price = self._get_price_at_date(h.symbol, h.market, week_start)
            if week_start_price is None:
                week_start_price = current_price  # fallback: no change

            if week_start_price and week_start_price != 0:
                week_change_pct = float((current_price - week_start_price) / week_start_price * 100)
            else:
                week_change_pct = 0.0

            week_pnl_local = (current_price - week_start_price) * qty
            week_pnl_cny = _to_cny_static(week_pnl_local, h.market, h.symbol, self._usd_cny)
            total_week_pnl_cny += week_pnl_cny

            name = _get_stock_name_static(self.db, h.symbol, h.market)

            if best_holding is None or week_change_pct > best_holding["pnl_pct"]:
                best_holding = {"symbol": h.symbol, "name": name, "pnl_pct": round(week_change_pct, 2)}
            if worst_holding is None or week_change_pct < worst_holding["pnl_pct"]:
                worst_holding = {"symbol": h.symbol, "name": name, "pnl_pct": round(week_change_pct, 2)}

        week_pnl_pct = (
            float(total_week_pnl_cny / total_current_value_cny * 100)
            if total_current_value_cny else 0.0
        )

        return {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "week_pnl": round(float(total_week_pnl_cny), 2),
            "week_pnl_pct": round(week_pnl_pct, 2),
            "best_holding": (
                {"symbol": best_holding["symbol"], "pnl_pct": best_holding["pnl_pct"]}
                if best_holding else None
            ),
            "worst_holding": (
                {"symbol": worst_holding["symbol"], "pnl_pct": worst_holding["pnl_pct"]}
                if worst_holding else None
            ),
            "ai_summary": "",  # filled later
        }

    def _get_price_at_date(
        self, symbol: str, market: Market, target_date: date
    ) -> Optional[Decimal]:
        """Get the closing price at or just before a given date."""
        if _is_cn_etf(symbol) and market == Market.CN:
            ts_code = _symbol_to_ts_code(symbol)
            nav = (
                self.db.query(FundNavSnapshot)
                .filter(
                    FundNavSnapshot.ts_code == ts_code,
                    FundNavSnapshot.nav_date <= target_date,
                )
                .order_by(desc(FundNavSnapshot.nav_date))
                .first()
            )
            if nav and nav.unit_nav:
                return Decimal(str(nav.unit_nav))

        quote = (
            self.db.query(DailyQuote)
            .filter(
                DailyQuote.symbol == symbol,
                DailyQuote.market == market,
                DailyQuote.trade_date <= target_date,
            )
            .order_by(desc(DailyQuote.trade_date))
            .first()
        )
        if quote and quote.close:
            return Decimal(str(quote.close))
        return None

    # ------------------------------------------------------------------
    # Macro + capital flow
    # ------------------------------------------------------------------

    def _build_macro_capital(self, week_start: date, week_end: date) -> Dict[str, Any]:
        """Build macro_capital section using analyzers and DB queries."""
        from src.analyzers.market_environment import MarketEnvironmentAnalyzer
        from src.analyzers.capital_flow import CapitalFlowAnalyzer

        # Run market environment analyzer
        market_env = MarketEnvironmentAnalyzer(self.db)
        env_report = market_env.analyze()

        us_score = env_report.data.get("us_macro", {}).get("score") if env_report.data else None
        cn_score = env_report.data.get("china_macro", {}).get("score") if env_report.data else None

        # Build US/CN summaries from report details
        us_summary = ""
        cn_summary = ""
        if env_report.details:
            us_parts = [d for d in env_report.details if d.startswith("[US宏观]") or d.startswith("[利差]") or d.startswith("[CPI]") or d.startswith("[失业率]") or d.startswith("[VIX]")]
            cn_parts = [d for d in env_report.details if d.startswith("[中国宏观]") or d.startswith("[PMI]") or d.startswith("[流动性]") or d.startswith("[Shibor") or d.startswith("[新增贷款]")]
            if us_parts:
                us_summary = "；".join(us_parts[:3])
            if cn_parts:
                cn_summary = "；".join(cn_parts[:3])

        # Run capital flow analyzer
        capital_flow = CapitalFlowAnalyzer(self.db)
        cf_report = capital_flow.analyze()

        nb_data = cf_report.data.get("northbound", {}) if cf_report.data else {}
        sf_data = cf_report.data.get("sector_flow", {}) if cf_report.data else {}

        # Northbound trading volume data (from TuShare, not net flow)
        nb_flow_detail = _get_northbound_flow_static(self.db, days=28)
        northbound_trend = nb_flow_detail.get("activity", "数据不足")

        # Sector flow: top5 inflow / outflow from capital flow analyzer
        sector_inflow_top5 = [
            {"name": s["name"], "flow": round(s["main_net_inflow"], 2)}
            for s in sf_data.get("top5_inflow", [])
        ]
        sector_outflow_top5 = [
            {"name": s["name"], "flow": round(s["main_net_inflow"], 2)}
            for s in sf_data.get("bottom5_outflow", [])
        ]

        # Key events: HIGH/CRITICAL signals this week
        key_events = self._get_key_events(week_start, week_end)

        # === NEW: Enhanced macro data ===

        # Yield spread (treasury 10Y-2Y)
        yield_spread = _get_yield_spread_static(self.db)

        # Market breadth (advance/decline)
        market_breadth = _get_market_breadth_static(self.db)

        # Index valuations (CSI 300, ChiNext) with PE percentile
        index_valuations = _get_index_valuations_static(self.db)

        # Detailed macro data (US + CN)
        macro_data = _get_macro_data_static(self.db)

        # Commodity data with percentiles
        commodity_data = _get_commodity_data_static(self.db)

        return {
            "us_score": us_score,
            "cn_score": cn_score,
            "us_summary": us_summary,
            "cn_summary": cn_summary,
            "northbound_weekly_flow": nb_flow_detail.get("today_volume", 0),
            "northbound_trend": northbound_trend,
            "northbound_detail": nb_flow_detail,
            "sector_inflow_top5": sector_inflow_top5,
            "sector_outflow_top5": sector_outflow_top5,
            "key_events": key_events,
            # Enhanced data
            "yield_spread": yield_spread,
            "market_breadth": market_breadth,
            "index_valuations": index_valuations,
            "macro_data": macro_data,
            "commodities": commodity_data,
        }

    def _get_weekly_northbound_flow(self, week_start: date, week_end: date) -> float:
        """Get average daily northbound trading volume for the given week."""
        flows = (
            self.db.query(NorthboundFlow.net_flow)
            .filter(
                NorthboundFlow.trade_date >= week_start,
                NorthboundFlow.trade_date <= week_end,
            )
            .all()
        )
        if not flows:
            return 0.0
        return sum(float(f[0]) for f in flows) / len(flows)

    def _get_key_events(self, week_start: date, week_end: date) -> List[str]:
        """Extract titles of HIGH/CRITICAL signals from the current week."""
        signals = (
            self.db.query(Signal)
            .filter(
                Signal.severity.in_([SignalSeverity.HIGH, SignalSeverity.CRITICAL]),
                Signal.created_at >= datetime.combine(week_start, datetime.min.time()),
                Signal.created_at <= datetime.combine(week_end, datetime.max.time()),
            )
            .order_by(desc(Signal.created_at))
            .limit(10)
            .all()
        )
        return [s.title for s in signals]

    # ------------------------------------------------------------------
    # Holdings review (weekly perspective)
    # ------------------------------------------------------------------

    def _build_holdings_review(self, week_start: date) -> List[Dict[str, Any]]:
        """Build holdings review with weekly change and medium-term AI commentary."""
        holdings = (
            self.db.query(Holding)
            .filter(Holding.status == HoldingStatus.ACTIVE)
            .all()
        )

        # First pass: compute total value for weight calculation
        total_value_cny = Decimal("0")
        position_data: List[tuple] = []
        for h in holdings:
            if h.symbol == "CASH":
                qty = Decimal(str(h.quantity))
                total_value_cny += qty
                continue

            current_price = _get_latest_price_static(self.db, h)
            qty = Decimal(str(h.quantity))
            avg_cost = Decimal(str(h.avg_cost))
            current_value_local = current_price * qty
            current_value_cny = _to_cny_static(current_value_local, h.market, h.symbol, self._usd_cny)
            total_value_cny += current_value_cny

            week_start_price = self._get_price_at_date(h.symbol, h.market, week_start)
            if week_start_price is None:
                week_start_price = current_price

            position_data.append((h, current_price, qty, avg_cost, current_value_cny, week_start_price))

        if total_value_cny == 0:
            total_value_cny = Decimal("1")

        # Second pass: build entries
        entries: List[Dict[str, Any]] = []
        for h, current_price, qty, avg_cost, current_value_cny, week_start_price in position_data:
            weight_pct = float(current_value_cny / total_value_cny * 100)
            total_pnl_pct = float((current_price - avg_cost) / avg_cost * 100) if avg_cost else 0.0

            # Calculate total P&L in CNY
            pnl_local = (current_price - avg_cost) * qty
            total_pnl_cny = float(_to_cny_static(pnl_local, h.market, h.symbol, self._usd_cny))

            # Week P&L
            if week_start_price and week_start_price != 0:
                week_change_pct = float((current_price - week_start_price) / week_start_price * 100)
                week_pnl_local = (current_price - week_start_price) * qty
                week_pnl_cny = float(_to_cny_static(week_pnl_local, h.market, h.symbol, self._usd_cny))
            else:
                week_change_pct = 0.0
                week_pnl_cny = 0.0

            name = _get_stock_name_static(self.db, h.symbol, h.market)

            entry: Dict[str, Any] = {
                "symbol": h.symbol,
                "name": name,
                "market": h.market.value,
                "tier": h.tier.value,
                "quantity": float(qty),
                "avg_cost": float(avg_cost),
                "current_price": float(current_price),
                "week_start_price": float(week_start_price) if week_start_price else None,
                "market_value_cny": round(float(current_value_cny), 2),
                "weight_pct": round(weight_pct, 2),
                "week_change_pct": round(week_change_pct, 2),
                "week_pnl": round(week_pnl_cny, 2),
                "total_pnl": round(total_pnl_cny, 2),
                "total_pnl_pct": round(total_pnl_pct, 2),
                "stop_loss_price": float(h.stop_loss_price) if h.stop_loss_price else None,
                "take_profit_price": float(h.take_profit_price) if h.take_profit_price else None,
                "action": "hold",
                "ai_comment": "",
                "ai_detail": "",
            }
            entries.append(entry)

        # Sort by week_change_pct ascending (worst first)
        entries.sort(key=lambda e: e.get("week_change_pct", 0))

        # AI enrichment for each holding (using QUALITY model)
        self._enrich_holdings_weekly_ai(entries)

        return entries

    def _enrich_holdings_weekly_ai(self, holdings_data: List[Dict[str, Any]]) -> None:
        """Add weekly AI commentary to each holding using QUALITY model."""
        if not holdings_data:
            return

        async def _run_all():
            tasks = [self._get_weekly_holding_ai(entry) for entry in holdings_data]
            return await asyncio.gather(*tasks, return_exceptions=True)

        try:
            results = asyncio.run(_run_all())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                results = loop.run_until_complete(_run_all())
            finally:
                loop.close()

        for entry, result in zip(holdings_data, results):
            if isinstance(result, Exception):
                logger.warning("Weekly AI enrichment failed for %s: %s", entry["symbol"], result)
                continue
            if result:
                entry["ai_comment"] = result.get("ai_comment", "")
                action = result.get("action", "hold").lower()
                if action in ("hold", "add", "reduce", "sell"):
                    entry["action"] = action
                entry["ai_detail"] = result.get("ai_detail", "")

    async def _get_weekly_holding_ai(self, entry: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Call LLM for a single holding's weekly review (QUALITY model)."""
        symbol = entry["symbol"]
        market_enum = Market(entry["market"])
        market_value = entry["market"]

        signals = (
            self.db.query(Signal)
            .filter(Signal.related_symbols.contains(symbol))
            .limit(5)
            .all()
        )

        # Get 60-day quotes for technical analysis (more history for weekly)
        quotes = _get_quotes_for_period(self.db, symbol, market_enum, 60)

        # Calculate price changes
        change_5d = _calc_price_change(quotes, 5)
        change_20d = _calc_price_change(quotes, 20)
        change_60d = _calc_price_change(quotes, 60)
        ma20 = _calc_moving_average(quotes, 20)
        ma60 = _calc_moving_average(quotes, 60)
        volume_change = _calc_volume_change(quotes)
        high_60d, low_60d = _get_high_low_60d(quotes)

        # Get fundamentals
        fundamental = _get_latest_fundamental_static(self.db, symbol, market_value)
        pe = float(fundamental.pe_ratio) if fundamental and fundamental.pe_ratio else None
        pb = float(fundamental.pb_ratio) if fundamental and fundamental.pb_ratio else None
        revenue_growth = float(fundamental.revenue_growth) if fundamental and fundamental.revenue_growth else None
        target_price = float(fundamental.target_price) if fundamental and fundamental.target_price else None
        analyst_rating = fundamental.analyst_rating if fundamental else None

        # PE percentile
        pe_percentile = None
        if pe and pe > 0:
            pe_percentile = _get_pe_percentile(self.db, symbol, market_value, pe)

        # ETF NAV data
        nav_data = None
        if market_enum == Market.CN and _is_cn_etf(symbol):
            nav_data = _get_fund_nav_static(self.db, symbol)

        # Northbound holding (for A-shares, longer period for weekly)
        nb_holding = None
        if market_enum == Market.CN and not _is_cn_etf(symbol):
            nb_holding = _get_northbound_holding_static(self.db, symbol, days=28)

        # Sector data
        sector_name = _get_sector_for_holding(self.db, symbol)
        sector_perf = None
        sector_flow = None
        if sector_name:
            sector_perf = _get_sector_performance_static(self.db, sector_name)
            sector_flow = _get_sector_flow_static(self.db, sector_name, days=14)

        # Current price (approximate from entry or quotes)
        current_price = quotes[-1].close if quotes and quotes[-1].close else None

        # Build enriched prompt
        lines = [
            f"持仓: {entry['name']} ({symbol}.{market_value})",
            f"市场: {market_value} | 层级: {entry['tier']} | 仓位占比: {entry['weight_pct']}%",
            f"本周涨跌: {'+' if entry['week_change_pct'] >= 0 else ''}{entry['week_change_pct']:.1f}%",
            f"总盈亏: {'+' if entry['total_pnl_pct'] >= 0 else ''}{entry['total_pnl_pct']:.1f}%",
        ]

        # Technical trends
        lines.append("")
        lines.append("== 技术面 ==")
        trend_parts = []
        if change_5d is not None:
            trend_parts.append(f"5日:{change_5d:+.1f}%")
        if change_20d is not None:
            trend_parts.append(f"20日:{change_20d:+.1f}%")
        if change_60d is not None:
            trend_parts.append(f"60日:{change_60d:+.1f}%")
        if trend_parts:
            lines.append("价格走势: " + ", ".join(trend_parts))

        if ma20 is not None and ma60 is not None and current_price:
            ma_status = "多头排列" if current_price > ma20 > ma60 else ("空头排列" if current_price < ma20 < ma60 else "震荡")
            lines.append(f"均线: MA20={ma20:.2f}, MA60={ma60:.2f} ({ma_status})")

        if volume_change is not None:
            vol_desc = "放量" if volume_change > 30 else ("缩量" if volume_change < -30 else "平稳")
            lines.append(f"成交量: 近5日vs前20日 {volume_change:+.0f}% ({vol_desc})")

        if high_60d is not None and low_60d is not None and current_price:
            position = (float(current_price) - low_60d) / (high_60d - low_60d) * 100 if high_60d != low_60d else 50
            lines.append(f"60日区间: {low_60d:.2f}-{high_60d:.2f} (当前{position:.0f}%位置)")

        # Fundamentals
        lines.append("")
        lines.append("== 基本面 ==")
        if pe is not None:
            pe_str = f"PE: {pe:.1f}"
            if pe_percentile is not None:
                pe_str += f" (历史{pe_percentile}%分位)"
            lines.append(pe_str)
        if pb is not None:
            lines.append(f"PB: {pb:.2f}")
        if revenue_growth is not None:
            lines.append(f"营收增长: {revenue_growth * 100:.1f}%")
        if target_price and current_price:
            upside = (target_price - float(current_price)) / float(current_price) * 100
            lines.append(f"目标价: {target_price:.2f} (空间{upside:+.1f}%)")
        if analyst_rating:
            lines.append(f"分析师评级: {analyst_rating}")

        # ETF NAV
        if nav_data:
            nav = nav_data.get("unit_nav")
            if nav and current_price:
                premium = (float(current_price) - nav) / nav * 100 if nav > 0 else 0
                lines.append(f"基金净值: {nav:.4f} ({'溢价' if premium >= 0 else '折价'}{abs(premium):.2f}%)")

        # Sector context
        if sector_perf or sector_flow:
            lines.append("")
            lines.append("== 所属板块 ==")
            if sector_perf:
                lines.append(f"板块涨跌: {sector_perf.get('change_pct', 0):.1f}%")
                if sector_perf.get("leading_stock"):
                    lines.append(f"领涨股: {sector_perf['leading_stock']}")
            if sector_flow:
                flow = sector_flow.get("net_inflow", 0)
                direction = sector_flow.get("direction", "")
                consecutive = sector_flow.get("consecutive_weeks", 0)
                lines.append(f"板块资金: {'流入' if flow > 0 else '流出'}{abs(flow):.1f}亿, 连续{consecutive}周{direction}")

        # Northbound holding
        if nb_holding:
            lines.append("")
            lines.append("== 北向资金 ==")
            if nb_holding.get("holding"):
                lines.append(f"持股量: {nb_holding['holding'] / 10000:.0f}万股")
            if nb_holding.get("change_pct") is not None:
                change_pct = nb_holding["change_pct"]
                lines.append(f"28日变化: {'增持' if change_pct > 0 else '减持'}{abs(change_pct):.1f}%")

        # Signals
        if signals:
            lines.append("")
            lines.append("== 本周信号 ==")
            for sig in signals:
                lines.append(f"  - [{sig.severity.value}] {sig.title}: {sig.description}")

        user_msg = "\n".join(lines)

        try:
            raw = await self._llm.chat_with_system(
                WEEKLY_HOLDING_SYSTEM_PROMPT, user_msg, model=ModelChoice.QUALITY,
                max_tokens=4000,
            )
            return _parse_llm_json(raw)
        except (LLMError, json.JSONDecodeError, ValueError, SyntaxError) as e:
            logger.warning("Failed to get weekly AI for %s: %s", entry["symbol"], e)
            return None

    # ------------------------------------------------------------------
    # Risk alerts
    # ------------------------------------------------------------------

    def _build_risk_alerts(self) -> List[Dict[str, Any]]:
        """Build risk alerts from PortfolioHealthAnalyzer."""
        from src.analyzers.portfolio_health import PortfolioHealthAnalyzer

        analyzer = PortfolioHealthAnalyzer(self.db)
        report = analyzer.analyze()

        alerts: List[Dict[str, Any]] = []

        if not report.data:
            return alerts

        # Concentration risk
        holdings_data = report.data.get("holdings", [])
        total_val = report.data.get("total_value_cny", 1)
        for pos in holdings_data:
            weight = pos["market_value_cny"] / total_val * 100 if total_val else 0
            if weight > 25:
                alerts.append({
                    "level": "high",
                    "message": f"{pos['symbol']} 持仓集中度过高（{weight:.0f}%）",
                })

        # Risk warnings from health analyzer
        risk_warnings = report.data.get("risk_warnings", [])
        for warning in risk_warnings:
            alerts.append({
                "level": "medium",
                "message": warning,
            })

        # Tier deviation warnings
        if report.details:
            for detail in report.details:
                if "[层级偏离]" in detail:
                    alerts.append({
                        "level": "low",
                        "message": detail.replace("[层级偏离] ", ""),
                    })

        return alerts

    # ------------------------------------------------------------------
    # Weekly AI summary
    # ------------------------------------------------------------------

    def _generate_week_summary_ai(
        self,
        week_summary: Dict[str, Any],
        macro_capital: Dict[str, Any],
        holdings: List[Dict[str, Any]],
    ) -> str:
        """Generate AI summary for the week using QUALITY model."""
        lines = [
            f"本周盈亏: {'+' if week_summary['week_pnl'] >= 0 else ''}{week_summary['week_pnl']:.0f}元 ({'+' if week_summary['week_pnl_pct'] >= 0 else ''}{week_summary['week_pnl_pct']:.1f}%)",
        ]
        if week_summary.get("best_holding"):
            bh = week_summary["best_holding"]
            lines.append(f"最佳持仓: {bh['symbol']} ({'+' if bh['pnl_pct'] >= 0 else ''}{bh['pnl_pct']:.1f}%)")
        if week_summary.get("worst_holding"):
            wh = week_summary["worst_holding"]
            lines.append(f"最差持仓: {wh['symbol']} ({'+' if wh['pnl_pct'] >= 0 else ''}{wh['pnl_pct']:.1f}%)")

        # Macro scores
        lines.append("")
        lines.append("== 宏观环境 ==")
        if macro_capital.get("us_score") is not None:
            lines.append(f"美国宏观评分: {macro_capital['us_score']}/100")
        if macro_capital.get("cn_score") is not None:
            lines.append(f"中国宏观评分: {macro_capital['cn_score']}/100")

        # Yield spread
        yield_spread = macro_capital.get("yield_spread")
        if yield_spread:
            spread = yield_spread.get("spread", 0)
            inverted = "倒挂" if yield_spread.get("is_inverted") else "正常"
            lines.append(f"美债利差(10Y-2Y): {spread:.2f}% ({inverted})")

        # Index valuations
        index_vals = macro_capital.get("index_valuations", [])
        for idx in index_vals:
            pe = idx.get("pe")
            pct = idx.get("pe_percentile")
            if pe is not None and pct is not None:
                lines.append(f"{idx.get('name', idx['ts_code'])} PE: {pe:.1f} (历史{pct}%分位)")

        # Capital flow
        lines.append("")
        lines.append("== 资金流向 ==")
        nb_detail = macro_capital.get("northbound_detail", {})
        if nb_detail.get("today_volume"):
            lines.append(
                f"北向交易额: 最新日{nb_detail['today_volume']:.1f}亿 "
                f"(沪股通{nb_detail.get('today_hgt', 0):.1f}亿 + 深股通{nb_detail.get('today_sgt', 0):.1f}亿)"
            )
            vol_change = nb_detail.get("vol_change_pct", 0)
            lines.append(
                f"日环比: {'+' if vol_change >= 0 else ''}{vol_change:.1f}%, "
                f"5日均量{nb_detail.get('avg_5d_volume', 0):.1f}亿, "
                f"活跃度: {nb_detail.get('activity', '未知')}"
            )

        # Market breadth
        breadth = macro_capital.get("market_breadth", [])
        for b in breadth[:2]:
            adv = b.get("advancing", 0)
            dec = b.get("declining", 0)
            total = adv + dec
            if total > 0:
                lines.append(f"{b.get('index_name', '')}: 涨{adv}家, 跌{dec}家 (涨跌比{adv/dec:.2f})" if dec > 0 else f"{b.get('index_name', '')}: 涨{adv}家")

        # Commodities
        commodities = macro_capital.get("commodities", [])
        if commodities:
            lines.append("")
            lines.append("== 大宗商品 ==")
            for c in commodities[:5]:
                if c["symbol"] == "GOLD_SILVER_RATIO":
                    lines.append(f"金银比: {c['value']:.1f}")
                elif c["symbol"] == "^VIX":
                    lines.append(f"VIX恐慌指数: {c['value']:.1f} (60日{c.get('percentile_60d', 50)}%分位)")
                else:
                    pct = c.get("percentile_60d")
                    change = c.get("change_pct", 0)
                    lines.append(f"{c['name']}: {c['value']:.2f} ({change:+.1f}%, 60日{pct}%分位)" if pct else f"{c['name']}: {c['value']:.2f}")

        # Key events
        if macro_capital.get("key_events"):
            lines.append("")
            lines.append(f"本周关键事件: {', '.join(macro_capital['key_events'][:3])}")

        # Holdings overview
        lines.append("")
        lines.append("== 持仓概况 ==")
        for h in holdings[:5]:
            lines.append(
                f"  {h['name']}({h['symbol']}): 本周{'+' if h['week_change_pct'] >= 0 else ''}{h['week_change_pct']:.1f}%, "
                f"仓位{h['weight_pct']:.1f}%"
            )

        user_msg = "\n".join(lines)

        try:
            raw = asyncio.run(
                self._llm.chat_with_system(
                    WEEKLY_SUMMARY_SYSTEM_PROMPT, user_msg, model=ModelChoice.QUALITY
                )
            )
            summary = raw.strip().strip('"').strip("'")
            if summary:
                return summary
        except (LLMError, RuntimeError) as e:
            logger.warning("Failed to generate weekly AI summary: %s", e)

        # Fallback template
        pnl = week_summary.get("week_pnl", 0)
        direction = "上涨" if pnl >= 0 else "下跌"
        return f"本周持仓整体{direction}{abs(week_summary.get('week_pnl_pct', 0)):.1f}%，盈亏{pnl:+.0f}元"
