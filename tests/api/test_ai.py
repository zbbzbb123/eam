"""Tests for AI API endpoints."""
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base, get_db
from src.db.models import Holding, Market, Tier, HoldingStatus
from src.api.ai import router as ai_router
from src.services.ai_advisor import HoldingAnalysis
from src.services.llm_client import LLMError


# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_test_app():
    test_app = FastAPI()
    test_app.include_router(ai_router, prefix="/api")
    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


@pytest.fixture(scope="function")
def client():
    Base.metadata.create_all(bind=engine)
    test_app = create_test_app()
    with TestClient(test_app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_holding():
    """Insert a sample holding into the test DB."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    holding = Holding(
        symbol="AAPL",
        market=Market.US,
        tier=Tier.STABLE,
        quantity=Decimal("100"),
        avg_cost=Decimal("150.00"),
        first_buy_date=date(2024, 1, 1),
        buy_reason="Strong fundamentals",
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    holding_id = holding.id
    db.close()
    return holding_id


def _mock_analysis(symbol="AAPL"):
    return HoldingAnalysis(
        symbol=symbol,
        status_assessment="Test assessment",
        recommended_action="hold",
        key_concerns=["concern1"],
        next_catalyst="earnings",
        confidence="medium",
        analysis_date=date.today(),
        model_used="test-model",
    )


class TestAnalyzeHolding:
    @patch("src.api.ai._advisor")
    def test_analyze_holding_success(self, mock_advisor, client, sample_holding):
        mock_advisor.analyze_holding = AsyncMock(return_value=_mock_analysis())
        response = client.post(f"/api/ai/analyze-holding/{sample_holding}?quality=true")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert data["recommended_action"] == "hold"
        assert data["confidence"] == "medium"

    def test_analyze_holding_not_found(self, client):
        response = client.post("/api/ai/analyze-holding/9999")
        assert response.status_code == 404

    @patch("src.api.ai._advisor")
    def test_analyze_holding_llm_error(self, mock_advisor, client, sample_holding):
        mock_advisor.analyze_holding = AsyncMock(side_effect=LLMError("fail"))
        response = client.post(f"/api/ai/analyze-holding/{sample_holding}")
        assert response.status_code == 500
        assert "AI analysis failed" in response.json()["detail"]

    @patch("src.api.ai._advisor")
    def test_analyze_holding_quality_false(self, mock_advisor, client, sample_holding):
        mock_advisor.analyze_holding = AsyncMock(return_value=_mock_analysis())
        response = client.post(f"/api/ai/analyze-holding/{sample_holding}?quality=false")
        assert response.status_code == 200
        mock_advisor.analyze_holding.assert_called_once()
        _, kwargs = mock_advisor.analyze_holding.call_args
        assert kwargs["use_quality_model"] is False


class TestAnalyzeAll:
    @patch("src.api.ai._advisor")
    def test_analyze_all_success(self, mock_advisor, client):
        mock_advisor.analyze_all_holdings = AsyncMock(
            return_value=[_mock_analysis("AAPL"), _mock_analysis("GOOGL")]
        )
        response = client.post("/api/ai/analyze-all")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["symbol"] == "AAPL"

    @patch("src.api.ai._advisor")
    def test_analyze_all_empty(self, mock_advisor, client):
        mock_advisor.analyze_all_holdings = AsyncMock(return_value=[])
        response = client.post("/api/ai/analyze-all")
        assert response.status_code == 200
        assert response.json() == []

    @patch("src.api.ai._advisor")
    def test_analyze_all_error(self, mock_advisor, client):
        mock_advisor.analyze_all_holdings = AsyncMock(side_effect=LLMError("fail"))
        response = client.post("/api/ai/analyze-all")
        assert response.status_code == 500


class TestPortfolioAdvice:
    @patch("src.api.ai._advisor")
    def test_portfolio_advice_success(self, mock_advisor, client):
        mock_advisor.generate_portfolio_advice = AsyncMock(return_value="Buy more AAPL")
        response = client.post("/api/ai/portfolio-advice")
        assert response.status_code == 200
        assert response.json()["advice"] == "Buy more AAPL"

    @patch("src.api.ai._advisor")
    def test_portfolio_advice_error(self, mock_advisor, client):
        mock_advisor.generate_portfolio_advice = AsyncMock(side_effect=LLMError("fail"))
        response = client.post("/api/ai/portfolio-advice")
        assert response.status_code == 500


class TestSummarize:
    @patch("src.api.ai._summarizer")
    def test_summarize_success(self, mock_summarizer, client):
        mock_summarizer.summarize_text = AsyncMock(return_value="Summary here")
        response = client.post("/api/ai/summarize", json={
            "text": "Long text to summarize",
            "max_words": 100,
            "language": "en",
        })
        assert response.status_code == 200
        assert response.json()["summary"] == "Summary here"
        mock_summarizer.summarize_text.assert_called_once_with(
            "Long text to summarize", max_words=100, language="en"
        )

    @patch("src.api.ai._summarizer")
    def test_summarize_defaults(self, mock_summarizer, client):
        mock_summarizer.summarize_text = AsyncMock(return_value="摘要")
        response = client.post("/api/ai/summarize", json={"text": "Some text"})
        assert response.status_code == 200
        mock_summarizer.summarize_text.assert_called_once_with(
            "Some text", max_words=200, language="zh"
        )

    def test_summarize_missing_text(self, client):
        response = client.post("/api/ai/summarize", json={})
        assert response.status_code == 422


class TestEnhanceReport:
    @patch("src.api.ai._summarizer")
    @patch("src.api.ai._report_service")
    def test_enhance_report_success(self, mock_report_svc, mock_summarizer, client):
        mock_report = MagicMock()
        mock_report_svc.generate_report.return_value = mock_report
        mock_report_svc.format_as_text.return_value = "Raw report"
        mock_summarizer.enhance_weekly_report = AsyncMock(return_value="Enhanced report")

        response = client.post("/api/ai/enhance-report")
        assert response.status_code == 200
        data = response.json()
        assert data["report"] == "Enhanced report"
        assert data["enhanced"] is True

    @patch("src.api.ai._summarizer")
    @patch("src.api.ai._report_service")
    def test_enhance_report_llm_error(self, mock_report_svc, mock_summarizer, client):
        mock_report = MagicMock()
        mock_report_svc.generate_report.return_value = mock_report
        mock_report_svc.format_as_text.return_value = "Raw report"
        mock_summarizer.enhance_weekly_report = AsyncMock(side_effect=LLMError("fail"))

        response = client.post("/api/ai/enhance-report")
        assert response.status_code == 500
