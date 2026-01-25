"""Tests for base analyzer."""
import pytest
from datetime import datetime
from typing import List

from src.analyzers.base import BaseAnalyzer, AnalyzerResult
from src.db.models import SignalSeverity


class TestAnalyzerResult:
    """Tests for AnalyzerResult."""

    def test_analyzer_result_creation(self):
        """Test creating an AnalyzerResult."""
        result = AnalyzerResult(
            title="Test Signal",
            description="This is a test",
            severity=SignalSeverity.MEDIUM,
            data={"key": "value"},
            related_symbols=["AAPL"],
        )

        assert result.title == "Test Signal"
        assert result.severity == SignalSeverity.MEDIUM
        assert result.data == {"key": "value"}


class MockAnalyzer(BaseAnalyzer):
    """Mock analyzer for testing."""

    @property
    def name(self) -> str:
        return "mock_analyzer"

    @property
    def sector(self) -> str:
        return "test"

    def analyze(self) -> List[AnalyzerResult]:
        return [
            AnalyzerResult(
                title="Mock Signal",
                description="Mock description",
                severity=SignalSeverity.LOW,
            )
        ]


class TestBaseAnalyzer:
    """Tests for BaseAnalyzer."""

    def test_analyzer_name(self):
        """Test analyzer has a name."""
        analyzer = MockAnalyzer()
        assert analyzer.name == "mock_analyzer"

    def test_analyzer_sector(self):
        """Test analyzer has a sector."""
        analyzer = MockAnalyzer()
        assert analyzer.sector == "test"

    def test_analyze_returns_results(self):
        """Test analyze returns AnalyzerResult list."""
        analyzer = MockAnalyzer()
        results = analyzer.analyze()

        assert len(results) == 1
        assert results[0].title == "Mock Signal"
