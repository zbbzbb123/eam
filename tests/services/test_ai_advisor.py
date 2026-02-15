"""Tests for AI Decision Advisor Service."""
import json
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from src.db.models import (
    Holding, HoldingStatus, Market, Signal, SignalSeverity,
    SignalStatus, SignalType, Tier,
)
from src.services.ai_advisor import (
    AIAdvisor, HoldingAnalysis, SYSTEM_PROMPT,
    _build_holding_prompt, _parse_analysis_response,
)
from src.services.llm_client import LLMClient, LLMError, ModelChoice


# --- Fixtures ---

def _make_holding(**overrides) -> Holding:
    defaults = dict(
        symbol="AAPL",
        market=Market.US,
        tier=Tier.CORE,
        quantity=Decimal("100"),
        avg_cost=Decimal("150.00"),
        first_buy_date=date(2024, 1, 15),
        buy_reason="Strong ecosystem and services growth",
        stop_loss_price=Decimal("130.00"),
        take_profit_price=Decimal("200.00"),
        status=HoldingStatus.ACTIVE,
    )
    defaults.update(overrides)
    return Holding(**defaults)


def _make_signal(**overrides) -> Signal:
    defaults = dict(
        signal_type=SignalType.HOLDING,
        title="AAPL earnings beat",
        description="Apple beat Q4 earnings expectations",
        severity=SignalSeverity.MEDIUM,
        source="earnings_monitor",
        related_symbols=["AAPL"],
    )
    defaults.update(overrides)
    return Signal(**defaults)


SAMPLE_LLM_JSON = json.dumps({
    "status_assessment": "买入逻辑依然成立，服务收入持续增长",
    "recommended_action": "hold",
    "key_concerns": ["估值偏高", "中国市场风险"],
    "next_catalyst": "下季度财报（1月底）",
    "confidence": "high",
})


# --- HoldingAnalysis dataclass ---

class TestHoldingAnalysis:
    def test_creation(self):
        a = HoldingAnalysis(
            symbol="AAPL",
            status_assessment="良好",
            recommended_action="hold",
            key_concerns=["估值"],
            next_catalyst="财报",
            confidence="high",
            analysis_date=date(2025, 1, 1),
            model_used=ModelChoice.QUALITY,
        )
        assert a.symbol == "AAPL"
        assert a.recommended_action == "hold"
        assert a.confidence == "high"
        assert a.key_concerns == ["估值"]


# --- Prompt building ---

class TestBuildHoldingPrompt:
    def test_basic_prompt(self):
        h = _make_holding()
        prompt = _build_holding_prompt(h)
        assert "AAPL" in prompt
        assert "US" in prompt
        assert "core" in prompt
        assert "150.00" in prompt or "150.0000" in prompt
        assert "Strong ecosystem" in prompt
        assert "130.00" in prompt or "130.0000" in prompt

    def test_prompt_without_stop_loss(self):
        h = _make_holding(stop_loss_price=None, take_profit_price=None)
        prompt = _build_holding_prompt(h)
        assert "止损价" not in prompt
        assert "止盈价" not in prompt

    def test_prompt_with_signals(self):
        h = _make_holding()
        signals = [_make_signal()]
        prompt = _build_holding_prompt(h, signals)
        assert "相关信号" in prompt
        assert "AAPL earnings beat" in prompt
        assert "medium" in prompt


# --- Response parsing ---

