"""Macroeconomic and geopolitical analyzer."""
from typing import List, Optional
from datetime import date, datetime, timedelta

from src.analyzers.base import BaseAnalyzer, AnalyzerResult
from src.db.models import SignalSeverity


# 2025 FOMC Meeting Dates (approximate - check Fed calendar)
FOMC_DATES_2025 = [
    date(2025, 1, 29),
    date(2025, 3, 19),
    date(2025, 5, 7),
    date(2025, 6, 18),
    date(2025, 7, 30),
    date(2025, 9, 17),
    date(2025, 11, 5),
    date(2025, 12, 17),
]

# 2026 FOMC Meeting Dates (approximate)
FOMC_DATES_2026 = [
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 5, 6),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),
    date(2026, 11, 4),
    date(2026, 12, 16),
]

ALL_FOMC_DATES = FOMC_DATES_2025 + FOMC_DATES_2026

# Thresholds
FOMC_WARNING_DAYS = 7  # Alert when FOMC is within this many days
HIGH_RATE_THRESHOLD = 5.0  # Fed funds rate considered "high"


class MacroAnalyzer(BaseAnalyzer):
    """
    Analyzer for macroeconomic and geopolitical factors.

    Monitors:
    - FOMC meeting schedule and rate decisions
    - Fed Funds Rate levels
    - Key economic indicators (CPI, GDP, PMI) - future enhancement
    - Geopolitical tension index - future enhancement

    Related assets: SGOV (short-term treasuries), TLT (long bonds), SPY
    """

    RELATED_ETFS = ["SGOV", "TLT", "SPY", "QQQ"]

    @property
    def name(self) -> str:
        return "macro_analyzer"

    @property
    def sector(self) -> str:
        return "macro"

    def _get_next_fomc_date(self) -> Optional[date]:
        """Get the next FOMC meeting date."""
        today = date.today()
        for fomc_date in ALL_FOMC_DATES:
            if fomc_date >= today:
                return fomc_date
        return None

    def _get_fed_funds_rate(self) -> Optional[float]:
        """
        Get current Fed Funds Rate.
        In production, use FRED API (series: FEDFUNDS or DFF).
        """
        # Placeholder - in production fetch from FRED
        return 5.25  # As of late 2024

    def analyze(self) -> List[AnalyzerResult]:
        """Analyze macroeconomic indicators and generate signals."""
        results = []

        # Check FOMC schedule
        next_fomc = self._get_next_fomc_date()
        if next_fomc:
            fomc_result = self._analyze_fomc_schedule(next_fomc)
            if fomc_result:
                results.append(fomc_result)

        # Check interest rate environment
        fed_rate = self._get_fed_funds_rate()
        if fed_rate is not None:
            rate_result = self._analyze_rate_environment(fed_rate)
            if rate_result:
                results.append(rate_result)

        return results

    def _analyze_fomc_schedule(self, next_fomc: date) -> Optional[AnalyzerResult]:
        """Generate signal for upcoming FOMC meeting."""
        days_until = (next_fomc - date.today()).days

        if days_until <= FOMC_WARNING_DAYS:
            severity = SignalSeverity.HIGH if days_until <= 3 else SignalSeverity.MEDIUM

            return AnalyzerResult(
                title=f"FOMC Meeting in {days_until} Days",
                description=(
                    f"Federal Reserve FOMC meeting scheduled for {next_fomc.strftime('%B %d, %Y')}. "
                    f"Market volatility typically increases around FOMC announcements. "
                    f"Review positions and consider hedging strategies. "
                    f"Key watch: rate decision, dot plot, Powell's press conference."
                ),
                severity=severity,
                data={
                    "fomc_date": next_fomc.isoformat(),
                    "days_until": days_until,
                },
                related_symbols=self.RELATED_ETFS,
                expires_at=datetime.combine(next_fomc + timedelta(days=1), datetime.min.time()),
            )

        return None

    def _analyze_rate_environment(self, fed_rate: float) -> Optional[AnalyzerResult]:
        """Analyze the interest rate environment."""

        if fed_rate >= HIGH_RATE_THRESHOLD:
            return AnalyzerResult(
                title=f"High Interest Rate Environment ({fed_rate:.2f}%)",
                description=(
                    f"Fed Funds Rate at {fed_rate:.2f}%, which is historically high. "
                    f"High rates typically pressure growth stocks and favor value/dividend stocks. "
                    f"Short-duration treasuries (SGOV) offer attractive risk-free returns. "
                    f"Consider reducing duration risk in bond holdings."
                ),
                severity=SignalSeverity.INFO,
                data={
                    "fed_funds_rate": fed_rate,
                    "signal": "high_rate_environment",
                },
                related_symbols=["SGOV", "SCHD", "VYM"],
            )

        return None
