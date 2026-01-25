"""Integration tests for database models using in-memory SQLite."""
import pytest
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from src.db.database import Base
from src.db.models import (
    Holding, Transaction, DailyQuote, Signal,
    Market, Tier, HoldingStatus, TransactionAction,
    SignalType, SignalSeverity, SignalStatus
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


@pytest.fixture
def db_session_with_fk():
    """Create an in-memory SQLite database session with foreign key enforcement."""
    engine = create_engine("sqlite:///:memory:", echo=False)

    # Enable foreign key constraints for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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

    def test_signal_persistence(self, db_session):
        """Test that a Signal can be persisted and queried."""
        signal = Signal(
            signal_type=SignalType.SECTOR,
            sector="tech",
            title="AI Capex Surge",
            description="Mag 7 capex increased 25% QoQ",
            severity=SignalSeverity.INFO,
            source="earnings_reports",
            data={"capex_growth": 0.25, "companies": ["NVDA", "MSFT"]},
            related_symbols=["NVDA", "MSFT", "GOOGL"],
        )

        db_session.add(signal)
        db_session.commit()

        # Query the signal back
        queried = db_session.query(Signal).filter_by(title="AI Capex Surge").first()

        assert queried is not None
        assert queried.signal_type == SignalType.SECTOR
        assert queried.sector == "tech"
        assert queried.severity == SignalSeverity.INFO
        assert queried.status == SignalStatus.ACTIVE
        assert queried.source == "earnings_reports"
        assert queried.data == {"capex_growth": 0.25, "companies": ["NVDA", "MSFT"]}
        assert queried.related_symbols == ["NVDA", "MSFT", "GOOGL"]
        assert queried.telegram_sent is False
        assert queried.telegram_sent_at is None

    def test_signal_holding_foreign_key(self, db_session):
        """Test that Signal can reference a Holding via foreign key."""
        # Create a holding first
        holding = Holding(
            symbol="NVDA",
            market=Market.US,
            tier=Tier.GAMBLE,
            quantity=Decimal("10.0"),
            avg_cost=Decimal("890.00"),
            first_buy_date=date(2025, 1, 20),
            buy_reason="AI compute play",
        )
        db_session.add(holding)
        db_session.commit()

        # Create a signal referencing the holding
        signal = Signal(
            signal_type=SignalType.HOLDING,
            title="NVDA earnings beat",
            description="NVIDIA beat earnings expectations",
            severity=SignalSeverity.HIGH,
            source="earnings_monitor",
            holding_id=holding.id,
            related_symbols=["NVDA"],
        )
        db_session.add(signal)
        db_session.commit()

        # Query and verify the foreign key relationship
        queried = db_session.query(Signal).filter_by(holding_id=holding.id).first()
        assert queried is not None
        assert queried.holding_id == holding.id
        assert queried.signal_type == SignalType.HOLDING

    def test_signal_invalid_holding_foreign_key(self, db_session_with_fk):
        """Test that Signal with invalid holding_id raises IntegrityError.

        Note: Uses db_session_with_fk fixture because SQLite requires explicit
        PRAGMA foreign_keys=ON to enforce foreign key constraints.
        """
        signal = Signal(
            signal_type=SignalType.HOLDING,
            title="Invalid holding reference",
            description="This signal references a non-existent holding",
            severity=SignalSeverity.MEDIUM,
            source="test",
            holding_id=99999,  # Non-existent holding
        )
        db_session_with_fk.add(signal)

        with pytest.raises(IntegrityError):
            db_session_with_fk.commit()

    def test_signal_without_holding(self, db_session):
        """Test that Signal can be created without a holding reference."""
        signal = Signal(
            signal_type=SignalType.MACRO,
            title="Fed rate decision",
            description="Federal Reserve keeps rates unchanged",
            severity=SignalSeverity.HIGH,
            source="fed_watch",
        )

        db_session.add(signal)
        db_session.commit()

        queried = db_session.query(Signal).filter_by(title="Fed rate decision").first()
        assert queried is not None
        assert queried.holding_id is None
