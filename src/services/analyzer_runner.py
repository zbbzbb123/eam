"""Analyzer runner service."""
import logging
from typing import List, Optional
from datetime import datetime

from sqlalchemy.orm import Session

from src.analyzers.base import BaseAnalyzer, AnalyzerResult
from src.db.models import Signal, SignalType, SignalSeverity
from src.services.telegram import TelegramService

logger = logging.getLogger(__name__)


class AnalyzerRunner:
    """
    Service for running analyzers and creating signals.

    Manages analyzer registration, execution, and signal persistence.
    """

    def __init__(self, db: Session, telegram_service: Optional[TelegramService] = None):
        """
        Initialize the analyzer runner.

        Args:
            db: Database session for persisting signals.
            telegram_service: Optional Telegram service for notifications.
        """
        self._db = db
        self._telegram = telegram_service
        self._analyzers: List[BaseAnalyzer] = []

    def register_analyzer(self, analyzer: BaseAnalyzer) -> None:
        """
        Register an analyzer to be run.

        Args:
            analyzer: The analyzer to register.
        """
        self._analyzers.append(analyzer)
        logger.info(f"Registered analyzer: {analyzer.name}")

    def run_analyzer(self, analyzer: BaseAnalyzer) -> List[Signal]:
        """
        Run a single analyzer and persist results.

        Args:
            analyzer: The analyzer to run.

        Returns:
            List of created Signal objects.
        """
        logger.info(f"Running analyzer: {analyzer.name}")
        signals = []

        try:
            results = analyzer.analyze()

            for result in results:
                signal = self._create_signal(analyzer, result)
                signals.append(signal)

            logger.info(f"Analyzer {analyzer.name} generated {len(signals)} signals")

        except Exception as e:
            logger.error(f"Error running analyzer {analyzer.name}: {e}")

        return signals

    def _create_signal(self, analyzer: BaseAnalyzer, result: AnalyzerResult) -> Signal:
        """
        Create and persist a signal from an analyzer result.

        Args:
            analyzer: The analyzer that generated the result.
            result: The analyzer result.

        Returns:
            The created Signal object.
        """
        signal = Signal(
            signal_type=SignalType.SECTOR,
            sector=analyzer.sector,
            title=result.title,
            description=result.description,
            severity=result.severity,
            source=analyzer.name,
            data=result.data,
            related_symbols=result.related_symbols,
            expires_at=result.expires_at,
        )

        self._db.add(signal)
        self._db.commit()
        self._db.refresh(signal)

        logger.debug(f"Created signal: {signal.id} - {signal.title}")

        return signal

    def run_all(self) -> List[Signal]:
        """
        Run all registered analyzers.

        Returns:
            List of all created signals.
        """
        all_signals = []

        for analyzer in self._analyzers:
            signals = self.run_analyzer(analyzer)
            all_signals.extend(signals)

        return all_signals

    async def run_all_with_notifications(self) -> List[Signal]:
        """
        Run all analyzers and send Telegram notifications for important signals.

        Returns:
            List of all created signals.
        """
        all_signals = self.run_all()

        if self._telegram and self._telegram.is_enabled():
            for signal in all_signals:
                # Only notify for MEDIUM severity and above
                if signal.severity in [
                    SignalSeverity.MEDIUM,
                    SignalSeverity.HIGH,
                    SignalSeverity.CRITICAL,
                ]:
                    success = await self._telegram.send_signal(signal)
                    if success:
                        signal.telegram_sent = True
                        signal.telegram_sent_at = datetime.utcnow()
                        self._db.commit()

        return all_signals
