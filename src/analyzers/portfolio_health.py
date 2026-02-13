"""Portfolio health analyzer - overall portfolio assessment."""
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.analyzers.base import ReportAnalyzer, AnalysisReport, AnalyzerResult
from src.db.models import (
    Holding, HoldingStatus, Market, Tier, DailyQuote, SignalSeverity,
)
from src.db.models_market_data import (
    MarketIndicatorSnapshot, FundNavSnapshot, FundamentalSnapshot,
)

# ---------------------------------------------------------------------------
# Theme mapping
# ---------------------------------------------------------------------------
THEME_MAP = {
    "512480": "半导体",
    "159682": "电池/新能源",
    "159875": "新能源",
    "516560": "养老",
    "BABA": "美股科技",
    "QQQ": "美股科技",
    "GOOG": "美股科技",
    "01810": "港股科技",
    "CASH": "现金",
}

# Tier allocation targets
TIER_TARGETS = {
    Tier.STABLE: Decimal("0.40"),
    Tier.MEDIUM: Decimal("0.30"),
    Tier.GAMBLE: Decimal("0.30"),
}

# Growth themes used for concentration check
GROWTH_THEMES = {"半导体", "新能源", "电池/新能源"}

# Constant HKD -> CNY rate
HKD_CNY_RATE = Decimal("0.93")


def _symbol_to_ts_code(symbol: str) -> str:
    """Convert a 6-digit CN symbol to TuShare ts_code format."""
    if symbol.startswith(("5", "6")):
        return f"{symbol}.SH"
    return f"{symbol}.SZ"


def _is_cn_etf(symbol: str) -> bool:
    """Check if symbol looks like a 6-digit CN ETF code."""
    return symbol.isdigit() and len(symbol) == 6


