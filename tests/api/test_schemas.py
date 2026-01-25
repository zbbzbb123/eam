"""Tests for API schemas."""
import pytest
from datetime import date, datetime
from decimal import Decimal

from pydantic import ValidationError

from src.api.schemas import (
    HoldingCreate, HoldingUpdate, HoldingResponse,
    TransactionCreate, MarketEnum, TierEnum, TransactionActionEnum
)


class TestHoldingSchemas:
    """Tests for Holding schemas."""

    def test_holding_create_valid(self):
        """Test creating a valid HoldingCreate."""
        holding = HoldingCreate(
            symbol="NVDA",
            market=MarketEnum.US,
            tier=TierEnum.GAMBLE,
            quantity=Decimal("10.0"),
            avg_cost=Decimal("890.00"),
            first_buy_date=date(2025, 1, 20),
            buy_reason="AI compute play",
        )

        assert holding.symbol == "NVDA"
        assert holding.market == MarketEnum.US

    def test_holding_create_invalid_quantity(self):
        """Test that negative quantity is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            HoldingCreate(
                symbol="NVDA",
                market=MarketEnum.US,
                tier=TierEnum.GAMBLE,
                quantity=Decimal("-10.0"),
                avg_cost=Decimal("890.00"),
                first_buy_date=date(2025, 1, 20),
                buy_reason="AI compute play",
            )

        assert "greater than 0" in str(exc_info.value)

    def test_holding_create_empty_reason_rejected(self):
        """Test that empty buy_reason is rejected."""
        with pytest.raises(ValidationError):
            HoldingCreate(
                symbol="NVDA",
                market=MarketEnum.US,
                tier=TierEnum.GAMBLE,
                quantity=Decimal("10.0"),
                avg_cost=Decimal("890.00"),
                first_buy_date=date(2025, 1, 20),
                buy_reason="",
            )

    def test_holding_update_partial(self):
        """Test partial update with only some fields."""
        update = HoldingUpdate(
            stop_loss_price=Decimal("800.00"),
        )

        assert update.stop_loss_price == Decimal("800.00")
        assert update.quantity is None


class TestTransactionSchemas:
    """Tests for Transaction schemas."""

    def test_transaction_create_valid(self):
        """Test creating a valid TransactionCreate."""
        transaction = TransactionCreate(
            holding_id=1,
            action=TransactionActionEnum.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("890.00"),
            reason="Initial position",
            transaction_date=datetime(2025, 1, 20, 10, 30, 0),
        )

        assert transaction.action == TransactionActionEnum.BUY
        assert transaction.quantity == Decimal("10.0")
