"""Tests for weekly report generation service."""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from src.services.weekly_report import (
    WeeklyReport,
    PortfolioSummary,
    TierSummary,
    SignalSummaryItem,
    RiskAlert,
    ActionItem,
    WeeklyReportService,
)
from src.db.models import (
    Holding, HoldingStatus, Tier, Market,
    Signal, SignalType, SignalSeverity, SignalStatus,
    Transaction, TransactionAction,
    DailyQuote,
)


# ===== Helpers =====

def _make_holding(
    id=1,
    symbol="AAPL",
    market=Market.US,
    tier=Tier.STABLE,
    quantity=Decimal("100"),
    avg_cost=Decimal("150.00"),
    status=HoldingStatus.ACTIVE,
    stop_loss_price=None,
    take_profit_price=None,
):
    h = Holding(
        symbol=symbol,
        market=market,
        tier=tier,
        quantity=quantity,
        avg_cost=avg_cost,
        first_buy_date=date(2024, 1, 1),
        buy_reason="test",
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
        status=status,
    )
    h.id = id
    return h


def _make_signal(
    id=1,
    signal_type=SignalType.SECTOR,
    sector="tech",
    title="Test Signal",
    description="Test description",
    severity=SignalSeverity.MEDIUM,
    created_at=None,
):
    s = Signal(
        signal_type=signal_type,
        sector=sector,
        title=title,
        description=description,
        severity=severity,
        source="test",
    )
    s.id = id
    s.created_at = created_at or datetime.now()
    return s


def _make_quote(symbol="AAPL", market=Market.US, close=Decimal("160.00"), trade_date=None):
    q = DailyQuote(
        symbol=symbol,
        market=market,
        trade_date=trade_date or date.today(),
        close=close,
    )
    return q


# ===== Data class tests =====

class TestWeeklyReportDataClasses:
    """Tests for report data classes."""

    def test_weekly_report_creation(self):
        report = WeeklyReport(
            report_date=date.today(),
            portfolio_summary=PortfolioSummary(
                total_value=Decimal("100000"),
                tiers=[],
            ),
            signal_summary=[],
            risk_alerts=[],
            action_items=[],
        )
        assert report.report_date == date.today()
        assert report.portfolio_summary.total_value == Decimal("100000")

    def test_tier_summary(self):
        ts = TierSummary(
            tier=Tier.STABLE,
            target_pct=Decimal("40"),
            actual_pct=Decimal("35"),
            deviation_pct=Decimal("-5"),
            market_value=Decimal("35000"),
            holdings_count=3,
        )
        assert ts.deviation_pct == Decimal("-5")

    def test_risk_alert(self):
        alert = RiskAlert(
            level="high",
            message="AAPL near stop loss",
            symbol="AAPL",
        )
        assert alert.level == "high"

    def test_action_item(self):
        item = ActionItem(
            priority="high",
            description="Rebalance portfolio",
        )
        assert item.priority == "high"


# ===== Service tests =====