class PortfolioHealthAnalyzer(ReportAnalyzer):
    """Produces a comprehensive portfolio health report."""

    def __init__(self, db: Session, user_id: Optional[int] = None):
        super().__init__(db, user_id=user_id)

    @property
    def name(self) -> str:
        return "portfolio_health"

    # ------------------------------------------------------------------
    # Price helpers
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
    # Core analysis
    # ------------------------------------------------------------------

    def analyze(self) -> AnalysisReport:
        query = self.db.query(Holding).filter(Holding.status == HoldingStatus.ACTIVE)
        if self.user_id is not None:
            query = query.filter(Holding.user_id == self.user_id)
        holdings = query.all()

        if not holdings:
            return AnalysisReport(
                section_name=self.name,
                rating="N/A",
                score=0,
                summary="No active holdings found.",
            )

        # Cache exchange rate
        self._usd_cny = self._get_usd_cny_rate()

        # 1. Build position details
        position_details: list[dict] = []
        total_value_cny = Decimal("0")
        market_values: dict[str, Decimal] = {"CN": Decimal("0"), "US": Decimal("0"), "HK": Decimal("0")}
        theme_values: dict[str, Decimal] = {}
        tier_values: dict[Tier, Decimal] = {t: Decimal("0") for t in Tier}
        cash_value_cny = Decimal("0")

        for h in holdings:
            price = self._get_latest_price(h)
            qty = Decimal(str(h.quantity))
            avg_cost = Decimal(str(h.avg_cost))

            local_value = price * qty
            value_cny = self._to_cny(local_value, h.market, h.symbol)

            pnl_local = (price - avg_cost) * qty
            pnl_pct = ((price - avg_cost) / avg_cost * 100) if avg_cost else Decimal("0")

            position_details.append({
                "symbol": h.symbol,
                "market": h.market.value,
                "tier": h.tier.value,
                "quantity": float(qty),
                "avg_cost": float(avg_cost),
                "latest_price": float(price),
                "market_value_cny": float(round(value_cny, 2)),
                "pnl": float(round(pnl_local, 2)),
                "pnl_pct": float(round(pnl_pct, 2)),
            })

            total_value_cny += value_cny

            if h.symbol == "CASH":
                cash_value_cny += value_cny
                market_values["CN"] += value_cny
            else:
                market_values[h.market.value] += value_cny

            # Theme
            theme = THEME_MAP.get(h.symbol, "其他")
            theme_values[theme] = theme_values.get(theme, Decimal("0")) + value_cny

            # Tier
            tier_values[h.tier] += value_cny

        # Avoid division by zero
        if total_value_cny == 0:
            total_value_cny = Decimal("1")

        # 2. Market distribution
        market_distribution = {
            k: float(round(v / total_value_cny * 100, 2))
            for k, v in market_values.items()
        }
        cash_pct = float(round(cash_value_cny / total_value_cny * 100, 2))

        # 3. Theme distribution
        theme_distribution = {
            k: float(round(v / total_value_cny * 100, 2))
            for k, v in theme_values.items()
        }

        # 4. Concentration risk
        details: list[str] = []
        recommendations: list[str] = []

        for pos in position_details:
            weight = pos["market_value_cny"] / float(total_value_cny) * 100
            if weight > 25:
                details.append(
                    f"[集中度风险] {pos['symbol']} 占比 {weight:.1f}%，超过25%阈值"
                )
                recommendations.append(
                    f"考虑减仓 {pos['symbol']}，单一持仓占比过高（{weight:.1f}%）"
                )

        # 5. Risk indicators
        risk_warnings: list[str] = []

        if cash_pct < 5:
            risk_warnings.append("加仓空间不足")
            details.append(f"[风险] 现金比例仅 {cash_pct:.1f}%，加仓空间不足")
            recommendations.append("建议提高现金比例至5%以上，保留加仓弹药")

        growth_pct = sum(
            theme_distribution.get(t, 0) for t in GROWTH_THEMES
        )
        if growth_pct > 45:
            risk_warnings.append("成长赛道过度集中")
            details.append(
                f"[风险] 成长主题（半导体+新能源+电池）合计 {growth_pct:.1f}%，超过45%"
            )
            recommendations.append("成长赛道过度集中，考虑分散至防御性资产")

        us_pct = market_distribution.get("US", 0)
        if us_pct > 40:
            risk_warnings.append("汇率风险暴露")
            details.append(
                f"[风险] 美元资产占比 {us_pct:.1f}%，汇率风险暴露较高"
            )
            recommendations.append("美元资产占比过高，注意汇率波动风险")

        # 6. Tier deviation
        tier_allocation = {
            t: tier_values[t] / total_value_cny for t in Tier
        }
        for t in Tier:
            actual = tier_allocation[t]
            target = TIER_TARGETS[t]
            deviation = actual - target
            dev_pct = float(deviation * 100)
            if abs(dev_pct) > 5:
                direction = "偏高" if dev_pct > 0 else "偏低"
                details.append(
                    f"[层级偏离] {t.value} 层实际 {float(actual*100):.1f}% vs 目标 {float(target*100):.0f}%，{direction} {abs(dev_pct):.1f}pp"
                )
                if dev_pct > 0:
                    recommendations.append(
                        f"{t.value} 层超配 {abs(dev_pct):.1f}pp，考虑减仓至目标比例"
                    )
                else:
                    recommendations.append(
                        f"{t.value} 层欠配 {abs(dev_pct):.1f}pp，可适当增配"
                    )

        # 7. Scoring
        score = 100
        score -= len(risk_warnings) * 15
        # Concentration penalties (per concentrated position)
        concentrated = sum(
            1 for p in position_details
            if p["market_value_cny"] / float(total_value_cny) * 100 > 25
        )
        score -= concentrated * 10
        # Tier deviation penalty
        total_tier_deviation = sum(
            abs(float(tier_allocation[t] - TIER_TARGETS[t]) * 100) for t in Tier
        )
        score -= int(total_tier_deviation)
        score = max(0, min(100, score))

        if score >= 80:
            rating = "健康"
        elif score >= 60:
            rating = "一般"
        elif score >= 40:
            rating = "需关注"
        else:
            rating = "高风险"

        # Summary
        summary_parts = [
            f"组合总市值约 {float(total_value_cny):,.0f} CNY",
            f"健康评分 {score}/100（{rating}）",
        ]
        if risk_warnings:
            summary_parts.append(f"风险提示: {', '.join(risk_warnings)}")
        summary = "；".join(summary_parts)

        return AnalysisReport(
            section_name=self.name,
            rating=rating,
            score=score,
            summary=summary,
            details=details,
            recommendations=recommendations,
            data={
                "holdings": position_details,
                "market_distribution": market_distribution,
                "theme_distribution": theme_distribution,
                "total_value_cny": float(round(total_value_cny, 2)),
                "cash_pct": cash_pct,
                "tier_allocation": {
                    t.value: float(round(tier_allocation[t] * 100, 2))
                    for t in Tier
                },
                "risk_warnings": risk_warnings,
            },
        )

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def get_signals(self) -> List[AnalyzerResult]:
        """Generate alert signals from portfolio health issues."""
        report = self.analyze()
        signals: list[AnalyzerResult] = []

        risk_warnings = (report.data or {}).get("risk_warnings", [])

        if "加仓空间不足" in risk_warnings:
            signals.append(AnalyzerResult(
                title="现金比例过低",
                description="现金占比低于5%，加仓空间不足，建议适当储备现金",
                severity=SignalSeverity.MEDIUM,
                data={"cash_pct": (report.data or {}).get("cash_pct")},
            ))

        if "成长赛道过度集中" in risk_warnings:
            signals.append(AnalyzerResult(
                title="成长赛道过度集中",
                description="半导体+新能源+电池主题合计占比超过45%，行业风险暴露过高",
                severity=SignalSeverity.HIGH,
                data={"theme_distribution": (report.data or {}).get("theme_distribution")},
            ))

        if "汇率风险暴露" in risk_warnings:
            signals.append(AnalyzerResult(
                title="美元资产占比过高",
                description="美元资产占比超过40%，人民币升值时存在汇兑损失风险",
                severity=SignalSeverity.MEDIUM,
                data={"us_pct": (report.data or {}).get("market_distribution", {}).get("US")},
            ))

        # Concentration signals
        holdings_data = (report.data or {}).get("holdings", [])
        total_val = (report.data or {}).get("total_value_cny", 1)
        for pos in holdings_data:
            weight = pos["market_value_cny"] / total_val * 100 if total_val else 0
            if weight > 25:
                signals.append(AnalyzerResult(
                    title=f"{pos['symbol']} 持仓集中度过高",
                    description=f"{pos['symbol']} 占组合 {weight:.1f}%，超过25%集中度阈值",
                    severity=SignalSeverity.HIGH,
                    related_symbols=[pos["symbol"]],
                    data={"weight_pct": round(weight, 2)},
                ))

        return signals
