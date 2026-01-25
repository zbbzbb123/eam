"""Base analyzer class and result model."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

from src.db.models import SignalSeverity


@dataclass
class AnalyzerResult:
    """Result from an analyzer."""
    title: str
    description: str
    severity: SignalSeverity
    data: Optional[dict] = field(default_factory=dict)
    related_symbols: Optional[List[str]] = field(default_factory=list)
    expires_at: Optional[datetime] = None


class BaseAnalyzer(ABC):
    """Abstract base class for all analyzers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the analyzer name (used as signal source)."""
        pass

    @property
    @abstractmethod
    def sector(self) -> str:
        """Return the sector this analyzer covers."""
        pass

    @abstractmethod
    def analyze(self) -> List[AnalyzerResult]:
        """
        Run the analysis and return a list of signals.

        Returns:
            List of AnalyzerResult objects representing detected signals.
        """
        pass

    def should_generate_signal(self, result: AnalyzerResult) -> bool:
        """
        Determine if a result should generate a signal.
        Override in subclasses for custom logic.

        Args:
            result: The analyzer result to evaluate.

        Returns:
            True if signal should be generated, False otherwise.
        """
        return True
