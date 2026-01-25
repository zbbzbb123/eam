"""Tests for Signals API."""
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.main import app
from src.db.database import Base, get_db


SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing with in-memory SQLite."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


class TestSignalsAPI:
    """Tests for Signals API."""

    def test_create_signal(self, client):
        """Test creating a new signal."""
        response = client.post("/api/signals", json={
            "signal_type": "sector",
            "sector": "tech",
            "title": "AI Capex Surge",
            "description": "Mag 7 capex increased 25% QoQ",
            "severity": "medium",
            "source": "earnings_analyzer",
            "data": {"capex_growth": 0.25},
            "related_symbols": ["NVDA", "MSFT"],
        })

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "AI Capex Surge"
        assert data["status"] == "active"
        assert data["telegram_sent"] is False

    def test_list_signals(self, client):
        """Test listing signals."""
        # Create two signals
        client.post("/api/signals", json={
            "signal_type": "sector",
            "title": "Signal 1",
            "description": "Description 1",
            "severity": "low",
            "source": "test",
        })
        client.post("/api/signals", json={
            "signal_type": "macro",
            "title": "Signal 2",
            "description": "Description 2",
            "severity": "high",
            "source": "test",
        })

        response = client.get("/api/signals")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_signals_filter_by_type(self, client):
        """Test filtering signals by type."""
        client.post("/api/signals", json={
            "signal_type": "sector",
            "title": "Sector Signal",
            "description": "Description",
            "severity": "low",
            "source": "test",
        })
        client.post("/api/signals", json={
            "signal_type": "macro",
            "title": "Macro Signal",
            "description": "Description",
            "severity": "low",
            "source": "test",
        })

        response = client.get("/api/signals?signal_type=sector")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["signal_type"] == "sector"

    def test_list_signals_filter_by_severity(self, client):
        """Test filtering signals by severity."""
        client.post("/api/signals", json={
            "signal_type": "sector",
            "title": "Low Signal",
            "description": "Description",
            "severity": "low",
            "source": "test",
        })
        client.post("/api/signals", json={
            "signal_type": "sector",
            "title": "High Signal",
            "description": "Description",
            "severity": "high",
            "source": "test",
        })

        response = client.get("/api/signals?min_severity=high")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["severity"] == "high"

    def test_update_signal_status(self, client):
        """Test updating signal status."""
        create_response = client.post("/api/signals", json={
            "signal_type": "sector",
            "title": "Test Signal",
            "description": "Description",
            "severity": "low",
            "source": "test",
        })
        signal_id = create_response.json()["id"]

        response = client.patch(f"/api/signals/{signal_id}", json={
            "status": "read",
        })

        assert response.status_code == 200
        assert response.json()["status"] == "read"

    def test_get_signal_not_found(self, client):
        """Test 404 for non-existent signal."""
        response = client.get("/api/signals/999")
        assert response.status_code == 404

    def test_get_signal(self, client):
        """Test getting a specific signal."""
        create_response = client.post("/api/signals", json={
            "signal_type": "sector",
            "title": "Test Signal",
            "description": "Description",
            "severity": "low",
            "source": "test",
        })
        signal_id = create_response.json()["id"]

        response = client.get(f"/api/signals/{signal_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Test Signal"

    def test_delete_signal(self, client):
        """Test deleting a signal."""
        create_response = client.post("/api/signals", json={
            "signal_type": "sector",
            "title": "Test Signal",
            "description": "Description",
            "severity": "low",
            "source": "test",
        })
        signal_id = create_response.json()["id"]

        delete_response = client.delete(f"/api/signals/{signal_id}")
        assert delete_response.status_code == 204

        get_response = client.get(f"/api/signals/{signal_id}")
        assert get_response.status_code == 404

    def test_mark_signal_read(self, client):
        """Test marking a signal as read."""
        create_response = client.post("/api/signals", json={
            "signal_type": "sector",
            "title": "Test Signal",
            "description": "Description",
            "severity": "low",
            "source": "test",
        })
        signal_id = create_response.json()["id"]

        response = client.post(f"/api/signals/{signal_id}/mark-read")
        assert response.status_code == 200
        assert response.json()["status"] == "read"
