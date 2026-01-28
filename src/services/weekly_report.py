"""Weekly report generation service (template-based, no LLM)."""
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
    Tier.STABLE: Decimal("40"),
    Tier.MEDIUM: Decimal("30"),
    Tier.GAMBLE: Decimal("30"),
}

TIER_LABELS = {
    Tier.STABLE: "稳健层",
    Tier.MEDIUM: "中等风险层",
    Tier.GAMBLE: "Gamble层",
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


# ===== Service =====

class WeeklyReportService:
    """Generate weekly investment summary reports."""

    def generate_report(self, db: Session) -> WeeklyReport:
        """Generate a full weekly report."""
        portfolio_summary = self._build_portfolio_summary(db)
        signal_summary = self._build_signal_summary(db)
        risk_alerts = self._build_risk_alerts(db)

        # Gather info for action items
        holdings = db.query(Holding).filter(Holding.status == HoldingStatus.ACTIVE).all()
        week_ago = datetime.now() - timedelta(days=7)
        critical_signals = db.query(Signal).filter(
            Signal.severity == SignalSeverity.CRITICAL,
            Signal.status == SignalStatus.ACTIVE,
            Signal.created_at >= week_ago,
        ).all()

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

    def _build_portfolio_summary(self, db: Session) -> PortfolioSummary:
        """Build three-tier portfolio allocation summary."""
        holdings = db.query(Holding).filter(Holding.status == HoldingStatus.ACTIVE).all()

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

    def _build_signal_summary(self, db: Session) -> List[SignalSummaryItem]:
        """Build weekly signal summary grouped by sector."""
        week_ago = datetime.now() - timedelta(days=7)
        signals = db.query(Signal).filter(Signal.created_at >= week_ago).all()

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

    def _build_risk_alerts(self, db: Session) -> List[RiskAlert]:
        """Build risk alerts for current portfolio."""
        holdings = db.query(Holding).filter(Holding.status == HoldingStatus.ACTIVE).all()

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
