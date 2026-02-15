"""Tests for database models."""
import pytest
from datetime import date, datetime
from decimal import Decimal

from src.db.models import (
    Holding, Transaction, DailyQuote,
    Market, Tier, HoldingStatus, TransactionAction
)


class TestHoldingModel:
    """Tests for Holding model."""

    def test_holding_creation(self):
        """Test creating a Holding instance."""
        holding = Holding(
            symbol="NVDA",
            market=Market.US,
            tier=Tier.GAMBLE,
            quantity=Decimal("10.0"),
            avg_cost=Decimal("890.00"),
            first_buy_date=date(2025, 1, 20),
            buy_reason="AI compute play before earnings",
            stop_loss_price=Decimal("800.00"),
            take_profit_price=Decimal("1050.00"),
        )

        assert holding.symbol == "NVDA"
        assert holding.market == Market.US
        assert holding.tier == Tier.GAMBLE
        assert holding.quantity == Decimal("10.0")
        assert holding.avg_cost == Decimal("890.00")
        assert holding.buy_reason == "AI compute play before earnings"

    def test_holding_default_status(self):
        """Test that holding defaults to active status."""
        holding = Holding(
            symbol="VOO",
            market=Market.US,
            tier=Tier.CORE,
            quantity=Decimal("50.0"),
            avg_cost=Decimal("450.00"),
            first_buy_date=date(2025, 1, 1),
            buy_reason="Core S&P 500 holding",
        )

        assert holding.status == HoldingStatus.ACTIVE


class TestTransactionModel:
    """Tests for Transaction model."""

    def test_transaction_creation(self):
        """Test creating a Transaction instance."""
        transaction = Transaction(
            holding_id=1,
            action=TransactionAction.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("890.00"),
            total_amount=Decimal("8900.00"),
            reason="Initial position",
            transaction_date=datetime(2025, 1, 20, 10, 30, 0),
        )

        assert transaction.action == TransactionAction.BUY
        assert transaction.quantity == Decimal("10.0")
        assert transaction.total_amount == Decimal("8900.00")


class TestDailyQuoteModel:
    """Tests for DailyQuote model."""

    def test_daily_quote_creation(self):
        """Test creating a DailyQuote instance."""
        quote = DailyQuote(
            symbol="NVDA",
            market=Market.US,
            trade_date=date(2025, 1, 24),
            open=Decimal("920.00"),
            high=Decimal("935.00"),
            low=Decimal("915.00"),
            close=Decimal("930.00"),
            volume=50000000,
        )

        assert quote.symbol == "NVDA"
        assert quote.close == Decimal("930.00")
        assert quote.volume == 50000000
