"""Base analyzer class and result model."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

from sqlalchemy.orm import Session

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


# ===== Report-oriented analyzer base =====

@dataclass
class AnalysisReport:
    """Structured report section from a ReportAnalyzer."""
    section_name: str
    rating: Optional[str] = None
    score: Optional[int] = None
    summary: str = ""
    details: List[str] = field(default_factory=list)
    data: Optional[dict] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)


class ReportAnalyzer(ABC):
    """Base class for analyzers that produce report sections + optional signals."""

    def __init__(self, db: Session):
        self.db = db

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def analyze(self) -> AnalysisReport:
        """Run analysis and return a structured report section."""
        pass

    def get_signals(self) -> List[AnalyzerResult]:
        """Return alert-worthy signals (override in subclasses)."""
        return []
