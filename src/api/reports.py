"""Reports API endpoints."""
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.services.weekly_report import WeeklyReportService
from src.api.schemas import (
    WeeklyReportResponse, PortfolioSummaryReportResponse,
    TierSummaryReportResponse, SignalSummaryItemResponse,
    RiskAlertResponse, ActionItemResponse,
)

router = APIRouter(prefix="/reports", tags=["reports"])

_report_service = WeeklyReportService()


def _report_to_response(report) -> WeeklyReportResponse:
    """Convert a WeeklyReport dataclass to the response schema."""
    ps = report.portfolio_summary
    return WeeklyReportResponse(
        report_date=report.report_date,
        portfolio_summary=PortfolioSummaryReportResponse(
            total_value=ps.total_value,
            tiers=[
                TierSummaryReportResponse(
                    tier=ts.tier.value,
                    target_pct=ts.target_pct,
                    actual_pct=ts.actual_pct,
                    deviation_pct=ts.deviation_pct,
                    market_value=ts.market_value,
                    holdings_count=ts.holdings_count,
                )
                for ts in ps.tiers
            ],
        ),
        signal_summary=[
            SignalSummaryItemResponse(
                sector=s.sector,
                count=s.count,
                max_severity=s.max_severity.value,
                titles=s.titles,
            )
            for s in report.signal_summary
        ],
        risk_alerts=[
            RiskAlertResponse(
                level=a.level,
                message=a.message,
                symbol=a.symbol,
            )
            for a in report.risk_alerts
        ],
        action_items=[
            ActionItemResponse(
                priority=a.priority,
                description=a.description,
            )
            for a in report.action_items
        ],
    )


@router.get("/weekly", response_model=WeeklyReportResponse)
def get_weekly_report(db: Session = Depends(get_db)):
    """Generate weekly report as JSON."""
    report = _report_service.generate_report(db)
    return _report_to_response(report)


@router.get("/weekly/text", response_class=PlainTextResponse)
def get_weekly_report_text(db: Session = Depends(get_db)):
    """Generate weekly report as plain text."""
    report = _report_service.generate_report(db)
    return _report_service.format_as_text(report)


@router.get("/weekly/markdown", response_class=PlainTextResponse)
def get_weekly_report_markdown(db: Session = Depends(get_db)):
    """Generate weekly report as Markdown."""
    report = _report_service.generate_report(db)
    return _report_service.format_as_markdown(report)
