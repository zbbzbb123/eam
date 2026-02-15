"""Report generation service — daily briefs and full weekly reports.

Supports:
- Legacy weekly report (template-based, no LLM)
- Daily brief report (macro + capital flow + commodities + short LLM summary)
- Full weekly report (all 5 analyzers + portfolio legacy data + full LLM advice)
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from src.db.models import (
    Holding, HoldingStatus, Tier, Market,
    Signal, SignalType, SignalSeverity, SignalStatus,
    DailyQuote,
)

logger = logging.getLogger(__name__)

# Target allocations per tier
TIER_TARGETS = {
    Tier.CORE: Decimal("40"),
    Tier.GROWTH: Decimal("30"),
    Tier.GAMBLE: Decimal("30"),
}

TIER_LABELS = {
    Tier.CORE: "核心层",
    Tier.GROWTH: "成长层",
    Tier.GAMBLE: "投机层",
}

SEVERITY_ORDER = {
    SignalSeverity.INFO: 0,
    SignalSeverity.LOW: 1,
    SignalSeverity.MEDIUM: 2,
    SignalSeverity.HIGH: 3,
    SignalSeverity.CRITICAL: 4,
}

# Thresholds
CONCENTRATION_THRESHOLD_PCT = Decimal("30")  # single holding > 30%
DEVIATION_ALERT_THRESHOLD = Decimal("10")  # tier deviation > 10%

# LLM system prompt for investment advice
LLM_SYSTEM_PROMPT = (
    "你是一位专业的投资顾问助手。根据以下市场分析数据，生成简洁的投资建议。\n\n"
    "要求：\n"
    "1. 用中文回答\n"
    "2. 结合宏观环境、资金面、持仓状况给出综合判断\n"
    "3. 对每个持仓给出明确建议：加仓/持有/减仓/观望\n"
    "4. 对watchlist标的评估是否值得入场\n"
    "5. 给出风控提醒\n"
    "6. 语气专业但易懂"
)


# ===== Data classes =====

@dataclass
class TierSummary:
    tier: Tier
    target_pct: Decimal
    actual_pct: Decimal
    deviation_pct: Decimal
    market_value: Decimal
    holdings_count: int


@dataclass
class PortfolioSummary:
    total_value: Decimal
    tiers: List[TierSummary]


@dataclass
class SignalSummaryItem:
    sector: str
    count: int
    max_severity: SignalSeverity
    titles: List[str]


@dataclass
class RiskAlert:
    level: str
    message: str
    symbol: Optional[str] = None


@dataclass
class ActionItem:
    priority: str
    description: str


@dataclass
class WeeklyReport:
    report_date: date
    portfolio_summary: PortfolioSummary
    signal_summary: List[SignalSummaryItem]
    risk_alerts: List[RiskAlert]
    action_items: List[ActionItem]


@dataclass
class AnalyzerSection:
    """One section from a ReportAnalyzer."""
    name: str
    rating: Optional[str]
    score: Optional[int]
    summary: str
    details: List[str]
    recommendations: List[str]
    data: Optional[dict] = None


@dataclass
class EnhancedReport:
    """Full enhanced report with all analyzer sections + LLM advice."""
    report_date: date
    report_type: str  # "daily" or "weekly"
    sections: List[AnalyzerSection]  # ordered analyzer results
    ai_advice: Optional[str] = None  # LLM-generated advice
    # Legacy fields for backward compatibility
    portfolio_summary: Optional[PortfolioSummary] = None
    signal_summary: List[SignalSummaryItem] = field(default_factory=list)
    risk_alerts: List[RiskAlert] = field(default_factory=list)
    action_items: List[ActionItem] = field(default_factory=list)


# ===== Service =====

class ReportService:
    """Generate daily briefs, full weekly reports, and legacy weekly reports."""

    # ------------------------------------------------------------------
    # New enhanced report methods
    # ------------------------------------------------------------------

    def generate_daily_report(self, db: Session, user_id: Optional[int] = None) -> EnhancedReport:
        """Daily brief: MarketEnvironment + CapitalFlow + Commodity + short LLM summary."""
        # Lazy imports to avoid circular dependencies
        from src.analyzers.market_environment import MarketEnvironmentAnalyzer
        from src.analyzers.capital_flow import CapitalFlowAnalyzer
        from src.analyzers.commodity import CommodityAnalyzer

        daily_analyzers = [
            MarketEnvironmentAnalyzer(db),
            CapitalFlowAnalyzer(db),
            CommodityAnalyzer(db),
        ]

        sections = self._run_analyzers(daily_analyzers)

        # Generate short LLM advice
        ai_advice = self._safe_llm_advice(sections, report_type="daily")

        return EnhancedReport(
            report_date=date.today(),
            report_type="daily",
            sections=sections,
            ai_advice=ai_advice,
        )

    def generate_weekly_report(self, db: Session, user_id: Optional[int] = None) -> EnhancedReport:
        """Full weekly: all 5 analyzers + portfolio legacy data + full LLM advice."""
        # Lazy imports to avoid circular dependencies
        from src.analyzers.market_environment import MarketEnvironmentAnalyzer
        from src.analyzers.capital_flow import CapitalFlowAnalyzer
        from src.analyzers.portfolio_health import PortfolioHealthAnalyzer
        from src.analyzers.commodity import CommodityAnalyzer
        from src.analyzers.watchlist_analyzer import WatchlistAnalyzer

        all_analyzers = [
            MarketEnvironmentAnalyzer(db),
            CapitalFlowAnalyzer(db),
            PortfolioHealthAnalyzer(db, user_id=user_id),
            CommodityAnalyzer(db),
            WatchlistAnalyzer(db, user_id=user_id),
        ]

        sections = self._run_analyzers(all_analyzers)

        # Build legacy data for backward compatibility
        portfolio_summary = self._build_portfolio_summary(db, user_id=user_id)
        signal_summary = self._build_signal_summary(db, user_id=user_id)
        risk_alerts = self._build_risk_alerts(db, user_id=user_id)

        holdings_query = db.query(Holding).filter(Holding.status == HoldingStatus.ACTIVE)
        if user_id is not None:
            holdings_query = holdings_query.filter(Holding.user_id == user_id)
        holdings = holdings_query.all()
        week_ago = datetime.now() - timedelta(days=7)
        signals_query = db.query(Signal).filter(
            Signal.severity == SignalSeverity.CRITICAL,
            Signal.status == SignalStatus.ACTIVE,
            Signal.created_at >= week_ago,
        )
        if user_id is not None:
            signals_query = signals_query.filter(Signal.user_id == user_id)
        critical_signals = signals_query.all()
        action_items = self._build_action_items(
            db, holdings=holdings, critical_signals=critical_signals,
        )

        # Generate full LLM advice
        ai_advice = self._safe_llm_advice(sections, report_type="weekly")

        return EnhancedReport(
            report_date=date.today(),
            report_type="weekly",
            sections=sections,
            ai_advice=ai_advice,
            portfolio_summary=portfolio_summary,
            signal_summary=signal_summary,
            risk_alerts=risk_alerts,
            action_items=action_items,
        )

    # ------------------------------------------------------------------
    # Legacy report method (backward compatible)
    # ------------------------------------------------------------------

    def generate_report(self, db: Session, user_id: Optional[int] = None) -> WeeklyReport:
        """Generate a full weekly report (legacy format)."""
        portfolio_summary = self._build_portfolio_summary(db, user_id=user_id)
        signal_summary = self._build_signal_summary(db, user_id=user_id)
        risk_alerts = self._build_risk_alerts(db, user_id=user_id)

        # Gather info for action items
        holdings_query = db.query(Holding).filter(Holding.status == HoldingStatus.ACTIVE)
        if user_id is not None:
            holdings_query = holdings_query.filter(Holding.user_id == user_id)
        holdings = holdings_query.all()
        week_ago = datetime.now() - timedelta(days=7)
        signals_query = db.query(Signal).filter(
            Signal.severity == SignalSeverity.CRITICAL,
            Signal.status == SignalStatus.ACTIVE,
            Signal.created_at >= week_ago,
        )
        if user_id is not None:
            signals_query = signals_query.filter(Signal.user_id == user_id)
        critical_signals = signals_query.all()

        action_items = self._build_action_items(
            db, holdings=holdings, critical_signals=critical_signals
        )

        return WeeklyReport(
            report_date=date.today(),
            portfolio_summary=portfolio_summary,
            signal_summary=signal_summary,
            risk_alerts=risk_alerts,
            action_items=action_items,
        )

    # ------------------------------------------------------------------
    # Analyzer runner
    # ------------------------------------------------------------------

    def _run_analyzers(self, analyzers) -> List[AnalyzerSection]:
        """Run a list of ReportAnalyzers and collect AnalyzerSection results.

        Each analyzer is called independently; if one fails the rest still run.
        """
        sections: List[AnalyzerSection] = []
        for analyzer in analyzers:
            try:
                report = analyzer.analyze()
                sections.append(AnalyzerSection(
                    name=report.section_name,
                    rating=report.rating,
                    score=report.score,
                    summary=report.summary,
                    details=report.details,
                    recommendations=report.recommendations,
                    data=report.data,
                ))
            except Exception:
                logger.exception("Analyzer %s failed", getattr(analyzer, "name", type(analyzer).__name__))
                sections.append(AnalyzerSection(
                    name=getattr(analyzer, "name", type(analyzer).__name__),
                    rating=None,
                    score=None,
                    summary="分析器运行出错，数据暂不可用。",
                    details=[],
                    recommendations=[],
                ))
        return sections

    # ------------------------------------------------------------------
    # LLM advice generation
    # ------------------------------------------------------------------

    async def _generate_llm_advice(
        self,
        sections: List[AnalyzerSection],
        report_type: str,
    ) -> Optional[str]:
        """Call LLM to generate investment advice from analyzer sections.

        Args:
            sections: Ordered list of analyzer section results.
            report_type: "daily" or "weekly".

        Returns:
            LLM-generated advice string, or None on failure.
        """
        from src.services.llm_client import LLMClient, ModelChoice

        # Build user message from sections
        user_parts: List[str] = []
        for section in sections:
            part_lines = [f"### {section.name}"]
            if section.rating:
                part_lines.append(f"评级: {section.rating}")
            if section.score is not None:
                part_lines.append(f"评分: {section.score}/100")
            if section.summary:
                part_lines.append(f"摘要: {section.summary}")
            if section.recommendations:
                part_lines.append("建议:")
                for rec in section.recommendations:
                    part_lines.append(f"  - {rec}")
            user_parts.append("\n".join(part_lines))

        user_message = "\n\n".join(user_parts)

        if report_type == "daily":
            user_message = f"以下是今日市场简报数据，请给出简短投资建议（200字以内）：\n\n{user_message}"
            max_tokens = 1000
        else:
            user_message = f"以下是本周完整市场分析数据，请给出详细投资建议：\n\n{user_message}"
            max_tokens = 3000

        client = LLMClient(model=ModelChoice.FAST)
        messages = [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
        return await client.chat(messages, model=ModelChoice.FAST, max_tokens=max_tokens)

    def _safe_llm_advice(
        self,
        sections: List[AnalyzerSection],
        report_type: str,
    ) -> Optional[str]:
        """Call LLM advice from sync context, returning None on any failure."""
        try:
            return asyncio.run(self._generate_llm_advice(sections, report_type))
        except Exception:
            logger.exception("LLM advice generation failed for %s report", report_type)
            return None

    # ------------------------------------------------------------------
    # Legacy builders
    # ------------------------------------------------------------------

    def _get_holding_value(self, holding: Holding, db: Session) -> Decimal:
        """Get market value of a holding. Uses latest quote or falls back to cost basis."""
        quote = (
            db.query(DailyQuote)
            .filter(
                DailyQuote.symbol == holding.symbol,
                DailyQuote.market == holding.market,
            )
            .order_by(DailyQuote.trade_date.desc())
            .first()
        )
        price = quote.close if quote and quote.close else holding.avg_cost
        return holding.quantity * price

    def _build_portfolio_summary(self, db: Session, user_id: Optional[int] = None) -> PortfolioSummary:
        """Build three-tier portfolio allocation summary."""
        query = db.query(Holding).filter(Holding.status == HoldingStatus.ACTIVE)
        if user_id is not None:
            query = query.filter(Holding.user_id == user_id)
        holdings = query.all()

        if not holdings:
            return PortfolioSummary(
                total_value=Decimal("0"),
                tiers=[
                    TierSummary(
                        tier=tier,
                        target_pct=target,
                        actual_pct=Decimal("0"),
                        deviation_pct=Decimal("0") - target,
                        market_value=Decimal("0"),
                        holdings_count=0,
                    )
                    for tier, target in TIER_TARGETS.items()
                ],
            )

        # Calculate per-holding values
        holding_values = {}
        for h in holdings:
            holding_values[h.id] = self._get_holding_value(h, db)

        total_value = sum(holding_values.values())

        tier_data = {}
        for tier in Tier:
            tier_holdings = [h for h in holdings if h.tier == tier]
            tier_value = sum(holding_values.get(h.id, Decimal("0")) for h in tier_holdings)
            target = TIER_TARGETS[tier]
            actual = (tier_value / total_value * 100) if total_value else Decimal("0")
            tier_data[tier] = TierSummary(
                tier=tier,
                target_pct=target,
                actual_pct=actual,
                deviation_pct=actual - target,
                market_value=tier_value,
                holdings_count=len(tier_holdings),
            )

        return PortfolioSummary(
            total_value=total_value,
            tiers=list(tier_data.values()),
        )

    def _build_signal_summary(self, db: Session, user_id: Optional[int] = None) -> List[SignalSummaryItem]:
        """Build weekly signal summary grouped by sector."""
        week_ago = datetime.now() - timedelta(days=7)
        query = db.query(Signal).filter(Signal.created_at >= week_ago)
        if user_id is not None:
            query = query.filter(Signal.user_id == user_id)
        signals = query.all()

        if not signals:
            return []

        # Group by sector (or signal_type if no sector)
        groups: dict[str, list[Signal]] = {}
        for s in signals:
            key = s.sector if s.sector else s.signal_type.value
            groups.setdefault(key, []).append(s)

        result = []
        for sector, sigs in groups.items():
            max_sev = max(sigs, key=lambda s: SEVERITY_ORDER.get(s.severity, 0)).severity
            result.append(SignalSummaryItem(
                sector=sector,
                count=len(sigs),
                max_severity=max_sev,
                titles=[s.title for s in sigs],
            ))

        return result

    def _build_risk_alerts(self, db: Session, user_id: Optional[int] = None) -> List[RiskAlert]:
        """Build risk alerts for current portfolio."""
        query = db.query(Holding).filter(Holding.status == HoldingStatus.ACTIVE)
        if user_id is not None:
            query = query.filter(Holding.user_id == user_id)
        holdings = query.all()

        if not holdings:
            return []

        alerts: List[RiskAlert] = []

        # Calculate values
        holding_values = {}
        for h in holdings:
            holding_values[h.id] = self._get_holding_value(h, db)
        total_value = sum(holding_values.values())

        # 1. Concentration risk
        if total_value > 0:
            for h in holdings:
                pct = holding_values[h.id] / total_value * 100
                if pct >= CONCENTRATION_THRESHOLD_PCT:
                    alerts.append(RiskAlert(
                        level="high",
                        message=f"{h.symbol} 集中度过高 ({pct:.0f}%)",
                        symbol=h.symbol,
                    ))

        # 2. Missing stop loss
        for h in holdings:
            if h.stop_loss_price is None:
                alerts.append(RiskAlert(
                    level="medium",
                    message=f"{h.symbol} 未设置止损价 (stop loss)",
                    symbol=h.symbol,
                ))

        # 3. Tier deviation
        if total_value > 0:
            for tier in Tier:
                tier_holdings = [h for h in holdings if h.tier == tier]
                tier_value = sum(holding_values.get(h.id, Decimal("0")) for h in tier_holdings)
                actual_pct = tier_value / total_value * 100
                target_pct = TIER_TARGETS[tier]
                deviation = abs(actual_pct - target_pct)
                if deviation >= DEVIATION_ALERT_THRESHOLD:
                    label = TIER_LABELS.get(tier, tier.value)
                    alerts.append(RiskAlert(
                        level="high",
                        message=f"{label} 偏离目标 {deviation:.0f}%，建议再平衡",
                    ))

        return alerts

    def _build_action_items(
        self,
        db: Session,
        holdings: Optional[List[Holding]] = None,
        critical_signals: Optional[List[Signal]] = None,
    ) -> List[ActionItem]:
        """Build action items list."""
        items: List[ActionItem] = []

        # Check for rebalance need
        if holdings:
            holding_values = {}
            total = Decimal("0")
            for h in holdings:
                val = self._get_holding_value(h, db)
                holding_values[h.id] = val
                total += val

            if total > 0:
                for tier in Tier:
                    tier_value = sum(
                        holding_values.get(h.id, Decimal("0"))
                        for h in holdings if h.tier == tier
                    )
                    actual = tier_value / total * 100
                    target = TIER_TARGETS[tier]
                    if abs(actual - target) >= DEVIATION_ALERT_THRESHOLD:
                        items.append(ActionItem(
                            priority="high",
                            description=f"检查再平衡需求：{TIER_LABELS.get(tier, tier.value)}偏离目标",
                        ))
                        break  # one rebalance item is enough

        # Check for critical signals needing attention
        if critical_signals:
            items.append(ActionItem(
                priority="high",
                description=f"处理 {len(critical_signals)} 条关键信号",
            ))

        # Check holdings without stop loss
        if holdings:
            no_sl = [h for h in holdings if h.stop_loss_price is None]
            if no_sl:
                symbols = ", ".join(h.symbol for h in no_sl[:5])
                items.append(ActionItem(
                    priority="medium",
                    description=f"为以下持仓设置止损：{symbols}",
                ))

        return items

    # ------------------------------------------------------------------
    # Legacy formatters (WeeklyReport)
    # ------------------------------------------------------------------

    def format_as_text(self, report: WeeklyReport) -> str:
        """Format report as plain text."""
        lines: List[str] = []
        lines.append(f"=== 周报 {report.report_date} ===")
        lines.append("")

        # 1. Portfolio summary
        lines.append("【仓位全景】")
        ps = report.portfolio_summary
        lines.append(f"总市值: {ps.total_value:,.2f}")
        lines.append("")
        for ts in ps.tiers:
            label = TIER_LABELS.get(ts.tier, ts.tier.value)
            sign = "+" if ts.deviation_pct > 0 else ""
            lines.append(
                f"  {label}: 目标{ts.target_pct}% | 实际{ts.actual_pct:.1f}% | "
                f"偏离{sign}{ts.deviation_pct:.1f}% | 市值{ts.market_value:,.2f} | "
                f"{ts.holdings_count}只"
            )
        lines.append("")

        # 2. Signal summary
        lines.append("【板块信号汇总】")
        if report.signal_summary:
            for item in report.signal_summary:
                lines.append(f"  {item.sector} ({item.count}条, 最高{item.max_severity.value}):")
                for title in item.titles:
                    lines.append(f"    - {title}")
        else:
            lines.append("  本周无信号")
        lines.append("")

        # 3. Risk alerts
        lines.append("【风险预警】")
        if report.risk_alerts:
            for alert in report.risk_alerts:
                lines.append(f"  [{alert.level.upper()}] {alert.message}")
        else:
            lines.append("  无风险预警")
        lines.append("")

        # 4. Action items
        lines.append("【本周待办】")
        if report.action_items:
            for i, item in enumerate(report.action_items, 1):
                lines.append(f"  {i}. [{item.priority.upper()}] {item.description}")
        else:
            lines.append("  无待办事项")

        return "\n".join(lines)

    def format_as_markdown(self, report: WeeklyReport) -> str:
        """Format report as Markdown."""
        lines: List[str] = []
        lines.append(f"# 投资周报 {report.report_date}")
        lines.append("")

        # 1. Portfolio
        lines.append("## 仓位全景")
        ps = report.portfolio_summary
        lines.append(f"**总市值**: {ps.total_value:,.2f}")
        lines.append("")
        lines.append("| 层级 | 目标 | 实际 | 偏离 | 市值 | 持仓数 |")
        lines.append("|------|------|------|------|------|--------|")
        for ts in ps.tiers:
            label = TIER_LABELS.get(ts.tier, ts.tier.value)
            sign = "+" if ts.deviation_pct > 0 else ""
            lines.append(
                f"| {label} | {ts.target_pct}% | {ts.actual_pct:.1f}% | "
                f"{sign}{ts.deviation_pct:.1f}% | {ts.market_value:,.2f} | {ts.holdings_count} |"
            )
        lines.append("")

        # 2. Signals
        lines.append("## 板块信号汇总")
        if report.signal_summary:
            for item in report.signal_summary:
                lines.append(f"### {item.sector} ({item.count}条, 最高: {item.max_severity.value})")
                for title in item.titles:
                    lines.append(f"- {title}")
                lines.append("")
        else:
            lines.append("本周无信号")
            lines.append("")

        # 3. Risk
        lines.append("## 风险预警")
        if report.risk_alerts:
            for alert in report.risk_alerts:
                lines.append(f"- **[{alert.level.upper()}]** {alert.message}")
        else:
            lines.append("无风险预警")
        lines.append("")

        # 4. Actions
        lines.append("## 本周待办")
        if report.action_items:
            for item in report.action_items:
                lines.append(f"- [ ] **[{item.priority.upper()}]** {item.description}")
        else:
            lines.append("无待办事项")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Enhanced report formatters
    # ------------------------------------------------------------------

    def format_enhanced_as_markdown(self, report: EnhancedReport) -> str:
        """Format EnhancedReport as markdown."""
        lines: List[str] = []

        if report.report_type == "daily":
            lines.append(f"# 每日简报 {report.report_date}")
        else:
            lines.append(f"# 投资周报 {report.report_date}")
        lines.append("")

        # Analyzer sections
        for section in report.sections:
            lines.append(f"## {section.name}")

            meta_parts = []
            if section.rating:
                meta_parts.append(f"**评级**: {section.rating}")
            if section.score is not None:
                meta_parts.append(f"**评分**: {section.score}/100")
            if meta_parts:
                lines.append(" | ".join(meta_parts))
                lines.append("")

            if section.summary:
                lines.append(section.summary)
                lines.append("")

            if section.details:
                lines.append("### 详细分析")
                for detail in section.details:
                    lines.append(f"- {detail}")
                lines.append("")

            if section.recommendations:
                lines.append("### 建议")
                for rec in section.recommendations:
                    lines.append(f"- {rec}")
                lines.append("")

        # Legacy portfolio section for weekly reports
        if report.report_type == "weekly" and report.portfolio_summary:
            ps = report.portfolio_summary
            lines.append("## 仓位全景")
            lines.append(f"**总市值**: {ps.total_value:,.2f}")
            lines.append("")
            lines.append("| 层级 | 目标 | 实际 | 偏离 | 市值 | 持仓数 |")
            lines.append("|------|------|------|------|------|--------|")
            for ts in ps.tiers:
                label = TIER_LABELS.get(ts.tier, ts.tier.value)
                sign = "+" if ts.deviation_pct > 0 else ""
                lines.append(
                    f"| {label} | {ts.target_pct}% | {ts.actual_pct:.1f}% | "
                    f"{sign}{ts.deviation_pct:.1f}% | {ts.market_value:,.2f} | {ts.holdings_count} |"
                )
            lines.append("")

        # Legacy signal summary for weekly reports
        if report.report_type == "weekly" and report.signal_summary:
            lines.append("## 板块信号汇总")
            for item in report.signal_summary:
                lines.append(f"### {item.sector} ({item.count}条, 最高: {item.max_severity.value})")
                for title in item.titles:
                    lines.append(f"- {title}")
                lines.append("")

        # Legacy risk alerts for weekly reports
        if report.report_type == "weekly" and report.risk_alerts:
            lines.append("## 风险预警")
            for alert in report.risk_alerts:
                lines.append(f"- **[{alert.level.upper()}]** {alert.message}")
            lines.append("")

        # Legacy action items for weekly reports
        if report.report_type == "weekly" and report.action_items:
            lines.append("## 本周待办")
            for item in report.action_items:
                lines.append(f"- [ ] **[{item.priority.upper()}]** {item.description}")
            lines.append("")

        # AI advice section
        if report.ai_advice:
            lines.append("## AI投资建议")
            lines.append(report.ai_advice)
            lines.append("")

        return "\n".join(lines)

    def format_enhanced_as_text(self, report: EnhancedReport) -> str:
        """Format EnhancedReport as plain text."""
        lines: List[str] = []

        if report.report_type == "daily":
            lines.append(f"=== 每日简报 {report.report_date} ===")
        else:
            lines.append(f"=== 投资周报 {report.report_date} ===")
        lines.append("")

        # Analyzer sections
        for section in report.sections:
            lines.append(f"【{section.name}】")

            meta_parts = []
            if section.rating:
                meta_parts.append(f"评级: {section.rating}")
            if section.score is not None:
                meta_parts.append(f"评分: {section.score}/100")
            if meta_parts:
                lines.append("  " + " | ".join(meta_parts))

            if section.summary:
                lines.append(f"  {section.summary}")

            if section.details:
                lines.append("  详细分析:")
                for detail in section.details:
                    lines.append(f"    - {detail}")

            if section.recommendations:
                lines.append("  建议:")
                for rec in section.recommendations:
                    lines.append(f"    - {rec}")

            lines.append("")

        # Legacy portfolio section for weekly reports
        if report.report_type == "weekly" and report.portfolio_summary:
            ps = report.portfolio_summary
            lines.append("【仓位全景】")
            lines.append(f"总市值: {ps.total_value:,.2f}")
            lines.append("")
            for ts in ps.tiers:
                label = TIER_LABELS.get(ts.tier, ts.tier.value)
                sign = "+" if ts.deviation_pct > 0 else ""
                lines.append(
                    f"  {label}: 目标{ts.target_pct}% | 实际{ts.actual_pct:.1f}% | "
                    f"偏离{sign}{ts.deviation_pct:.1f}% | 市值{ts.market_value:,.2f} | "
                    f"{ts.holdings_count}只"
                )
            lines.append("")

        # Legacy signal summary for weekly reports
        if report.report_type == "weekly" and report.signal_summary:
            lines.append("【板块信号汇总】")
            for item in report.signal_summary:
                lines.append(f"  {item.sector} ({item.count}条, 最高{item.max_severity.value}):")
                for title in item.titles:
                    lines.append(f"    - {title}")
            lines.append("")

        # Legacy risk alerts for weekly reports
        if report.report_type == "weekly" and report.risk_alerts:
            lines.append("【风险预警】")
            for alert in report.risk_alerts:
                lines.append(f"  [{alert.level.upper()}] {alert.message}")
            lines.append("")

        # Legacy action items for weekly reports
        if report.report_type == "weekly" and report.action_items:
            lines.append("【本周待办】")
            for i, item in enumerate(report.action_items, 1):
                lines.append(f"  {i}. [{item.priority.upper()}] {item.description}")
            lines.append("")

        # AI advice section
        if report.ai_advice:
            lines.append("【AI投资建议】")
            lines.append(f"  {report.ai_advice}")
            lines.append("")

        return "\n".join(lines)


# Backward-compatible alias
WeeklyReportService = ReportService
