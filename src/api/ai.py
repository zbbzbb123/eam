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
from src.services.ai_advisor import AIAdvisor
from src.services.ai_summarizer import AISummarizer
from src.services.llm_client import LLMClient, LLMError, ModelChoice
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


class ClassifyTierRequest(BaseModel):
    symbol: str
    market: str  # US, HK, CN


@router.post("/analyze-holding/{holding_id}")
async def analyze_holding(
    holding_id: int,
    quality: bool = True,
    db: Session = Depends(get_db),
):
    """Analyze a single holding with AI."""
    holding = db.get(Holding, holding_id)
    if not holding:
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
async def analyze_all(db: Session = Depends(get_db)):
    """Analyze all active holdings with AI (uses fast model)."""
    try:
        analyses = await _advisor.analyze_all_holdings(db)
        return [dataclasses.asdict(a) for a in analyses]
    except (LLMError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {e}")


@router.post("/portfolio-advice")
async def portfolio_advice(db: Session = Depends(get_db)):
    """Generate portfolio-level AI advice."""
    try:
        advice = await _advisor.generate_portfolio_advice(db)
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
async def enhance_report(db: Session = Depends(get_db)):
    """Generate weekly report and enhance with AI commentary."""
    try:
        report = _report_service.generate_report(db)
        report_text = _report_service.format_as_text(report)
        enhanced = await _summarizer.enhance_weekly_report(report_text)
        return {"report": enhanced, "enhanced": True}
    except (LLMError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"AI enhance failed: {e}")


@router.post("/classify-tier")
async def classify_tier(request: ClassifyTierRequest):
    """Use AI to classify a stock into stable/medium/gamble tier.

    - stable: 大盘蓝筹、高股息、低波动ETF、国债等稳健资产
    - medium: 成长股、行业龙头、主题ETF等中等风险资产
    - gamble: 小盘股、概念股、高波动个股、加密货币等高风险资产
    """
    prompt = f"""你是一个投资组合分类专家。请根据以下股票信息，将其归入三个风险层级之一。

股票代码: {request.symbol}
市场: {request.market}

三个层级定义：
- stable: 大盘蓝筹、高股息、低波动ETF、国债类基金、货币基金等稳健资产
- medium: 成长型龙头、行业ETF、主题基金等中等风险资产
- gamble: 小盘股、概念股、高波动个股、meme股、加密货币相关等高风险资产

请只回复一个单词: stable、medium 或 gamble。不要解释。"""

    try:
        client = LLMClient()
        result = await client.chat_with_system(
            "你是投资分类助手，只回复分类结果。",
            prompt,
            model=ModelChoice.FAST,
        )
        tier = result.strip().lower()
        if tier not in ("stable", "medium", "gamble"):
            tier = "medium"
        return {"tier": tier}
    except (LLMError, Exception) as e:
        logger.warning("AI tier classification failed: %s, defaulting to medium", e)
        return {"tier": "medium"}
