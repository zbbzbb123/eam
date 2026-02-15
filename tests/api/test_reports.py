"""Tests for Reports API."""
import pytest
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base, get_db
from src.api.holdings import router as holdings_router
from src.api.reports import router as reports_router


# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_test_app():
    """Create a test FastAPI app without the startup event."""
    test_app = FastAPI()
    test_app.include_router(holdings_router, prefix="/api")
    test_app.include_router(reports_router, prefix="/api")
    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


@pytest.fixture(scope="function")
def client():
    """Create test client with fresh database."""
    Base.metadata.create_all(bind=engine)
    test_app = create_test_app()

    with TestClient(test_app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)


def _create_holding(client, symbol="VOO", tier="core", quantity="100.0", avg_cost="400.00"):
    """Helper to create a holding."""
    return client.post("/api/holdings", json={
        "symbol": symbol,
        "market": "US",
        "tier": tier,
        "quantity": quantity,
        "avg_cost": avg_cost,
        "first_buy_date": "2025-01-01",
        "buy_reason": "Test holding",
    })


class TestReportsAPI:
    """Tests for Reports API."""

    def test_weekly_report_empty(self, client):
        """Test weekly report with no holdings."""
        response = client.get("/api/reports/weekly")
        assert response.status_code == 200
        data = response.json()
        assert "report_date" in data
        assert "portfolio_summary" in data
        assert data["portfolio_summary"]["total_value"] == "0"
        assert "signal_summary" in data
        assert "risk_alerts" in data
        assert "action_items" in data

    def test_weekly_report_with_holdings(self, client):
        """Test weekly report with holdings."""
        _create_holding(client, "VOO", "core", "100.0", "400.00")
        _create_holding(client, "QQQ", "growth", "50.0", "600.00")

        response = client.get("/api/reports/weekly")
        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["portfolio_summary"]["total_value"]) > 0
        assert len(data["portfolio_summary"]["tiers"]) == 3

    def test_weekly_report_text(self, client):
        """Test weekly report as plain text."""
        _create_holding(client, "VOO", "core", "100.0", "400.00")

        response = client.get("/api/reports/weekly/text")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        text = response.text
        assert "周报" in text
        assert "仓位全景" in text

    def test_weekly_report_text_empty(self, client):
        """Test weekly report text with no data."""
        response = client.get("/api/reports/weekly/text")
        assert response.status_code == 200
        assert "周报" in response.text

    def test_weekly_report_markdown(self, client):
        """Test weekly report as Markdown."""
        _create_holding(client, "VOO", "core", "100.0", "400.00")

        response = client.get("/api/reports/weekly/markdown")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        md = response.text
        assert "# 投资周报" in md
        assert "## 仓位全景" in md

    def test_weekly_report_markdown_empty(self, client):
        """Test weekly report markdown with no data."""
        response = client.get("/api/reports/weekly/markdown")
        assert response.status_code == 200
        assert "# 投资周报" in response.text

    def test_weekly_report_risk_alerts_no_stop_loss(self, client):
        """Test that holdings without stop loss generate risk alerts."""
        _create_holding(client, "NVDA", "gamble", "100.0", "1000.00")

        response = client.get("/api/reports/weekly")
        assert response.status_code == 200
        data = response.json()
        # Should have risk alert for missing stop loss
        alert_messages = [a["message"] for a in data["risk_alerts"]]
        assert any("stop loss" in m.lower() or "止损" in m for m in alert_messages)
