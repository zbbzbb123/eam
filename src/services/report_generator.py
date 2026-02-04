"""Report generator service — creates and stores daily/weekly reports."""
import asyncio
import json
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.db.models import (
    Holding, HoldingStatus, Market, Tier, DailyQuote, Signal, Watchlist,
)
from src.db.models_market_data import (
    GeneratedReport, MarketIndicatorSnapshot, FundNavSnapshot, FundamentalSnapshot,
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


class DailyReportGenerator:
    """Generates pre-stored daily reports with per-holding AI commentary."""

    def __init__(self, db: Session):
        self.db = db
        self._llm = LLMClient()
        self._usd_cny: Optional[Decimal] = None

    def generate(self) -> int:
        """Generate a daily report and save to DB. Returns report ID."""
        now = datetime.now()
        self._usd_cny = self._get_usd_cny_rate()

        # 1. Build holdings data with P&L
        holdings_data, total_value_cny, cash_pct = self._build_holdings_data()

        # 2. Calculate today's change for each holding
        self._enrich_today_change(holdings_data)

        # 3. Sort by today_change_pct ascending (worst first)
        holdings_data.sort(key=lambda h: h.get("today_change_pct") or 0)

        # 4. AI commentary for each holding
        self._enrich_with_ai(holdings_data, total_value_cny)

        # 5. Scan opportunities (watchlist + related sectors)
        opportunities = self._scan_opportunities()

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
    # Price helpers (same pattern as PortfolioHealthAnalyzer)
    # ------------------------------------------------------------------

    def _get_usd_cny_rate(self) -> Decimal:
        """Get latest USD/CNY rate from MarketIndicatorSnapshot."""
        row = (
            self.db.query(MarketIndicatorSnapshot)
            .filter(MarketIndicatorSnapshot.symbol == "CNY=X")
            .order_by(desc(MarketIndicatorSnapshot.date))
            .first()
        )
        if row and row.value:
            return Decimal(str(row.value))
        return Decimal("7.25")  # sensible fallback

    def _get_latest_price_cn_etf(self, symbol: str) -> Optional[Decimal]:
        """Try FundNavSnapshot first, then DailyQuote for CN ETFs."""
        ts_code = _symbol_to_ts_code(symbol)
        nav = (
            self.db.query(FundNavSnapshot)
            .filter(FundNavSnapshot.ts_code == ts_code)
            .order_by(desc(FundNavSnapshot.nav_date))
            .first()
        )
        if nav and nav.unit_nav:
            return Decimal(str(nav.unit_nav))

        quote = (
            self.db.query(DailyQuote)
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

    def _get_latest_price(self, holding: Holding) -> Decimal:
        """Return latest price for a holding. Fallback to avg_cost."""
        if holding.symbol == "CASH":
            return Decimal("1")

        if holding.market == Market.CN and _is_cn_etf(holding.symbol):
            price = self._get_latest_price_cn_etf(holding.symbol)
            if price is not None:
                return price

        quote = (
            self.db.query(DailyQuote)
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

    def _to_cny(self, value: Decimal, market: Market, symbol: str) -> Decimal:
        """Convert a value in local currency to CNY."""
        if symbol == "CASH" or market == Market.CN:
            return value
        if market == Market.US:
            return value * self._usd_cny
        if market == Market.HK:
            return value * HKD_CNY_RATE
        return value

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
            price = self._get_latest_price(h)
            qty = Decimal(str(h.quantity))
            avg_cost = Decimal(str(h.avg_cost))
            local_value = price * qty
            value_cny = self._to_cny(local_value, h.market, h.symbol)
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
            total_pnl_cny = float(self._to_cny(pnl_local, h.market, h.symbol))

            name = self._get_stock_name(h.symbol, h.market)

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
                    pnl_cny = float(self._to_cny(pnl_local, market_enum, entry["symbol"]))
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
        # Fetch related signals
        signals = (
            self.db.query(Signal)
            .filter(Signal.related_symbols.contains(entry["symbol"]))
            .limit(5)
            .all()
        )

        # Build user prompt
        lines = [
            f"持仓: {entry['name']} ({entry['symbol']}.{entry['market']})",
            f"市场: {entry['market']} | 层级: {entry['tier']} | 仓位占比: {entry['weight_pct']}%",
            f"数量: {int(entry['quantity'])} | 均成本: {entry['avg_cost']:.2f} | 现价: {entry['current_price']:.2f}",
            f"总盈亏: {'+' if entry['total_pnl'] >= 0 else ''}{entry['total_pnl']:.0f} ({'+' if entry['total_pnl_pct'] >= 0 else ''}{entry['total_pnl_pct']:.1f}%)",
        ]
        if entry.get("today_change_pct") is not None:
            lines.append(f"今日涨跌: {'+' if entry['today_change_pct'] >= 0 else ''}{entry['today_change_pct']:.1f}%")
        if entry.get("stop_loss_price"):
            lines.append(f"止损价: {entry['stop_loss_price']:.2f}")
        if entry.get("take_profit_price"):
            lines.append(f"止盈价: {entry['take_profit_price']:.2f}")
        if signals:
            lines.append("相关信号:")
            for sig in signals:
                lines.append(f"  - [{sig.severity.value}] {sig.title}: {sig.description}")

        user_msg = "\n".join(lines)

        try:
            raw = await self._llm.chat_with_system(
                DAILY_HOLDING_SYSTEM_PROMPT, user_msg, model=ModelChoice.FAST
            )
            text = _strip_markdown_fences(raw)
            return json.loads(text)
        except (LLMError, json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to get AI for %s: %s", entry["symbol"], e)
            return None

    # ------------------------------------------------------------------
    # Opportunity scanning
    # ------------------------------------------------------------------

    def _scan_opportunities(self) -> List[Dict[str, Any]]:
        """Scan watchlist items for investment opportunities."""
        watchlist_items = self.db.query(Watchlist).all()
        if not watchlist_items:
            return []

        opportunities: List[Dict[str, Any]] = []

        for item in watchlist_items:
            market_value = item.market.value if isinstance(item.market, Market) else item.market
            fundamental = self._get_latest_fundamental(item.symbol, market_value)
            quotes = self._get_recent_quotes(item.symbol, item.market)

            # Current price
            price = None
            if quotes and quotes[-1].close is not None:
                price = float(quotes[-1].close)

            # PE
            pe = float(fundamental.pe_ratio) if fundamental and fundamental.pe_ratio else None

            # Revenue growth
            revenue_growth = (
                float(fundamental.revenue_growth)
                if fundamental and fundamental.revenue_growth is not None
                else None
            )

            # 30d change
            change_30d = self._calc_30d_change(quotes)

            # Target price / upside
            target_price = float(fundamental.target_price) if fundamental and fundamental.target_price else None
            upside = None
            if price and price > 0 and target_price:
                upside = (target_price - price) / price

            # Detect opportunity signals
            opp_signals = self._detect_opportunity(pe, revenue_growth, change_30d, upside)

            if not opp_signals:
                continue

            name = fundamental.name if fundamental and fundamental.name else item.symbol

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
            ai_result = self._get_opportunity_ai(
                opp_entry, item, fundamental, pe, revenue_growth, change_30d, opp_signals
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

    def _get_opportunity_ai(
        self,
        opp_entry: Dict[str, Any],
        item: Watchlist,
        fundamental: Optional[FundamentalSnapshot],
        pe: Optional[float],
        revenue_growth: Optional[float],
        change_30d: Optional[float],
        opp_signals: List[str],
    ) -> Optional[Dict[str, str]]:
        """Call LLM for opportunity analysis. Returns parsed dict or None."""
        lines = [
            f"标的: {opp_entry['name']} ({opp_entry['symbol']})",
            f"市场: {opp_entry['market']} | 主题: {item.theme}",
        ]
        if opp_entry.get("current_price"):
            lines.append(f"当前价: {opp_entry['current_price']:.2f}")
        if pe is not None:
            lines.append(f"PE: {pe:.1f}")
        if revenue_growth is not None:
            lines.append(f"营收增长: {revenue_growth * 100:.1f}%")
        if change_30d is not None:
            lines.append(f"30日涨跌: {change_30d * 100:.1f}%")
        if opp_entry.get("target_price"):
            lines.append(f"目标价: {opp_entry['target_price']:.2f}")
        lines.append(f"机会信号: {', '.join(opp_signals)}")

        user_msg = "\n".join(lines)

        try:
            raw = asyncio.run(
                self._llm.chat_with_system(
                    OPPORTUNITY_SYSTEM_PROMPT, user_msg, model=ModelChoice.FAST
                )
            )
            text = _strip_markdown_fences(raw)
            return json.loads(text)
        except (LLMError, json.JSONDecodeError, ValueError, RuntimeError) as e:
            logger.warning("Failed to get opportunity AI for %s: %s", opp_entry["symbol"], e)
            return None

    def _get_latest_fundamental(
        self, symbol: str, market_value: str
    ) -> Optional[FundamentalSnapshot]:
        """Get the latest fundamental snapshot for a symbol."""
        return (
            self.db.query(FundamentalSnapshot)
            .filter(
                FundamentalSnapshot.symbol == symbol,
                FundamentalSnapshot.market == market_value,
            )
            .order_by(FundamentalSnapshot.snapshot_date.desc())
            .first()
        )

    def _get_recent_quotes(
        self, symbol: str, market: Market
    ) -> List[DailyQuote]:
        """Get recent quotes (last 30 days) sorted ascending by date."""
        since = date.today() - timedelta(days=LOOKBACK_DAYS)
        return (
            self.db.query(DailyQuote)
            .filter(
                DailyQuote.symbol == symbol,
                DailyQuote.market == market,
                DailyQuote.trade_date >= since,
            )
            .order_by(DailyQuote.trade_date.asc())
            .all()
        )

    @staticmethod
    def _calc_30d_change(quotes: List[DailyQuote]) -> Optional[float]:
        """Calculate 30-day price change percentage."""
        if len(quotes) < 2:
            return None
        oldest_close = quotes[0].close
        newest_close = quotes[-1].close
        if oldest_close is None or newest_close is None or oldest_close == 0:
            return None
        return float((newest_close - oldest_close) / oldest_close)

    @staticmethod
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

    # ------------------------------------------------------------------
    # Stock name resolution
    # ------------------------------------------------------------------

    def _get_stock_name(self, symbol: str, market: Market) -> str:
        """Get stock name from FundamentalSnapshot or fallback to THEME_MAP/symbol."""
        if symbol == "CASH":
            return "现金"

        market_value = market.value if isinstance(market, Market) else market
        fundamental = (
            self.db.query(FundamentalSnapshot)
            .filter(
                FundamentalSnapshot.symbol == symbol,
                FundamentalSnapshot.market == market_value,
            )
            .order_by(FundamentalSnapshot.snapshot_date.desc())
            .first()
        )
        if fundamental and fundamental.name:
            return fundamental.name

        # Fallback to theme map or symbol itself
        return THEME_MAP.get(symbol, symbol)
