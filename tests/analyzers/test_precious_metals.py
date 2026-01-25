"""Tests for precious metals analyzer."""
import pytest
from unittest.mock import patch

from src.analyzers.precious_metals import PreciousMetalsAnalyzer
from src.db.models import SignalSeverity


class TestPreciousMetalsAnalyzer:
    """Tests for PreciousMetalsAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return PreciousMetalsAnalyzer()

    def test_analyzer_name(self, analyzer):
        """Test analyzer name."""
        assert analyzer.name == "precious_metals_analyzer"

    def test_analyzer_sector(self, analyzer):
        """Test analyzer sector."""
        assert analyzer.sector == "precious_metals"

    def test_gold_silver_ratio_high(self, analyzer):
        """Test signal when gold/silver ratio is high (silver undervalued)."""
        with patch.object(analyzer, '_get_gold_price', return_value=2000.0):
            with patch.object(analyzer, '_get_silver_price', return_value=22.0):
                # Ratio = 2000/22 = 90.9 (> 85)
                results = analyzer.analyze()

                # Should have at least one signal about silver being undervalued
                silver_signals = [r for r in results if "silver" in r.title.lower()]
                assert len(silver_signals) >= 1
                assert any(r.severity in [SignalSeverity.MEDIUM, SignalSeverity.HIGH]
                          for r in silver_signals)

    def test_gold_silver_ratio_low(self, analyzer):
        """Test signal when gold/silver ratio is low (silver overvalued)."""
        with patch.object(analyzer, '_get_gold_price', return_value=2000.0):
            with patch.object(analyzer, '_get_silver_price', return_value=35.0):
                # Ratio = 2000/35 = 57.1 (< 65)
                results = analyzer.analyze()

                silver_signals = [r for r in results if "silver" in r.title.lower()]
                assert len(silver_signals) >= 1

    def test_gold_silver_ratio_normal(self, analyzer):
        """Test no signal when ratio is normal."""
        with patch.object(analyzer, '_get_gold_price', return_value=2000.0):
            with patch.object(analyzer, '_get_silver_price', return_value=26.67):
                # Ratio = 2000/26.67 = 75 (between 65 and 85)
                with patch.object(analyzer, '_get_tips_yield', return_value=1.5):
                    results = analyzer.analyze()

                    # Should have no gold/silver ratio signals
                    ratio_signals = [r for r in results
                                    if "ratio" in r.title.lower() or "silver" in r.title.lower()]
                    assert len(ratio_signals) == 0

    def test_tips_yield_signal(self, analyzer):
        """Test signal based on TIPS yield."""
        with patch.object(analyzer, '_get_gold_price', return_value=2000.0):
            with patch.object(analyzer, '_get_silver_price', return_value=26.67):
                with patch.object(analyzer, '_get_tips_yield', return_value=-0.5):
                    # Negative real yield is bullish for gold
                    results = analyzer.analyze()

                    tips_signals = [r for r in results if "tips" in r.title.lower() or "yield" in r.title.lower()]
                    assert len(tips_signals) >= 1