class TestParseAnalysisResponse:
    def test_parse_valid_json(self):
        result = _parse_analysis_response(SAMPLE_LLM_JSON, "AAPL", ModelChoice.QUALITY)
        assert result.symbol == "AAPL"
        assert result.recommended_action == "hold"
        assert result.confidence == "high"
        assert "估值偏高" in result.key_concerns
        assert result.model_used == ModelChoice.QUALITY
        assert result.analysis_date == date.today()

    def test_parse_json_with_code_fence(self):
        raw = f"```json\n{SAMPLE_LLM_JSON}\n```"
        result = _parse_analysis_response(raw, "AAPL", ModelChoice.FAST)
        assert result.recommended_action == "hold"
        assert result.model_used == ModelChoice.FAST

    def test_parse_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Failed to parse"):
            _parse_analysis_response("not json", "AAPL", ModelChoice.FAST)

    def test_parse_unknown_action_defaults_hold(self):
        data = json.dumps({"recommended_action": "unknown_action", "confidence": "high"})
        result = _parse_analysis_response(data, "AAPL", ModelChoice.FAST)
        assert result.recommended_action == "hold"

    def test_parse_unknown_confidence_defaults_medium(self):
        data = json.dumps({"recommended_action": "sell", "confidence": "very_high"})
        result = _parse_analysis_response(data, "AAPL", ModelChoice.FAST)
        assert result.confidence == "medium"

    def test_parse_missing_fields_use_defaults(self):
        data = json.dumps({})
        result = _parse_analysis_response(data, "TSLA", ModelChoice.FAST)
        assert result.symbol == "TSLA"
        assert result.recommended_action == "hold"
        assert result.confidence == "medium"
        assert result.key_concerns == []
        assert result.status_assessment == ""
        assert result.next_catalyst == ""


# --- AIAdvisor.analyze_holding ---

class TestAnalyzeHolding:
    @pytest.mark.asyncio
    async def test_analyze_holding_quality_model(self):
        llm = MagicMock(spec=LLMClient)
        llm.chat_with_system = AsyncMock(return_value=SAMPLE_LLM_JSON)

        advisor = AIAdvisor(llm_client=llm)
        holding = _make_holding()
        result = await advisor.analyze_holding(holding, use_quality_model=True)

        assert result.symbol == "AAPL"
        assert result.recommended_action == "hold"
        assert result.model_used == ModelChoice.QUALITY
        llm.chat_with_system.assert_awaited_once()
        call_kwargs = llm.chat_with_system.call_args
        assert call_kwargs[1]["model"] == ModelChoice.QUALITY

    @pytest.mark.asyncio
    async def test_analyze_holding_fast_model(self):
        llm = MagicMock(spec=LLMClient)
        llm.chat_with_system = AsyncMock(return_value=SAMPLE_LLM_JSON)

        advisor = AIAdvisor(llm_client=llm)
        result = await advisor.analyze_holding(
            _make_holding(), use_quality_model=False
        )
        assert result.model_used == ModelChoice.FAST

    @pytest.mark.asyncio
    async def test_analyze_holding_with_signals(self):
        llm = MagicMock(spec=LLMClient)
        llm.chat_with_system = AsyncMock(return_value=SAMPLE_LLM_JSON)

        advisor = AIAdvisor(llm_client=llm)
        signals = [_make_signal()]
        await advisor.analyze_holding(_make_holding(), signals=signals)

        prompt = llm.chat_with_system.call_args[0][1]
        assert "AAPL earnings beat" in prompt

    @pytest.mark.asyncio
    async def test_analyze_holding_llm_error_propagates(self):
        llm = MagicMock(spec=LLMClient)
        llm.chat_with_system = AsyncMock(side_effect=LLMError("API down"))

        advisor = AIAdvisor(llm_client=llm)
        with pytest.raises(LLMError):
            await advisor.analyze_holding(_make_holding())

    @pytest.mark.asyncio
    async def test_analyze_holding_parse_error_propagates(self):
        llm = MagicMock(spec=LLMClient)
        llm.chat_with_system = AsyncMock(return_value="not json")

        advisor = AIAdvisor(llm_client=llm)
        with pytest.raises(ValueError):
            await advisor.analyze_holding(_make_holding())

    @pytest.mark.asyncio
    async def test_system_prompt_passed(self):
        llm = MagicMock(spec=LLMClient)
        llm.chat_with_system = AsyncMock(return_value=SAMPLE_LLM_JSON)

        advisor = AIAdvisor(llm_client=llm)
        await advisor.analyze_holding(_make_holding())

        system = llm.chat_with_system.call_args[0][0]
        assert system == SYSTEM_PROMPT
        assert "保守型投资分析师" in system
        assert "JSON" in system


