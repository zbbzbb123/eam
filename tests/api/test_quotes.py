"""Tests for Quotes API."""
import pytest
from datetime import date
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base, get_db
from src.api.quotes import router as quotes_router
from src.collectors.base import QuoteData


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
    test_app.include_router(quotes_router, prefix="/api")
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


class TestQuotesAPI:
    """Tests for Quotes API."""

    @pytest.fixture
    def mock_quote(self):
        return QuoteData(
            symbol="NVDA",
            trade_date=date(2025, 1, 24),
            open=920.0,
            high=935.0,
            low=915.0,
            close=930.0,
            volume=50000000,
        )

    def test_get_latest_quote_us(self, client, mock_quote):
        """Test getting latest US stock quote."""
        with patch(
            "src.api.quotes.YFinanceCollector.fetch_latest_quote"
        ) as mock_fn:
            mock_fn.return_value = mock_quote

            response = client.get("/api/quotes/latest/NVDA?market=US")

            assert response.status_code == 200
            data = response.json()
            assert data["symbol"] == "NVDA"
            assert float(data["close"]) == 930.0

    def test_get_latest_quote_not_found(self, client):
        """Test 404 when quote not found."""
        with patch(
            "src.api.quotes.YFinanceCollector.fetch_latest_quote"
        ) as mock_fn:
            mock_fn.return_value = None

            response = client.get("/api/quotes/latest/INVALID?market=US")

            assert response.status_code == 404

    def test_get_quote_history(self, client, mock_quote):
        """Test getting quote history."""
        with patch(
            "src.api.quotes.YFinanceCollector.fetch_quotes"
        ) as mock_fn:
            mock_fn.return_value = [mock_quote]

            response = client.get(
                "/api/quotes/history/NVDA?market=US&start_date=2025-01-20&end_date=2025-01-24"
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["symbol"] == "NVDA"

    def test_sync_quotes(self, client, mock_quote):
        """Test syncing quotes to database."""
        with patch(
            "src.api.quotes.YFinanceCollector.fetch_quotes"
        ) as mock_fn:
            mock_fn.return_value = [mock_quote]

            response = client.post(
                "/api/quotes/sync/NVDA?market=US&start_date=2025-01-20&end_date=2025-01-24"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["synced"] == 1
            assert data["total"] == 1

    def test_sync_quotes_deduplication(self, client, mock_quote):
        """Test that syncing twice does not create duplicate records."""
        with patch(
            "src.api.quotes.YFinanceCollector.fetch_quotes"
        ) as mock_fn:
            mock_fn.return_value = [mock_quote]

            # First sync - should insert 1 record
            response1 = client.post(
                "/api/quotes/sync/NVDA?market=US&start_date=2025-01-20&end_date=2025-01-24"
            )
            assert response1.status_code == 200
            data1 = response1.json()
            assert data1["synced"] == 1
            assert data1["total"] == 1

            # Second sync - should report 0 new records (deduplication)
            response2 = client.post(
                "/api/quotes/sync/NVDA?market=US&start_date=2025-01-20&end_date=2025-01-24"
            )
            assert response2.status_code == 200
            data2 = response2.json()
            assert data2["synced"] == 0
            assert data2["total"] == 1

    def test_get_latest_quote_cn_market(self, client):
        """Test getting latest quote for CN market using AkShareCollector."""
        mock_cn_quote = QuoteData(
            symbol="600519",
            trade_date=date(2025, 1, 24),
            open=1800.0,
            high=1850.0,
            low=1790.0,
            close=1820.0,
            volume=10000000,
        )
        with patch(
            "src.api.quotes.AkShareCollector.fetch_latest_quote"
        ) as mock_fn:
            mock_fn.return_value = mock_cn_quote

            response = client.get("/api/quotes/latest/600519?market=CN")

            assert response.status_code == 200
            data = response.json()
            assert data["symbol"] == "600519"
            assert data["market"] == "CN"
            assert float(data["close"]) == 1820.0
            mock_fn.assert_called_once_with("600519", "CN")
