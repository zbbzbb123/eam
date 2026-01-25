"""Tests for API schemas."""
import pytest
from datetime import date, datetime
from decimal import Decimal

from pydantic import ValidationError

from src.api.schemas import (
    HoldingCreate, HoldingUpdate, HoldingResponse,
    TransactionCreate, MarketEnum, TierEnum, TransactionActionEnum,
    SignalCreate, SignalTypeEnum, SignalSeverityEnum
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


class TestSignalSchemas:
    """Tests for Signal schemas."""

    def test_signal_create_valid(self):
        """Test creating a valid SignalCreate."""
        signal = SignalCreate(
            signal_type=SignalTypeEnum.SECTOR,
            sector="tech",
            title="AI Capex Surge",
            description="Mag 7 capex increased 25% QoQ",
            severity=SignalSeverityEnum.INFO,
            source="earnings_reports",
            data={"capex_growth": 0.25},
            related_symbols=["NVDA", "MSFT"],
        )

        assert signal.signal_type == SignalTypeEnum.SECTOR
        assert signal.sector == "tech"
        assert signal.title == "AI Capex Surge"

    def test_signal_create_empty_title_rejected(self):
        """Test that empty title is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SignalCreate(
                signal_type=SignalTypeEnum.SECTOR,
                title="",
                description="Some description",
                severity=SignalSeverityEnum.INFO,
                source="test_source",
            )

        assert "String should have at least 1 character" in str(exc_info.value)

    def test_signal_create_title_over_200_chars_rejected(self):
        """Test that title over 200 characters is rejected."""
        long_title = "A" * 201

        with pytest.raises(ValidationError) as exc_info:
            SignalCreate(
                signal_type=SignalTypeEnum.SECTOR,
                title=long_title,
                description="Some description",
                severity=SignalSeverityEnum.INFO,
                source="test_source",
            )

        assert "String should have at most 200 characters" in str(exc_info.value)

    def test_signal_create_empty_description_rejected(self):
        """Test that empty description is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SignalCreate(
                signal_type=SignalTypeEnum.SECTOR,
                title="Valid title",
                description="",
                severity=SignalSeverityEnum.INFO,
                source="test_source",
            )

        assert "String should have at least 1 character" in str(exc_info.value)

    def test_signal_create_sector_over_50_chars_rejected(self):
        """Test that sector over 50 characters is rejected."""
        long_sector = "A" * 51

        with pytest.raises(ValidationError) as exc_info:
            SignalCreate(
                signal_type=SignalTypeEnum.SECTOR,
                sector=long_sector,
                title="Valid title",
                description="Valid description",
                severity=SignalSeverityEnum.INFO,
                source="test_source",
            )

        assert "String should have at most 50 characters" in str(exc_info.value)
