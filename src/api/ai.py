"""AI API endpoints."""
import dataclasses
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.db.database import get_db
from src.db.models import Holding, Signal, HoldingStatus
from src.db.models_auth import User
from src.services.auth import get_current_user
from src.services.ai_advisor import AIAdvisor
from src.services.ai_summarizer import AISummarizer
from src.services.llm_client import LLMError
from src.services.weekly_report import WeeklyReportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

_advisor = AIAdvisor()
_summarizer = AISummarizer()
_report_service = WeeklyReportService()


class SummarizeRequest(BaseModel):
    text: str
    max_words: int = 200
    language: str = "zh"



@router.post("/analyze-holding/{holding_id}")
async def analyze_holding(
    holding_id: int,
    quality: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Analyze a single holding with AI."""
    holding = db.get(Holding, holding_id)
    if not holding or holding.user_id != current_user.id:
        raise HTTPException(status_code=404, detail=f"Holding {holding_id} not found")

    # Get recent signals related to this holding
    signals = (
        db.query(Signal)
        .filter(Signal.related_symbols.contains(holding.symbol))
        .limit(5)
        .all()
    )

    try:
        analysis = await _advisor.analyze_holding(
            holding, signals=signals, use_quality_model=quality
        )
        return dataclasses.asdict(analysis)
    except (LLMError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {e}")


@router.post("/analyze-all")
async def analyze_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Analyze all active holdings with AI (uses fast model)."""
    try:
        analyses = await _advisor.analyze_all_holdings(db, user_id=current_user.id)
        return [dataclasses.asdict(a) for a in analyses]
    except (LLMError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {e}")


@router.post("/portfolio-advice")
async def portfolio_advice(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate portfolio-level AI advice."""
    try:
        advice = await _advisor.generate_portfolio_advice(db, user_id=current_user.id)
        return {"advice": advice}
    except (LLMError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"AI advice failed: {e}")


@router.post("/summarize")
async def summarize(request: SummarizeRequest):
    """Summarize text with AI."""
    try:
        summary = await _summarizer.summarize_text(
            request.text, max_words=request.max_words, language=request.language
        )
        return {"summary": summary}
    except (LLMError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"AI summarize failed: {e}")


@router.post("/enhance-report")
async def enhance_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate weekly report and enhance with AI commentary."""
    try:
        report = _report_service.generate_report(db)
        report_text = _report_service.format_as_text(report)
        enhanced = await _summarizer.enhance_weekly_report(report_text)
        return {"report": enhanced, "enhanced": True}
    except (LLMError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"AI enhance failed: {e}")


