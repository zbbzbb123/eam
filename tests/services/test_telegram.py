"""Tests for Telegram service."""
import pytest
from unittest.mock import Mock

from src.services.telegram import TelegramService, format_signal_message
from src.db.models import Signal, SignalType, SignalSeverity


class TestFormatSignalMessage:
    """Tests for message formatting."""

    def test_format_signal_message(self):
        """Test formatting a signal as Telegram message."""
        signal = Signal(
            id=1,
            signal_type=SignalType.SECTOR,
            sector="precious_metals",
            title="Silver Undervalued",
            description="Gold/Silver ratio at 90. Consider adding silver.",
            severity=SignalSeverity.MEDIUM,
            source="precious_metals_analyzer",
            related_symbols=["SLV", "GLD"],
        )

        message = format_signal_message(signal)

        assert "Silver Undervalued" in message
        assert "MEDIUM" in message
        assert "precious_metals" in message
        assert "SLV" in message

    def test_format_critical_signal(self):
        """Test that critical signals have special formatting."""
        signal = Signal(
            id=2,
            signal_type=SignalType.PRICE,
            title="Stop Loss Triggered",
            description="NVDA hit stop loss at $800",
            severity=SignalSeverity.CRITICAL,
            source="price_monitor",
            related_symbols=["NVDA"],
        )

        message = format_signal_message(signal)

        assert "CRITICAL" in message
        assert "Stop Loss" in message


class TestTelegramService:
    """Tests for TelegramService."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock()
        settings.telegram_bot_token = "test_token"
        settings.telegram_chat_id = "123456"
        settings.telegram_enabled = True
        return settings

    def test_service_disabled_when_no_token(self):
        """Test service is disabled without token."""
        settings = Mock()
        settings.telegram_bot_token = ""
        settings.telegram_chat_id = ""
        settings.telegram_enabled = False

        service = TelegramService(settings)
        assert not service.is_enabled()

    def test_service_enabled_with_config(self, mock_settings):
        """Test service is enabled with proper config."""
        service = TelegramService(mock_settings)
        assert service.is_enabled()

    @pytest.mark.asyncio
    async def test_send_signal_when_disabled(self):
        """Test that send_signal returns False when disabled."""
        settings = Mock()
        settings.telegram_bot_token = ""
        settings.telegram_chat_id = ""
        settings.telegram_enabled = False

        service = TelegramService(settings)
        signal = Signal(
            signal_type=SignalType.SECTOR,
            title="Test",
            description="Test",
            severity=SignalSeverity.LOW,
            source="test",
        )

        result = await service.send_signal(signal)
        assert result is False
