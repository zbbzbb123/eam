"""Telegram notification service."""
import logging

from src.db.models import Signal, SignalSeverity

logger = logging.getLogger(__name__)

# Severity emoji mapping
SEVERITY_EMOJI = {
    SignalSeverity.INFO: "ℹ️",
    SignalSeverity.LOW: "🔵",
    SignalSeverity.MEDIUM: "🟡",
    SignalSeverity.HIGH: "🟠",
    SignalSeverity.CRITICAL: "🔴",
}


def format_signal_message(signal: Signal) -> str:
    """
    Format a signal as a Telegram message.

    Args:
        signal: The signal to format.

    Returns:
        Formatted message string.
    """
    emoji = SEVERITY_EMOJI.get(signal.severity, "📊")
    severity_name = signal.severity.value.upper()

    lines = [
        f"{emoji} *{signal.title}*",
        "",
        f"📊 Severity: {severity_name}",
    ]

    if signal.sector:
        lines.append(f"📁 Sector: {signal.sector}")

    lines.append("")
    lines.append(signal.description)

    if signal.related_symbols:
        symbols = ", ".join(signal.related_symbols)
        lines.append("")
        lines.append(f"🏷️ Symbols: {symbols}")

    lines.append("")
    lines.append(f"_Source: {signal.source}_")

    return "\n".join(lines)


class TelegramService:
    """Service for sending Telegram notifications."""

    def __init__(self, settings):
        """
        Initialize Telegram service.

        Args:
            settings: Application settings with Telegram config.
        """
        self._token = settings.telegram_bot_token
        self._chat_id = settings.telegram_chat_id
        self._enabled = settings.telegram_enabled
        self._bot = None

    def is_enabled(self) -> bool:
        """Check if Telegram notifications are enabled."""
        return bool(self._enabled and self._token and self._chat_id)

    async def _get_bot(self):
        """Get or create bot instance."""
        if self._bot is None:
            try:
                from telegram import Bot
                self._bot = Bot(token=self._token)
            except ImportError:
                logger.warning("python-telegram-bot not installed")
                return None
        return self._bot

    async def send_signal(self, signal: Signal) -> bool:
        """
        Send a signal notification via Telegram.

        Args:
            signal: The signal to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self.is_enabled():
            logger.debug("Telegram notifications disabled")
            return False

        try:
            bot = await self._get_bot()
            if not bot:
                return False

            message = format_signal_message(signal)

            await bot.send_message(
                chat_id=self._chat_id,
                text=message,
                parse_mode="Markdown",
            )

            logger.info(f"Sent Telegram notification for signal {signal.id}")
            return True

        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
            return False

    async def send_message(self, text: str) -> bool:
        """
        Send a custom message via Telegram.

        Args:
            text: The message text.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self.is_enabled():
            return False

        try:
            bot = await self._get_bot()
            if not bot:
                return False

            await bot.send_message(
                chat_id=self._chat_id,
                text=text,
                parse_mode="Markdown",
            )
            return True

        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False


def get_telegram_service():
    """Get TelegramService instance with current settings."""
    from src.config import get_settings
    return TelegramService(get_settings())
