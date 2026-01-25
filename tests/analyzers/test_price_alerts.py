"""Tests for price alert analyzer."""
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import date

from src.analyzers.price_alerts import PriceAlertAnalyzer
from src.db.models import Holding, Market, Tier, SignalSeverity


class TestPriceAlertAnalyzer:
    """Tests for PriceAlertAnalyzer."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def sample_holding(self):
        """Create a sample holding."""
        holding = Holding(
            id=1,
            symbol="NVDA",
            market=Market.US,
            tier=Tier.GAMBLE,
            quantity=Decimal("10"),
            avg_cost=Decimal("900"),
            first_buy_date=date(2025, 1, 1),
            buy_reason="AI play",
            stop_loss_price=Decimal("800"),
            take_profit_price=Decimal("1100"),
        )
        return holding

    def test_analyzer_name(self, mock_db):
        """Test analyzer name."""
        analyzer = PriceAlertAnalyzer(mock_db)
        assert analyzer.name == "price_alert_analyzer"

    def test_analyzer_sector(self, mock_db):
        """Test analyzer sector."""
        analyzer = PriceAlertAnalyzer(mock_db)
        assert analyzer.sector == "price"

    def test_stop_loss_triggered(self, mock_db, sample_holding):
        """Test signal when stop loss is triggered."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = [sample_holding]

        analyzer = PriceAlertAnalyzer(mock_db)

        # Mock price below stop loss
        with patch.object(analyzer, '_get_current_price', return_value=780.0):
            results = analyzer.analyze()

            stop_loss_signals = [r for r in results if "stop" in r.title.lower()]
            assert len(stop_loss_signals) == 1
            assert stop_loss_signals[0].severity == SignalSeverity.CRITICAL

    def test_take_profit_triggered(self, mock_db, sample_holding):
        """Test signal when take profit is triggered."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = [sample_holding]

        analyzer = PriceAlertAnalyzer(mock_db)

        # Mock price above take profit
        with patch.object(analyzer, '_get_current_price', return_value=1150.0):
            results = analyzer.analyze()

            take_profit_signals = [r for r in results if "profit" in r.title.lower()]
            assert len(take_profit_signals) == 1
            assert take_profit_signals[0].severity == SignalSeverity.HIGH

    def test_large_daily_move(self, mock_db, sample_holding):
        """Test signal for large daily price move."""
        sample_holding.stop_loss_price = None
        sample_holding.take_profit_price = None
        mock_db.execute.return_value.scalars.return_value.all.return_value = [sample_holding]

        analyzer = PriceAlertAnalyzer(mock_db)

        # Mock 8% daily drop
        with patch.object(analyzer, '_get_current_price', return_value=850.0):
            with patch.object(analyzer, '_get_previous_close', return_value=920.0):
                results = analyzer.analyze()

                move_signals = [r for r in results if "move" in r.title.lower() or "drop" in r.title.lower()]
                assert len(move_signals) >= 1

    def test_no_signal_normal_price(self, mock_db, sample_holding):
        """Test no signal when price is normal."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = [sample_holding]

        analyzer = PriceAlertAnalyzer(mock_db)

        # Mock price in normal range
        with patch.object(analyzer, '_get_current_price', return_value=950.0):
            with patch.object(analyzer, '_get_previous_close', return_value=945.0):
                results = analyzer.analyze()

                # Should have no alerts
                assert len(results) == 0
