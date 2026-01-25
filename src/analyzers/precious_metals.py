"""Precious metals sector analyzer."""
from typing import List, Optional
import logging

from src.analyzers.base import BaseAnalyzer, AnalyzerResult
from src.db.models import SignalSeverity
from src.collectors.structured.yfinance_collector import YFinanceCollector

logger = logging.getLogger(__name__)

# Thresholds
GOLD_SILVER_RATIO_HIGH = 85  # Silver undervalued when ratio > 85
GOLD_SILVER_RATIO_LOW = 65   # Silver overvalued when ratio < 65
TIPS_YIELD_BULLISH = 1.0     # Gold bullish when real yield < 1%
TIPS_YIELD_VERY_BULLISH = 0  # Gold very bullish when real yield < 0


class PreciousMetalsAnalyzer(BaseAnalyzer):
    """
    Analyzer for precious metals sector (Gold & Silver).

    Monitors:
    - Gold/Silver ratio (>85 silver undervalued, <65 silver overvalued)
    - US Real Interest Rate (TIPS yield) - core driver for gold
    - Central bank gold purchases (future enhancement)

    Related ETFs: GLD, IAU, SLV, 518880 (A-share gold ETF)
    """

    RELATED_ETFS = ["GLD", "IAU", "SLV"]

    def __init__(self):
        self._collector = YFinanceCollector()

    @property
    def name(self) -> str:
        return "precious_metals_analyzer"

    @property
    def sector(self) -> str:
        return "precious_metals"

    def _get_gold_price(self) -> Optional[float]:
        """Get current gold price via GLD ETF."""
        try:
            quote = self._collector.fetch_latest_quote("GLD")
            if quote and quote.close:
                # GLD represents ~1/10 oz of gold, multiply by 10 for rough gold price
                return quote.close * 10
        except Exception as e:
            logger.error(f"Error fetching gold price: {e}")
        return None

    def _get_silver_price(self) -> Optional[float]:
        """Get current silver price via SLV ETF."""
        try:
            quote = self._collector.fetch_latest_quote("SLV")
            if quote and quote.close:
                # SLV represents ~1 oz of silver
                return quote.close
        except Exception as e:
            logger.error(f"Error fetching silver price: {e}")
        return None

    def _get_tips_yield(self) -> Optional[float]:
        """
        Get 10-year TIPS yield (real interest rate).
        Uses TIP ETF as proxy - in production, use FRED API for actual TIPS yield.
        """
        # For MVP, return a placeholder. In production, use FRED API.
        # FRED series: DFII10 (10-Year Treasury Inflation-Indexed Security)
        return None

    def analyze(self) -> List[AnalyzerResult]:
        """Analyze precious metals indicators and generate signals."""
        results = []

        gold_price = self._get_gold_price()
        silver_price = self._get_silver_price()
        tips_yield = self._get_tips_yield()

        # Analyze gold/silver ratio
        if gold_price and silver_price and silver_price > 0:
            ratio = gold_price / silver_price
            ratio_result = self._analyze_gold_silver_ratio(ratio, gold_price, silver_price)
            if ratio_result:
                results.append(ratio_result)

        # Analyze TIPS yield
        if tips_yield is not None:
            tips_result = self._analyze_tips_yield(tips_yield)
            if tips_result:
                results.append(tips_result)

        return results

    def _analyze_gold_silver_ratio(
        self,
        ratio: float,
        gold_price: float,
        silver_price: float
    ) -> Optional[AnalyzerResult]:
        """Analyze gold/silver ratio for trading signals."""

        if ratio > GOLD_SILVER_RATIO_HIGH:
            return AnalyzerResult(
                title="Silver Undervalued - High Gold/Silver Ratio",
                description=(
                    f"Gold/Silver ratio at {ratio:.1f} (threshold: >{GOLD_SILVER_RATIO_HIGH}). "
                    f"Historically high ratio suggests silver is undervalued relative to gold. "
                    f"Gold: ${gold_price:.2f}, Silver: ${silver_price:.2f}. "
                    f"Consider adding silver exposure (SLV) or rotating from gold to silver."
                ),
                severity=SignalSeverity.MEDIUM,
                data={
                    "gold_silver_ratio": round(ratio, 2),
                    "gold_price": round(gold_price, 2),
                    "silver_price": round(silver_price, 2),
                    "signal": "silver_undervalued",
                },
                related_symbols=["SLV", "GLD"],
            )

        elif ratio < GOLD_SILVER_RATIO_LOW:
            return AnalyzerResult(
                title="Silver Overvalued - Low Gold/Silver Ratio",
                description=(
                    f"Gold/Silver ratio at {ratio:.1f} (threshold: <{GOLD_SILVER_RATIO_LOW}). "
                    f"Historically low ratio suggests silver may be overvalued. "
                    f"Gold: ${gold_price:.2f}, Silver: ${silver_price:.2f}. "
                    f"Consider reducing silver exposure or rotating to gold."
                ),
                severity=SignalSeverity.LOW,
                data={
                    "gold_silver_ratio": round(ratio, 2),
                    "gold_price": round(gold_price, 2),
                    "silver_price": round(silver_price, 2),
                    "signal": "silver_overvalued",
                },
                related_symbols=["SLV", "GLD"],
            )

        return None

    def _analyze_tips_yield(self, tips_yield: float) -> Optional[AnalyzerResult]:
        """Analyze TIPS yield for gold outlook."""

        if tips_yield < TIPS_YIELD_VERY_BULLISH:
            return AnalyzerResult(
                title="Negative Real Yields - Very Bullish for Gold",
                description=(
                    f"10-Year TIPS yield at {tips_yield:.2f}% (negative real rates). "
                    f"Negative real interest rates are historically very bullish for gold "
                    f"as the opportunity cost of holding gold is negative. "
                    f"Consider increasing gold exposure."
                ),
                severity=SignalSeverity.HIGH,
                data={
                    "tips_yield": round(tips_yield, 2),
                    "signal": "very_bullish_gold",
                },
                related_symbols=["GLD", "IAU"],
            )

        elif tips_yield < TIPS_YIELD_BULLISH:
            return AnalyzerResult(
                title="Low Real Yields - Bullish for Gold",
                description=(
                    f"10-Year TIPS yield at {tips_yield:.2f}% (below {TIPS_YIELD_BULLISH}%). "
                    f"Low real interest rates support gold prices. "
                    f"Maintain or consider adding gold exposure."
                ),
                severity=SignalSeverity.MEDIUM,
                data={
                    "tips_yield": round(tips_yield, 2),
                    "signal": "bullish_gold",
                },
                related_symbols=["GLD", "IAU"],
            )

        return None
