"""Tests for macro analyzer."""
import pytest
from unittest.mock import patch
from datetime import date, timedelta

from src.analyzers.macro import MacroAnalyzer
from src.db.models import SignalSeverity


class TestMacroAnalyzer:
    """Tests for MacroAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return MacroAnalyzer()

    def test_analyzer_name(self, analyzer):
        """Test analyzer name."""
        assert analyzer.name == "macro_analyzer"

    def test_analyzer_sector(self, analyzer):
        """Test analyzer sector."""
        assert analyzer.sector == "macro"

    def test_fomc_meeting_upcoming(self, analyzer):
        """Test signal for upcoming FOMC meeting."""
        # Mock an FOMC meeting 3 days from now
        future_date = date.today() + timedelta(days=3)

        with patch.object(analyzer, '_get_next_fomc_date', return_value=future_date):
            with patch.object(analyzer, '_get_fed_funds_rate', return_value=5.25):
                results = analyzer.analyze()

                fomc_signals = [r for r in results if "fomc" in r.title.lower()]
                assert len(fomc_signals) >= 1

    def test_no_signal_when_fomc_far_away(self, analyzer):
        """Test no signal when FOMC meeting is far away."""
        # Mock an FOMC meeting 30 days from now
        future_date = date.today() + timedelta(days=30)

        with patch.object(analyzer, '_get_next_fomc_date', return_value=future_date):
            with patch.object(analyzer, '_get_fed_funds_rate', return_value=5.25):
                results = analyzer.analyze()

                fomc_signals = [r for r in results if "fomc" in r.title.lower()]
                assert len(fomc_signals) == 0

    def test_high_interest_rate_signal(self, analyzer):
        """Test signal for high interest rates."""
        with patch.object(analyzer, '_get_next_fomc_date', return_value=None):
            with patch.object(analyzer, '_get_fed_funds_rate', return_value=6.0):
                results = analyzer.analyze()

                rate_signals = [r for r in results if "rate" in r.title.lower()]
                # High rates should generate a signal (INFO severity for informational)
                assert len(rate_signals) >= 1
                assert any(r.severity in [SignalSeverity.INFO, SignalSeverity.MEDIUM, SignalSeverity.HIGH]
                          for r in rate_signals)
