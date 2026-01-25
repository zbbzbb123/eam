"""Integration tests for database models using in-memory SQLite."""
import pytest
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from src.db.database import Base
from src.db.models import (
    Holding, Transaction, DailyQuote,
    Market, Tier, HoldingStatus, TransactionAction
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestDatabaseIntegration:
    """Integration tests for database operations."""

    def test_holding_persistence(self, db_session):
        """Test that a Holding can be persisted and queried."""
        holding = Holding(
            symbol="AAPL",
            market=Market.US,
            tier=Tier.STABLE,
            quantity=Decimal("100.0"),
            avg_cost=Decimal("175.50"),
            first_buy_date=date(2025, 1, 15),
            buy_reason="Long-term investment in Apple",
        )

        db_session.add(holding)
        db_session.commit()

        # Query the holding back
        queried = db_session.query(Holding).filter_by(symbol="AAPL").first()

        assert queried is not None
        assert queried.symbol == "AAPL"
        assert queried.market == Market.US
        assert queried.tier == Tier.STABLE
        assert queried.quantity == Decimal("100.0")
        assert queried.status == HoldingStatus.ACTIVE

    def test_transaction_relationship(self, db_session):
        """Test that Transaction relates properly to Holding."""
        holding = Holding(
            symbol="GOOGL",
            market=Market.US,
            tier=Tier.MEDIUM,
            quantity=Decimal("50.0"),
            avg_cost=Decimal("140.00"),
            first_buy_date=date(2025, 1, 10),
            buy_reason="Alphabet growth play",
        )
        db_session.add(holding)
        db_session.commit()

        transaction = Transaction(
            holding_id=holding.id,
            action=TransactionAction.BUY,
            quantity=Decimal("50.0"),
            price=Decimal("140.00"),
            total_amount=Decimal("7000.00"),
            reason="Initial purchase",
            transaction_date=datetime(2025, 1, 10, 14, 30, 0),
        )
        db_session.add(transaction)
        db_session.commit()

        # Query and verify relationship
        queried_holding = db_session.query(Holding).filter_by(symbol="GOOGL").first()
        assert len(queried_holding.transactions) == 1
        assert queried_holding.transactions[0].action == TransactionAction.BUY

    def test_daily_quote_unique_constraint(self, db_session):
        """Test that DailyQuote enforces unique constraint on (symbol, market, trade_date)."""
        # Note: Explicitly providing id because SQLite's AUTOINCREMENT only works
        # with INTEGER PRIMARY KEY, not BIGINT. In production (MySQL), autoincrement works.
        quote1 = DailyQuote(
            id=1,
            symbol="MSFT",
            market=Market.US,
            trade_date=date(2025, 1, 24),
            open=Decimal("420.00"),
            high=Decimal("425.00"),
            low=Decimal("418.00"),
            close=Decimal("423.00"),
            volume=25000000,
        )
        db_session.add(quote1)
        db_session.commit()

        # Try to insert a duplicate (same symbol, market, trade_date)
        quote2 = DailyQuote(
            id=2,
            symbol="MSFT",
            market=Market.US,
            trade_date=date(2025, 1, 24),
            open=Decimal("421.00"),
            high=Decimal("426.00"),
            low=Decimal("419.00"),
            close=Decimal("424.00"),
            volume=26000000,
        )
        db_session.add(quote2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_cascade_delete(self, db_session):
        """Test that deleting a Holding cascades to its Transactions."""
        holding = Holding(
            symbol="TSLA",
            market=Market.US,
            tier=Tier.GAMBLE,
            quantity=Decimal("20.0"),
            avg_cost=Decimal("250.00"),
            first_buy_date=date(2025, 1, 20),
            buy_reason="EV and AI play",
        )
        db_session.add(holding)
        db_session.commit()

        transaction = Transaction(
            holding_id=holding.id,
            action=TransactionAction.BUY,
            quantity=Decimal("20.0"),
            price=Decimal("250.00"),
            total_amount=Decimal("5000.00"),
            reason="Initial position",
            transaction_date=datetime(2025, 1, 20, 9, 30, 0),
        )
        db_session.add(transaction)
        db_session.commit()

        # Verify transaction exists
        assert db_session.query(Transaction).count() == 1

        # Delete the holding
        db_session.delete(holding)
        db_session.commit()

        # Verify transaction was cascaded
        assert db_session.query(Transaction).count() == 0