class TestWeeklyReportService:
    """Tests for WeeklyReportService."""

    @pytest.fixture
    def service(self):
        return WeeklyReportService()

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    # --- _build_portfolio_summary ---

    def test_build_portfolio_summary_empty(self, service, mock_db):
        """Empty portfolio returns zero total."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        summary = service._build_portfolio_summary(mock_db)
        assert summary.total_value == Decimal("0")
        assert len(summary.tiers) == 3

    def test_build_portfolio_summary_single_tier(self, service, mock_db):
        """Single tier holding computes 100% actual allocation."""
        holdings = [_make_holding(tier=Tier.STABLE, quantity=Decimal("100"), avg_cost=Decimal("100"))]
        mock_db.query.return_value.filter.return_value.all.return_value = holdings
        # Mock latest quotes
        quote = _make_quote(symbol="AAPL", close=Decimal("100"))
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = quote

        summary = service._build_portfolio_summary(mock_db)
        assert summary.total_value == Decimal("10000")
        stable = next(t for t in summary.tiers if t.tier == Tier.STABLE)
        assert stable.actual_pct == Decimal("100")
        assert stable.deviation_pct == Decimal("60")  # 100 - 40 target

    def test_build_portfolio_summary_no_quote_uses_cost(self, service, mock_db):
        """When no quote available, use avg_cost * quantity as value."""
        holdings = [_make_holding(tier=Tier.STABLE, quantity=Decimal("10"), avg_cost=Decimal("50"))]
        mock_db.query.return_value.filter.return_value.all.return_value = holdings
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        summary = service._build_portfolio_summary(mock_db)
        assert summary.total_value == Decimal("500")

    def test_build_portfolio_summary_multi_tier(self, service, mock_db):
        """Multiple tiers compute correct percentages."""
        holdings = [
            _make_holding(id=1, symbol="VTI", tier=Tier.STABLE, quantity=Decimal("40"), avg_cost=Decimal("100")),
            _make_holding(id=2, symbol="QQQ", tier=Tier.MEDIUM, quantity=Decimal("30"), avg_cost=Decimal("100")),
            _make_holding(id=3, symbol="MEME", tier=Tier.GAMBLE, quantity=Decimal("30"), avg_cost=Decimal("100")),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = holdings
        # No quotes - use cost basis
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        summary = service._build_portfolio_summary(mock_db)
        assert summary.total_value == Decimal("10000")
        stable = next(t for t in summary.tiers if t.tier == Tier.STABLE)
        assert stable.actual_pct == Decimal("40")
        assert stable.deviation_pct == Decimal("0")

    # --- _build_signal_summary ---

    def test_build_signal_summary_empty(self, service, mock_db):
        """No signals returns empty list."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = service._build_signal_summary(mock_db)
        assert result == []

    def test_build_signal_summary_groups_by_sector(self, service, mock_db):
        """Signals grouped by sector."""
        signals = [
            _make_signal(id=1, sector="tech", title="AI boom", severity=SignalSeverity.HIGH),
            _make_signal(id=2, sector="tech", title="Chip shortage", severity=SignalSeverity.MEDIUM),
            _make_signal(id=3, sector="energy", title="Oil up", severity=SignalSeverity.LOW),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = signals

        result = service._build_signal_summary(mock_db)
        assert len(result) == 2
        tech_item = next(s for s in result if s.sector == "tech")
        assert tech_item.count == 2
        assert tech_item.max_severity == SignalSeverity.HIGH

    def test_build_signal_summary_no_sector_uses_type(self, service, mock_db):
        """Signals without sector use signal_type as group key."""
        signals = [
            _make_signal(id=1, sector=None, signal_type=SignalType.MACRO, title="Fed rate"),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = signals

        result = service._build_signal_summary(mock_db)
        assert len(result) == 1
        assert result[0].sector == "macro"

    # --- _build_risk_alerts ---

    def test_build_risk_alerts_no_holdings(self, service, mock_db):
        """No holdings returns empty alerts."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = service._build_risk_alerts(mock_db)
        assert result == []

    def test_build_risk_alerts_concentration(self, service, mock_db):
        """Single holding at 100% triggers concentration alert."""
        holdings = [_make_holding(tier=Tier.STABLE, quantity=Decimal("100"), avg_cost=Decimal("100"))]
        mock_db.query.return_value.filter.return_value.all.return_value = holdings
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        result = service._build_risk_alerts(mock_db)
        assert any("concentration" in a.message.lower() or "集中" in a.message for a in result)

    def test_build_risk_alerts_no_stop_loss(self, service, mock_db):
        """Holdings without stop loss trigger alert."""
        holdings = [_make_holding(stop_loss_price=None)]
        mock_db.query.return_value.filter.return_value.all.return_value = holdings
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        result = service._build_risk_alerts(mock_db)
        assert any("stop" in a.message.lower() or "止损" in a.message for a in result)

    def test_build_risk_alerts_tier_deviation(self, service, mock_db):
        """Large tier deviation triggers rebalance alert."""
        # All in gamble tier
        holdings = [_make_holding(tier=Tier.GAMBLE, quantity=Decimal("100"), avg_cost=Decimal("100"))]
        mock_db.query.return_value.filter.return_value.all.return_value = holdings
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        result = service._build_risk_alerts(mock_db)
        assert any("偏离" in a.message or "deviation" in a.message.lower() or "再平衡" in a.message for a in result)

    # --- _build_action_items ---

    def test_build_action_items_rebalance(self, service, mock_db):
        """Deviation triggers rebalance action item."""
        holdings = [_make_holding(tier=Tier.GAMBLE, quantity=Decimal("100"), avg_cost=Decimal("100"))]
        mock_db.query.return_value.filter.return_value.all.return_value = holdings
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        # Also need signals query for action items
        result = service._build_action_items(mock_db, holdings=holdings)
        assert len(result) > 0

    def test_build_action_items_unread_signals(self, service, mock_db):
        """Active critical signals trigger action item."""
        signals = [_make_signal(severity=SignalSeverity.CRITICAL)]
        holdings = []

        # We pass signals directly
        result = service._build_action_items(mock_db, holdings=holdings, critical_signals=signals)
        assert any("信号" in item.description or "signal" in item.description.lower() for item in result)

    # --- generate_report ---

    def test_generate_report_returns_weekly_report(self, service, mock_db):
        """generate_report returns a WeeklyReport instance."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        report = service.generate_report(mock_db)
        assert isinstance(report, WeeklyReport)
        assert report.report_date == date.today()

    # --- format_as_text ---

    def test_format_as_text(self, service):
        """Text format produces readable output."""
        report = WeeklyReport(
            report_date=date(2025, 1, 15),
            portfolio_summary=PortfolioSummary(
                total_value=Decimal("100000"),
                tiers=[
                    TierSummary(tier=Tier.STABLE, target_pct=Decimal("40"), actual_pct=Decimal("38"),
                                deviation_pct=Decimal("-2"), market_value=Decimal("38000"), holdings_count=2),
                    TierSummary(tier=Tier.MEDIUM, target_pct=Decimal("30"), actual_pct=Decimal("32"),
                                deviation_pct=Decimal("2"), market_value=Decimal("32000"), holdings_count=1),
                    TierSummary(tier=Tier.GAMBLE, target_pct=Decimal("30"), actual_pct=Decimal("30"),
                                deviation_pct=Decimal("0"), market_value=Decimal("30000"), holdings_count=1),
                ],
            ),
            signal_summary=[
                SignalSummaryItem(sector="tech", count=3, max_severity=SignalSeverity.HIGH, titles=["AI boom", "Chip news", "Earnings"]),
            ],
            risk_alerts=[
                RiskAlert(level="high", message="AAPL 集中度过高 (50%)", symbol="AAPL"),
            ],
            action_items=[
                ActionItem(priority="high", description="检查再平衡需求"),
            ],
        )

        text = service.format_as_text(report)
        assert "仓位全景" in text
        assert "100000" in text or "100,000" in text
        assert "信号汇总" in text
        assert "风险预警" in text
        assert "待办" in text

    # --- format_as_markdown ---

    def test_format_as_markdown(self, service):
        """Markdown format uses proper formatting."""
        report = WeeklyReport(
            report_date=date(2025, 1, 15),
            portfolio_summary=PortfolioSummary(
                total_value=Decimal("50000"),
                tiers=[
                    TierSummary(tier=Tier.STABLE, target_pct=Decimal("40"), actual_pct=Decimal("40"),
                                deviation_pct=Decimal("0"), market_value=Decimal("20000"), holdings_count=1),
                    TierSummary(tier=Tier.MEDIUM, target_pct=Decimal("30"), actual_pct=Decimal("30"),
                                deviation_pct=Decimal("0"), market_value=Decimal("15000"), holdings_count=1),
                    TierSummary(tier=Tier.GAMBLE, target_pct=Decimal("30"), actual_pct=Decimal("30"),
                                deviation_pct=Decimal("0"), market_value=Decimal("15000"), holdings_count=1),
                ],
            ),
            signal_summary=[],
            risk_alerts=[],
            action_items=[],
        )

        md = service.format_as_markdown(report)
        assert "# " in md or "## " in md
        assert "仓位全景" in md

    def test_format_as_text_empty_sections(self, service):
        """Text format handles empty sections gracefully."""
        report = WeeklyReport(
            report_date=date.today(),
            portfolio_summary=PortfolioSummary(total_value=Decimal("0"), tiers=[]),
            signal_summary=[],
            risk_alerts=[],
            action_items=[],
        )
        text = service.format_as_text(report)
        assert isinstance(text, str)
        assert len(text) > 0
