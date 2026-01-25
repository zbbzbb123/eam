"""Tests for analyzer runner service."""
import pytest
from unittest.mock import MagicMock

from src.services.analyzer_runner import AnalyzerRunner
from src.analyzers.base import AnalyzerResult
from src.db.models import SignalSeverity


class TestAnalyzerRunner:
    """Tests for AnalyzerRunner."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = MagicMock()
        session.add = MagicMock()
        session.commit = MagicMock()
        session.refresh = MagicMock()
        return session

    @pytest.fixture
    def mock_analyzer(self):
        """Create mock analyzer."""
        analyzer = MagicMock()
        analyzer.name = "test_analyzer"
        analyzer.sector = "test"
        analyzer.analyze.return_value = [
            AnalyzerResult(
                title="Test Signal",
                description="Test description",
                severity=SignalSeverity.MEDIUM,
                data={"key": "value"},
                related_symbols=["TEST"],
            )
        ]
        return analyzer

    def test_run_analyzer_creates_signals(self, mock_db_session, mock_analyzer):
        """Test that running an analyzer creates signals in database."""
        runner = AnalyzerRunner(mock_db_session)

        signals = runner.run_analyzer(mock_analyzer)

        assert len(signals) == 1
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    def test_run_analyzer_with_no_results(self, mock_db_session):
        """Test analyzer that returns no results."""
        analyzer = MagicMock()
        analyzer.name = "empty_analyzer"
        analyzer.sector = "test"
        analyzer.analyze.return_value = []

        runner = AnalyzerRunner(mock_db_session)
        signals = runner.run_analyzer(analyzer)

        assert len(signals) == 0
        mock_db_session.add.assert_not_called()

    def test_run_all_analyzers(self, mock_db_session, mock_analyzer):
        """Test running all registered analyzers."""
        runner = AnalyzerRunner(mock_db_session)
        runner.register_analyzer(mock_analyzer)

        all_signals = runner.run_all()

        assert len(all_signals) == 1
        mock_analyzer.analyze.assert_called_once()
