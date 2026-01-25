"""Tests for Signal model."""
import pytest
from datetime import datetime
from decimal import Decimal

from src.db.models import Signal, SignalType, SignalSeverity, SignalStatus


class TestSignalModel:
    """Tests for Signal model."""

    def test_signal_creation(self):
        """Test creating a Signal instance."""
        signal = Signal(
            signal_type=SignalType.SECTOR,
            sector="tech",
            title="AI Capex Surge",
            description="Mag 7 capex increased 25% QoQ",
            severity=SignalSeverity.INFO,
            source="earnings_reports",
            data={"capex_growth": 0.25, "companies": ["NVDA", "MSFT"]},
        )

        assert signal.signal_type == SignalType.SECTOR
        assert signal.sector == "tech"
        assert signal.severity == SignalSeverity.INFO
        assert signal.status == SignalStatus.ACTIVE

    def test_signal_with_related_symbols(self):
        """Test signal with related symbols."""
        signal = Signal(
            signal_type=SignalType.PRICE,
            title="NVDA hits 52-week high",
            description="NVIDIA reached new all-time high",
            severity=SignalSeverity.MEDIUM,
            source="price_monitor",
            related_symbols=["NVDA"],
        )

        assert signal.related_symbols == ["NVDA"]