# --- AIAdvisor.analyze_all_holdings ---

class TestAnalyzeAllHoldings:
    @pytest.mark.asyncio
    async def test_analyze_all_active_holdings(self):
        llm = MagicMock(spec=LLMClient)
        llm.chat_with_system = AsyncMock(return_value=SAMPLE_LLM_JSON)

        h1 = _make_holding(symbol="AAPL")
        h2 = _make_holding(symbol="TSLA")

        db = MagicMock(spec=Session)
        query = MagicMock()
        db.query.return_value = query
        filter_mock = MagicMock()
        query.filter.return_value = filter_mock

        # First call: holdings query -> .all()
        # Subsequent calls: signals query -> .limit().all()
        filter_mock.all.return_value = [h1, h2]
        limit_mock = MagicMock()
        filter_mock.limit.return_value = limit_mock
        limit_mock.all.return_value = []

        advisor = AIAdvisor(llm_client=llm)
        results = await advisor.analyze_all_holdings(db)

        assert len(results) == 2
        assert results[0].symbol == "AAPL"
        assert results[1].symbol == "TSLA"
        # All should use FAST model
        for r in results:
            assert r.model_used == ModelChoice.FAST

    @pytest.mark.asyncio
    async def test_analyze_all_skips_failed(self):
        llm = MagicMock(spec=LLMClient)
        # First call succeeds, second fails
        llm.chat_with_system = AsyncMock(
            side_effect=[SAMPLE_LLM_JSON, LLMError("fail")]
        )

        h1 = _make_holding(symbol="AAPL")
        h2 = _make_holding(symbol="BAD")

        db = MagicMock(spec=Session)
        query = MagicMock()
        db.query.return_value = query
        filter_mock = MagicMock()
        query.filter.return_value = filter_mock
        filter_mock.all.return_value = [h1, h2]
        limit_mock = MagicMock()
        filter_mock.limit.return_value = limit_mock
        limit_mock.all.return_value = []

        advisor = AIAdvisor(llm_client=llm)
        results = await advisor.analyze_all_holdings(db)

        assert len(results) == 1
        assert results[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_analyze_all_no_holdings(self):
        llm = MagicMock(spec=LLMClient)

        db = MagicMock(spec=Session)
        query = MagicMock()
        db.query.return_value = query
        filter_mock = MagicMock()
        query.filter.return_value = filter_mock
        filter_mock.all.return_value = []

        advisor = AIAdvisor(llm_client=llm)
        results = await advisor.analyze_all_holdings(db)

        assert results == []
        llm.chat_with_system.assert_not_awaited()


# --- AIAdvisor.generate_portfolio_advice ---

class TestGeneratePortfolioAdvice:
    @pytest.mark.asyncio
    async def test_generates_chinese_report(self):
        llm = MagicMock(spec=LLMClient)
        llm.chat_with_system = AsyncMock(return_value=SAMPLE_LLM_JSON)

        h1 = _make_holding(symbol="AAPL")

        db = MagicMock(spec=Session)
        query = MagicMock()
        db.query.return_value = query
        filter_mock = MagicMock()
        query.filter.return_value = filter_mock
        filter_mock.all.return_value = [h1]
        limit_mock = MagicMock()
        filter_mock.limit.return_value = limit_mock
        limit_mock.all.return_value = []

        advisor = AIAdvisor(llm_client=llm)
        report = await advisor.generate_portfolio_advice(db)

        assert "AAPL" in report
        assert "持有" in report
        assert "投资组合AI建议" in report

    @pytest.mark.asyncio
    async def test_empty_portfolio(self):
        llm = MagicMock(spec=LLMClient)

        db = MagicMock(spec=Session)
        query = MagicMock()
        db.query.return_value = query
        filter_mock = MagicMock()
        query.filter.return_value = filter_mock
        filter_mock.all.return_value = []

        advisor = AIAdvisor(llm_client=llm)
        report = await advisor.generate_portfolio_advice(db)

        assert "没有活跃持仓" in report
