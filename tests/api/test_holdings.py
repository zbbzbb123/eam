"""Tests for Holdings API."""
import pytest
from datetime import date, datetime
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base, get_db
from src.api.holdings import router as holdings_router


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


class TestHoldingsAPI:
    """Tests for Holdings CRUD API."""

    def test_create_holding(self, client):
        """Test creating a new holding."""
        response = client.post("/api/holdings", json={
            "symbol": "NVDA",
            "market": "US",
            "tier": "gamble",
            "quantity": "10.0",
            "avg_cost": "890.00",
            "first_buy_date": "2025-01-20",
            "buy_reason": "AI compute play before earnings",
            "stop_loss_price": "800.00",
            "take_profit_price": "1050.00",
        })

        assert response.status_code == 201
        data = response.json()
        assert data["symbol"] == "NVDA"
        assert data["tier"] == "gamble"
        assert data["status"] == "active"
        assert "id" in data

    def test_list_holdings(self, client):
        """Test listing holdings."""
        # Create two holdings
        client.post("/api/holdings", json={
            "symbol": "VOO",
            "market": "US",
            "tier": "stable",
            "quantity": "50.0",
            "avg_cost": "450.00",
            "first_buy_date": "2025-01-01",
            "buy_reason": "Core S&P 500",
        })
        client.post("/api/holdings", json={
            "symbol": "QQQ",
            "market": "US",
            "tier": "medium",
            "quantity": "20.0",
            "avg_cost": "420.00",
            "first_buy_date": "2025-01-15",
            "buy_reason": "Tech exposure",
        })

        response = client.get("/api/holdings")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_holdings_filter_by_tier(self, client):
        """Test filtering holdings by tier."""
        client.post("/api/holdings", json={
            "symbol": "VOO",
            "market": "US",
            "tier": "stable",
            "quantity": "50.0",
            "avg_cost": "450.00",
            "first_buy_date": "2025-01-01",
            "buy_reason": "Core S&P 500",
        })
        client.post("/api/holdings", json={
            "symbol": "NVDA",
            "market": "US",
            "tier": "gamble",
            "quantity": "10.0",
            "avg_cost": "890.00",
            "first_buy_date": "2025-01-20",
            "buy_reason": "AI play",
        })

        response = client.get("/api/holdings?tier=stable")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "VOO"

    def test_get_holding(self, client):
        """Test getting a specific holding."""
        create_response = client.post("/api/holdings", json={
            "symbol": "NVDA",
            "market": "US",
            "tier": "gamble",
            "quantity": "10.0",
            "avg_cost": "890.00",
            "first_buy_date": "2025-01-20",
            "buy_reason": "AI compute play",
        })
        holding_id = create_response.json()["id"]

        response = client.get(f"/api/holdings/{holding_id}")
        assert response.status_code == 200
        assert response.json()["symbol"] == "NVDA"

    def test_get_holding_not_found(self, client):
        """Test 404 for non-existent holding."""
        response = client.get("/api/holdings/999")
        assert response.status_code == 404

    def test_update_holding(self, client):
        """Test updating a holding."""
        create_response = client.post("/api/holdings", json={
            "symbol": "NVDA",
            "market": "US",
            "tier": "gamble",
            "quantity": "10.0",
            "avg_cost": "890.00",
            "first_buy_date": "2025-01-20",
            "buy_reason": "AI compute play",
        })
        holding_id = create_response.json()["id"]

        response = client.patch(f"/api/holdings/{holding_id}", json={
            "stop_loss_price": "850.00",
            "notes": "Updated stop loss",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["stop_loss_price"] == "850.0000"
        assert data["notes"] == "Updated stop loss"

    def test_delete_holding(self, client):
        """Test deleting a holding."""
        create_response = client.post("/api/holdings", json={
            "symbol": "NVDA",
            "market": "US",
            "tier": "gamble",
            "quantity": "10.0",
            "avg_cost": "890.00",
            "first_buy_date": "2025-01-20",
            "buy_reason": "AI compute play",
        })
        holding_id = create_response.json()["id"]

        delete_response = client.delete(f"/api/holdings/{holding_id}")
        assert delete_response.status_code == 204

        get_response = client.get(f"/api/holdings/{holding_id}")
        assert get_response.status_code == 404


class TestTransactionsAPI:
    """Tests for Transactions API."""

    def test_create_buy_transaction(self, client):
        """Test creating a buy transaction."""
        create_response = client.post("/api/holdings", json={
            "symbol": "NVDA",
            "market": "US",
            "tier": "gamble",
            "quantity": "10.0",
            "avg_cost": "890.00",
            "first_buy_date": "2025-01-20",
            "buy_reason": "AI compute play",
        })
        holding_id = create_response.json()["id"]

        response = client.post(f"/api/holdings/{holding_id}/transactions", json={
            "holding_id": holding_id,
            "action": "buy",
            "quantity": "5.0",
            "price": "920.00",
            "reason": "Adding to position",
            "transaction_date": "2025-01-24T10:30:00",
        })

        assert response.status_code == 201
        data = response.json()
        assert data["action"] == "buy"
        assert data["total_amount"] == "4600.0000"

        # Verify holding was updated
        holding = client.get(f"/api/holdings/{holding_id}").json()
        assert holding["quantity"] == "15.0000"

    def test_create_sell_transaction_closes_position(self, client):
        """Test that selling all shares closes the position."""
        create_response = client.post("/api/holdings", json={
            "symbol": "NVDA",
            "market": "US",
            "tier": "gamble",
            "quantity": "10.0",
            "avg_cost": "890.00",
            "first_buy_date": "2025-01-20",
            "buy_reason": "AI compute play",
        })
        holding_id = create_response.json()["id"]

        client.post(f"/api/holdings/{holding_id}/transactions", json={
            "holding_id": holding_id,
            "action": "sell",
            "quantity": "10.0",
            "price": "950.00",
            "reason": "Taking profits",
            "transaction_date": "2025-01-24T10:30:00",
        })

        holding = client.get(f"/api/holdings/{holding_id}").json()
        assert holding["status"] == "closed"
        assert holding["quantity"] == "0.0000"

    def test_list_transactions(self, client):
        """Test listing transactions for a holding."""
        create_response = client.post("/api/holdings", json={
            "symbol": "NVDA",
            "market": "US",
            "tier": "gamble",
            "quantity": "10.0",
            "avg_cost": "890.00",
            "first_buy_date": "2025-01-20",
            "buy_reason": "AI compute play",
        })
        holding_id = create_response.json()["id"]

        client.post(f"/api/holdings/{holding_id}/transactions", json={
            "holding_id": holding_id,
            "action": "buy",
            "quantity": "5.0",
            "price": "920.00",
            "reason": "Adding",
            "transaction_date": "2025-01-24T10:30:00",
        })

        response = client.get(f"/api/holdings/{holding_id}/transactions")
        assert response.status_code == 200
        assert len(response.json()) == 1
