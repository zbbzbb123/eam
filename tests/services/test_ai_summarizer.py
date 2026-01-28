"""Tests for AI Summarizer Service."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.ai_summarizer import AISummarizer
from src.services.llm_client import LLMError, ModelChoice


@pytest.fixture
def summarizer():
    with patch("src.services.ai_summarizer.LLMClient") as MockLLM:
        client = AsyncMock()
        MockLLM.return_value = client
        s = AISummarizer()
        s._client = client
        yield s


# ── summarize_text ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_summarize_text_chinese(summarizer):
    summarizer._client.chat.return_value = "这是一段摘要。"
    result = await summarizer.summarize_text("很长的文章内容...", max_words=100, language="zh")
    assert result == "这是一段摘要。"
    call_args = summarizer._client.chat.call_args
    messages = call_args[0][0] if call_args[0] else call_args[1]["messages"]
    # Should use FAST model
    assert call_args[1].get("model") == ModelChoice.FAST or (
        len(call_args[0]) > 1 and call_args[0][1] == ModelChoice.FAST
    )
    # System prompt should mention Chinese
    system_msg = messages[0]["content"]
    assert "中文" in system_msg or "Chinese" in system_msg.lower() or "zh" in system_msg.lower()


@pytest.mark.asyncio
async def test_summarize_text_english(summarizer):
    summarizer._client.chat.return_value = "This is a summary."
    result = await summarizer.summarize_text("A long article...", max_words=200, language="en")
    assert result == "This is a summary."
    call_args = summarizer._client.chat.call_args
    messages = call_args[0][0] if call_args[0] else call_args[1]["messages"]
    system_msg = messages[0]["content"]
    assert "English" in system_msg or "en" in system_msg.lower()


@pytest.mark.asyncio
async def test_summarize_text_error_returns_fallback(summarizer):
    summarizer._client.chat.side_effect = LLMError("timeout")
    result = await summarizer.summarize_text("some text")
    # Should return original text or error message, not raise
    assert isinstance(result, str)
    assert len(result) > 0


# ── summarize_signals ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_summarize_signals(summarizer):
    signals = [
        {"title": "半导体出口限制", "severity": "high", "sector": "半导体"},
        {"title": "油价上涨", "severity": "medium", "sector": "能源"},
        {"title": "芯片需求增长", "severity": "low", "sector": "半导体"},
    ]
    summarizer._client.chat.return_value = "本周共3条信号，半导体板块最为活跃。"
    result = await summarizer.summarize_signals(signals)
    assert result == "本周共3条信号，半导体板块最为活跃。"
    # Verify model is FAST
    call_args = summarizer._client.chat.call_args
    model_arg = call_args[1].get("model", call_args[0][1] if len(call_args[0]) > 1 else None)
    assert model_arg == ModelChoice.FAST


@pytest.mark.asyncio
async def test_summarize_signals_empty(summarizer):
    result = await summarizer.summarize_signals([])
    assert isinstance(result, str)
    # Should not call LLM for empty input
    summarizer._client.chat.assert_not_called()


@pytest.mark.asyncio
async def test_summarize_signals_error(summarizer):
    signals = [{"title": "test", "severity": "high", "sector": "tech"}]
    summarizer._client.chat.side_effect = LLMError("fail")
    result = await summarizer.summarize_signals(signals)
    assert isinstance(result, str)


# ── enhance_weekly_report ───────────────────────────────────────


@pytest.mark.asyncio
async def test_enhance_weekly_report(summarizer):
    raw_report = "=== 周报 2025-01-20 ===\n总市值: 100,000"
    enhanced = "原始报告...\n\n## AI 点评\n市场展望积极。关键风险：无。建议：持有。"
    summarizer._client.chat.return_value = enhanced
    result = await summarizer.enhance_weekly_report(raw_report)
    assert result == enhanced
    # Should use QUALITY model (Claude)
    call_args = summarizer._client.chat.call_args
    model_arg = call_args[1].get("model", call_args[0][1] if len(call_args[0]) > 1 else None)
    assert model_arg == ModelChoice.QUALITY


@pytest.mark.asyncio
async def test_enhance_weekly_report_error_returns_original(summarizer):
    raw_report = "=== 周报 ==="
    summarizer._client.chat.side_effect = LLMError("fail")
    result = await summarizer.enhance_weekly_report(raw_report)
    assert result == raw_report


# ── analyze_market_sentiment ────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_market_sentiment(summarizer):
    news = ["美联储暗示降息", "科技股创新高", "中美贸易谈判进展顺利"]
    summarizer._client.chat.return_value = "整体偏多（Bullish）。主要主题：货币宽松、科技股强势。"
    result = await summarizer.analyze_market_sentiment(news)
    assert "Bullish" in result or "偏多" in result
    # Should use FAST model
    call_args = summarizer._client.chat.call_args
    model_arg = call_args[1].get("model", call_args[0][1] if len(call_args[0]) > 1 else None)
    assert model_arg == ModelChoice.FAST


@pytest.mark.asyncio
async def test_analyze_market_sentiment_empty(summarizer):
    result = await summarizer.analyze_market_sentiment([])
    assert isinstance(result, str)
    summarizer._client.chat.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_market_sentiment_error(summarizer):
    news = ["headline"]
    summarizer._client.chat.side_effect = LLMError("fail")
    result = await summarizer.analyze_market_sentiment(news)
    assert isinstance(result, str)
