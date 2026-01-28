"""AI Decision Advisor Service - generates investment decision suggestions."""
import json
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from src.db.models import Holding, HoldingStatus, Signal
from src.services.llm_client import LLMClient, LLMError, ModelChoice

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位保守型投资分析师，专注于风险管理。你的职责是：
- 评估每个持仓的当前状态
- 尊重用户的原始买入逻辑，在此基础上给出建议
- 提供可操作的、具体的投资建议
- 所有回复使用中文

请以严格的JSON格式回复，不要包含任何其他文本。JSON结构如下：
{
  "status_assessment": "当前状态评估（买入逻辑是否仍然成立）",
  "recommended_action": "hold/add/reduce/sell 之一",
  "key_concerns": ["关注点1", "关注点2"],
  "next_catalyst": "下一个催化剂事件",
  "confidence": "high/medium/low"
}"""


@dataclass
class HoldingAnalysis:
    """Analysis result for a single holding."""

    symbol: str
    status_assessment: str
    recommended_action: str  # hold/add/reduce/sell
    key_concerns: List[str]
    next_catalyst: str
    confidence: str  # high/medium/low
    analysis_date: date
    model_used: str


def _build_holding_prompt(holding: Holding, signals: Optional[List[Signal]] = None) -> str:
    """Build the user prompt for analyzing a holding."""
    lines = [
        f"请分析以下持仓：",
        f"股票代码: {holding.symbol}",
        f"市场: {holding.market.value}",
        f"层级: {holding.tier.value}",
        f"持仓数量: {holding.quantity}",
        f"平均成本: {holding.avg_cost}",
        f"首次买入日期: {holding.first_buy_date}",
        f"买入理由: {holding.buy_reason}",
    ]
    if holding.stop_loss_price is not None:
        lines.append(f"止损价: {holding.stop_loss_price}")
    if holding.take_profit_price is not None:
        lines.append(f"止盈价: {holding.take_profit_price}")

    if signals:
        lines.append("\n相关信号:")
        for sig in signals:
            lines.append(f"- [{sig.severity.value}] {sig.title}: {sig.description}")

    return "\n".join(lines)


def _parse_analysis_response(
    raw: str, symbol: str, model: str
) -> HoldingAnalysis:
    """Parse JSON response from LLM into HoldingAnalysis.

    Raises:
        ValueError: If the response cannot be parsed.
    """
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        # Remove first line (```json or ```) and last line (```)
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}") from e

    action = data.get("recommended_action", "hold").lower()
    if action not in ("hold", "add", "reduce", "sell"):
        action = "hold"

    confidence = data.get("confidence", "medium").lower()
    if confidence not in ("high", "medium", "low"):
        confidence = "medium"

    return HoldingAnalysis(
        symbol=symbol,
        status_assessment=data.get("status_assessment", ""),
        recommended_action=action,
        key_concerns=data.get("key_concerns", []),
        next_catalyst=data.get("next_catalyst", ""),
        confidence=confidence,
        analysis_date=date.today(),
        model_used=model,
    )


class AIAdvisor:
    """AI-powered investment decision advisor."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self._llm = llm_client or LLMClient()

    async def analyze_holding(
        self,
        holding: Holding,
        signals: Optional[List[Signal]] = None,
        use_quality_model: bool = True,
    ) -> HoldingAnalysis:
        """Analyze a single holding and return investment advice.

        Args:
            holding: The holding to analyze.
            signals: Optional related signals.
            use_quality_model: Use QUALITY model if True, FAST otherwise.

        Returns:
            HoldingAnalysis with the AI's recommendation.

        Raises:
            LLMError: On LLM communication failure.
            ValueError: If the response cannot be parsed.
        """
        model = ModelChoice.QUALITY if use_quality_model else ModelChoice.FAST
        prompt = _build_holding_prompt(holding, signals)

        raw = await self._llm.chat_with_system(
            SYSTEM_PROMPT, prompt, model=model
        )

        return _parse_analysis_response(raw, holding.symbol, model)

    async def analyze_all_holdings(self, db: Session) -> List[HoldingAnalysis]:
        """Analyze all active holdings using the FAST model for cost efficiency.

        Args:
            db: Database session.

        Returns:
            List of HoldingAnalysis for each active holding.
        """
        holdings = (
            db.query(Holding)
            .filter(Holding.status == HoldingStatus.ACTIVE)
            .all()
        )

        results: List[HoldingAnalysis] = []
        for holding in holdings:
            signals = (
                db.query(Signal)
                .filter(Signal.related_symbols.contains(holding.symbol))
                .limit(5)
                .all()
            )

            try:
                analysis = await self.analyze_holding(
                    holding, signals=signals, use_quality_model=False
                )
                results.append(analysis)
            except (LLMError, ValueError) as e:
                logger.warning(
                    "Failed to analyze holding %s: %s", holding.symbol, e
                )

        return results

    async def generate_portfolio_advice(self, db: Session) -> str:
        """Generate a summary portfolio advice in Chinese.

        Args:
            db: Database session.

        Returns:
            A formatted Chinese-language portfolio advice string.
        """
        analyses = await self.analyze_all_holdings(db)

        if not analyses:
            return "当前没有活跃持仓需要分析。"

        lines = ["📊 投资组合AI建议\n"]
        for a in analyses:
            action_map = {
                "hold": "持有",
                "add": "加仓",
                "reduce": "减仓",
                "sell": "卖出",
            }
            action_cn = action_map.get(a.recommended_action, a.recommended_action)
            lines.append(f"【{a.symbol}】建议: {action_cn} (信心: {a.confidence})")
            lines.append(f"  状态评估: {a.status_assessment}")
            if a.key_concerns:
                lines.append(f"  关注点: {', '.join(a.key_concerns)}")
            lines.append(f"  下一催化剂: {a.next_catalyst}")
            lines.append("")

        return "\n".join(lines)
