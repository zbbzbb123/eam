"""Reports API endpoints."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models_market_data import GeneratedReport
from src.services.weekly_report import ReportService
from src.api.schemas import (
    WeeklyReportResponse, PortfolioSummaryReportResponse,
    TierSummaryReportResponse, SignalSummaryItemResponse,
    RiskAlertResponse, ActionItemResponse,
    EnhancedReportResponse, AnalyzerSectionResponse,
    GeneratedReportListItem, GeneratedReportDetail,
)

router = APIRouter(prefix="/reports", tags=["reports"])

_report_service = ReportService()


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


# ===== Enhanced Report Helpers =====

def _enhanced_report_to_response(report) -> EnhancedReportResponse:
    """Convert an EnhancedReport dataclass to the response schema."""
    sections = [
        AnalyzerSectionResponse(
            name=s.name,
            rating=s.rating,
            score=s.score,
            summary=s.summary,
            details=s.details,
            recommendations=s.recommendations,
            data=s.data,
        )
        for s in report.sections
    ]

    # Build legacy portfolio summary if present
    portfolio_summary = None
    if report.portfolio_summary is not None:
        ps = report.portfolio_summary
        portfolio_summary = PortfolioSummaryReportResponse(
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
        )

    return EnhancedReportResponse(
        report_date=report.report_date,
        report_type=report.report_type,
        sections=sections,
        ai_advice=report.ai_advice,
        portfolio_summary=portfolio_summary,
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


# ===== Daily Report Endpoints =====

@router.get("/daily", response_model=EnhancedReportResponse)
def get_daily_report(db: Session = Depends(get_db)):
    """Generate daily brief report as JSON."""
    report = _report_service.generate_daily_report(db)
    return _enhanced_report_to_response(report)


@router.get("/daily/text", response_class=PlainTextResponse)
def get_daily_report_text(db: Session = Depends(get_db)):
    """Generate daily brief report as plain text."""
    report = _report_service.generate_daily_report(db)
    return _report_service.format_enhanced_as_text(report)


@router.get("/daily/markdown", response_class=PlainTextResponse)
def get_daily_report_markdown(db: Session = Depends(get_db)):
    """Generate daily brief report as Markdown."""
    report = _report_service.generate_daily_report(db)
    return _report_service.format_enhanced_as_markdown(report)


# ===== Enhanced Weekly Report Endpoints =====

@router.get("/weekly/enhanced", response_model=EnhancedReportResponse)
def get_enhanced_weekly_report(db: Session = Depends(get_db)):
    """Generate enhanced weekly report as JSON."""
    report = _report_service.generate_weekly_report(db)
    return _enhanced_report_to_response(report)


@router.get("/weekly/enhanced/markdown", response_class=PlainTextResponse)
def get_enhanced_weekly_report_markdown(db: Session = Depends(get_db)):
    """Generate enhanced weekly report as Markdown."""
    report = _report_service.generate_weekly_report(db)
    return _report_service.format_enhanced_as_markdown(report)


# ===== Pre-generated Report Endpoints =====

@router.get("/daily/list", response_model=List[GeneratedReportListItem])
def list_daily_reports(limit: int = 10, offset: int = 0, db: Session = Depends(get_db)):
    """List generated daily reports, newest first."""
    reports = (
        db.query(GeneratedReport)
        .filter(GeneratedReport.report_type == "daily")
        .order_by(desc(GeneratedReport.generated_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [GeneratedReportListItem.model_validate(r) for r in reports]


@router.post("/daily/generate")
def trigger_daily_report(db: Session = Depends(get_db)):
    """Manually trigger daily report generation."""
    from src.services.report_generator import DailyReportGenerator
    gen = DailyReportGenerator(db)
    report_id = gen.generate()
    return {"status": "ok", "report_id": report_id}


@router.get("/daily/{report_id}", response_model=GeneratedReportDetail)
def get_daily_report_detail(report_id: int, db: Session = Depends(get_db)):
    """Get a single daily report by ID."""
    report = (
        db.query(GeneratedReport)
        .filter(GeneratedReport.id == report_id, GeneratedReport.report_type == "daily")
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return GeneratedReportDetail.model_validate(report)


@router.get("/weekly/list", response_model=List[GeneratedReportListItem])
def list_weekly_reports(limit: int = 10, offset: int = 0, db: Session = Depends(get_db)):
    """List generated weekly reports, newest first."""
    reports = (
        db.query(GeneratedReport)
        .filter(GeneratedReport.report_type == "weekly")
        .order_by(desc(GeneratedReport.generated_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [GeneratedReportListItem.model_validate(r) for r in reports]


@router.post("/weekly/generate")
def trigger_weekly_report(db: Session = Depends(get_db)):
    """Manually trigger weekly report generation."""
    from src.services.report_generator import WeeklyReportGenerator
    gen = WeeklyReportGenerator(db)
    report_id = gen.generate()
    return {"status": "ok", "report_id": report_id}


@router.get("/weekly/{report_id}", response_model=GeneratedReportDetail)
def get_weekly_report_detail(report_id: int, db: Session = Depends(get_db)):
    """Get a single weekly report by ID."""
    report = (
        db.query(GeneratedReport)
        .filter(GeneratedReport.id == report_id, GeneratedReport.report_type == "weekly")
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return GeneratedReportDetail.model_validate(report)
