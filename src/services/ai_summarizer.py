"""AI Summarizer Service - summarize content and enhance reports with LLM."""
import logging
from typing import List, Optional

from src.services.llm_client import LLMClient, LLMError, ModelChoice

logger = logging.getLogger(__name__)


class AISummarizer:
    """Summarize long-form content and enhance weekly reports using LLM."""

    def __init__(self, client: Optional[LLMClient] = None):
        self._client = client or LLMClient(model=ModelChoice.FAST)

    async def summarize_text(
        self, text: str, max_words: int = 200, language: str = "zh"
    ) -> str:
        """Summarize long text into a concise summary.

        Args:
            text: The text to summarize.
            max_words: Maximum words in the summary.
            language: Output language - "zh" for Chinese, "en" for English.

        Returns:
            Concise summary string, or the original text on error.
        """
        lang_instruction = "用中文回答" if language == "zh" else "Reply in English"
        system_prompt = (
            f"你是一个专业的文本摘要助手。请将用户提供的文本精炼总结，"
            f"不超过{max_words}字。{lang_instruction}。"
            f"只输出摘要内容，不要加前缀。"
        )
        try:
            return await self._client.chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                model=ModelChoice.FAST,
            )
        except LLMError:
            logger.warning("summarize_text failed, returning original text")
            return text

    async def summarize_signals(self, signals: List[dict]) -> str:
        """Produce a narrative summary of signal dicts grouped by severity and sector.

        Args:
            signals: List of dicts with keys: title, severity, sector.

        Returns:
            Narrative summary in Chinese.
        """
        if not signals:
            return "本周无信号。"

        # Build structured input for LLM
        lines = []
        for s in signals:
            lines.append(f"- [{s.get('severity', 'unknown')}] {s.get('sector', '未知')}: {s.get('title', '')}")
        signal_text = "\n".join(lines)

        system_prompt = (
            "你是一个投资信号分析师。请根据以下信号列表生成一段简洁的中文叙述摘要。"
            "按严重程度和板块分组，突出最重要的信号。只输出摘要。"
        )
        try:
            return await self._client.chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": signal_text},
                ],
                model=ModelChoice.FAST,
            )
        except LLMError:
            logger.warning("summarize_signals failed, returning fallback")
            return f"本周共{len(signals)}条信号，AI摘要生成失败。"

    async def enhance_weekly_report(self, report_text: str) -> str:
        """Enhance a raw weekly report with AI commentary.

        Adds market outlook, key risks, and actionable recommendations.
        Uses QUALITY model (Claude) since final report quality matters.

        Args:
            report_text: Raw weekly report text.

        Returns:
            Enhanced report text, or original on error.
        """
        system_prompt = (
            "你是一位资深投资顾问。请基于以下周报内容，添加AI点评，包括：\n"
            "1. 市场展望\n"
            "2. 关键风险提示\n"
            "3. 可执行的建议\n\n"
            "保留原始报告内容，在末尾追加 '## AI 点评' 部分。用中文回答。"
        )
        try:
            return await self._client.chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": report_text},
                ],
                model=ModelChoice.QUALITY,
            )
        except LLMError:
            logger.warning("enhance_weekly_report failed, returning original")
            return report_text

    async def analyze_market_sentiment(self, news_items: List[str]) -> str:
        """Analyze market sentiment from news headlines.

        Args:
            news_items: List of news headline strings.

        Returns:
            Sentiment analysis with Bullish/Bearish/Neutral assessment and key themes.
        """
        if not news_items:
            return "无新闻数据，无法分析市场情绪。"

        news_text = "\n".join(f"- {item}" for item in news_items)

        system_prompt = (
            "你是一位市场情绪分析师。根据以下新闻标题，给出：\n"
            "1. 整体情绪判断：Bullish（偏多）/ Bearish（偏空）/ Neutral（中性）\n"
            "2. 关键主题\n"
            "用中文简洁回答。"
        )
        try:
            return await self._client.chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": news_text},
                ],
                model=ModelChoice.FAST,
            )
        except LLMError:
            logger.warning("analyze_market_sentiment failed")
            return "市场情绪分析失败，请稍后重试。"
