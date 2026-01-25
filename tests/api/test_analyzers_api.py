"""Tests for Analyzers API."""
import pytest
from unittest.mock import patch, MagicMock

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


class TestAnalyzersAPI:
    """Tests for Analyzers API."""

    def test_list_analyzers(self, client):
        """Test listing available analyzers."""
        response = client.get("/api/analyzers")

        assert response.status_code == 200
        data = response.json()
        assert "analyzers" in data
        assert len(data["analyzers"]) > 0

    def test_run_specific_analyzer(self, client):
        """Test running a specific analyzer."""
        with patch('src.api.analyzers.PreciousMetalsAnalyzer') as MockAnalyzer:
            mock_instance = MagicMock()
            mock_instance.analyze.return_value = []
            mock_instance.name = "precious_metals_analyzer"
            mock_instance.sector = "precious_metals"
            MockAnalyzer.return_value = mock_instance

            response = client.post("/api/analyzers/precious_metals/run")

            assert response.status_code == 200
            data = response.json()
            assert "signals_created" in data

    def test_run_invalid_analyzer(self, client):
        """Test running non-existent analyzer."""
        response = client.post("/api/analyzers/invalid_analyzer/run")

        assert response.status_code == 404

    def test_run_all_analyzers(self, client):
        """Test running all analyzers."""
        response = client.post("/api/analyzers/run-all")

        assert response.status_code == 200
        data = response.json()
        assert "total_signals" in data
