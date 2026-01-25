"""Tests for Portfolio API."""
import pytest
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base, get_db
from src.api.holdings import router as holdings_router
from src.api.portfolio import router as portfolio_router


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
    test_app.include_router(portfolio_router, prefix="/api")
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


class TestPortfolioAPI:
    """Tests for Portfolio API."""

    def test_empty_portfolio_overview(self, client):
        """Test overview with no holdings."""
        response = client.get("/api/portfolio/overview")

        assert response.status_code == 200
        data = response.json()
        assert data["total_value"] == "0"
        assert data["holdings_count"] == 0
        assert len(data["allocations"]) == 3

    def test_portfolio_overview_with_holdings(self, client):
        """Test overview with holdings."""
        # Create holdings in each tier (40/30/30 split = $100k total)
        client.post("/api/holdings", json={
            "symbol": "VOO",
            "market": "US",
            "tier": "stable",
            "quantity": "100.0",
            "avg_cost": "400.00",  # $40,000
            "first_buy_date": "2025-01-01",
            "buy_reason": "S&P 500",
        })
        client.post("/api/holdings", json={
            "symbol": "QQQ",
            "market": "US",
            "tier": "medium",
            "quantity": "50.0",
            "avg_cost": "600.00",  # $30,000
            "first_buy_date": "2025-01-01",
            "buy_reason": "Nasdaq",
        })
        client.post("/api/holdings", json={
            "symbol": "NVDA",
            "market": "US",
            "tier": "gamble",
            "quantity": "30.0",
            "avg_cost": "1000.00",  # $30,000
            "first_buy_date": "2025-01-01",
            "buy_reason": "AI play",
        })

        response = client.get("/api/portfolio/overview")

        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["total_value"]) == Decimal("100000")
        assert data["holdings_count"] == 3

        # Check allocations (40/30/30)
        allocations = {a["tier"]: a for a in data["allocations"]}
        assert Decimal(allocations["stable"]["actual_pct"]) == Decimal("40")
        assert Decimal(allocations["medium"]["actual_pct"]) == Decimal("30")
        assert Decimal(allocations["gamble"]["actual_pct"]) == Decimal("30")

    def test_rebalance_no_suggestions_when_balanced(self, client):
        """Test no rebalance suggestions when portfolio is balanced."""
        # Create balanced portfolio (40/30/30)
        client.post("/api/holdings", json={
            "symbol": "VOO",
            "market": "US",
            "tier": "stable",
            "quantity": "100.0",
            "avg_cost": "400.00",
            "first_buy_date": "2025-01-01",
            "buy_reason": "S&P 500",
        })
        client.post("/api/holdings", json={
            "symbol": "QQQ",
            "market": "US",
            "tier": "medium",
            "quantity": "50.0",
            "avg_cost": "600.00",
            "first_buy_date": "2025-01-01",
            "buy_reason": "Nasdaq",
        })
        client.post("/api/holdings", json={
            "symbol": "NVDA",
            "market": "US",
            "tier": "gamble",
            "quantity": "30.0",
            "avg_cost": "1000.00",
            "first_buy_date": "2025-01-01",
            "buy_reason": "AI play",
        })

        response = client.get("/api/portfolio/rebalance-suggestions")

        assert response.status_code == 200
        data = response.json()
        assert data["needs_rebalance"] is False
        assert len(data["suggestions"]) == 0

    def test_rebalance_suggestions_when_unbalanced(self, client):
        """Test rebalance suggestions when portfolio is unbalanced."""
        # Create unbalanced portfolio (all in gamble)
        client.post("/api/holdings", json={
            "symbol": "NVDA",
            "market": "US",
            "tier": "gamble",
            "quantity": "100.0",
            "avg_cost": "1000.00",
            "first_buy_date": "2025-01-01",
            "buy_reason": "YOLO",
        })

        response = client.get("/api/portfolio/rebalance-suggestions")

        assert response.status_code == 200
        data = response.json()
        assert data["needs_rebalance"] is True
        assert len(data["suggestions"]) > 0
