"""Database connection and session management."""
import logging

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from src.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


settings = get_settings()
engine = create_engine(settings.database_url, echo=settings.debug)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_column_if_not_exists(engine, table: str, column: str, column_def: str):
    """Add a column to a table if it doesn't already exist."""
    insp = inspect(engine)
    try:
        columns = [c["name"] for c in insp.get_columns(table)]
    except Exception:
        return  # Table doesn't exist yet
    if column not in columns:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {column_def}"))
            conn.execute(text(f"CREATE INDEX `ix_{table}_{column}` ON `{table}`(`{column}`)"))
        logger.info(f"Added column {column} to {table}")


def _migrate_user_columns():
    """Add user_id columns to existing tables if they don't exist."""
    for table in ["holdings", "watchlist", "signals", "generated_report"]:
        _add_column_if_not_exists(engine, table, "user_id", "INT NULL")

    # Drop old unique constraint on watchlist and add new one with user_id
    insp = inspect(engine)
    try:
        constraints = insp.get_unique_constraints("watchlist")
        old_constraint = [c for c in constraints if c["name"] == "uq_watchlist_symbol_market"]
        if old_constraint:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE `watchlist` DROP INDEX `uq_watchlist_symbol_market`"))
                logger.info("Dropped old watchlist unique constraint")
    except Exception:
        pass


def _migrate_tier_rename():
    """Rename tier values: stable→core, medium→growth."""
    insp = inspect(engine)
    try:
        columns = {c["name"]: c for c in insp.get_columns("holdings")}
    except Exception:
        return  # Table doesn't exist yet

    if "tier" not in columns:
        return

    # SQLAlchemy Enum(PythonEnum) uses enum member NAMES (uppercase) as DB values.
    # Old enum names: STABLE, MEDIUM, GAMBLE → new: CORE, GROWTH, GAMBLE
    with engine.begin() as conn:
        # Check if old values exist (case-insensitive in MySQL)
        result = conn.execute(text(
            "SELECT COUNT(*) FROM holdings WHERE tier IN ('STABLE', 'MEDIUM', 'stable', 'medium')"
        ))
        count = result.scalar()
        if count > 0:
            # Use VARCHAR as intermediate to avoid MySQL ENUM duplicate-value errors
            conn.execute(text(
                "ALTER TABLE holdings MODIFY COLUMN tier VARCHAR(20) NOT NULL"
            ))
            conn.execute(text("UPDATE holdings SET tier='CORE' WHERE tier IN ('STABLE','stable')"))
            conn.execute(text("UPDATE holdings SET tier='GROWTH' WHERE tier IN ('MEDIUM','medium')"))
            conn.execute(text("UPDATE holdings SET tier='GAMBLE' WHERE tier IN ('GAMBLE','gamble')"))
            logger.info("Migrated tier values: STABLE→CORE, MEDIUM→GROWTH (%d rows)", count)

        # Finalize enum to new values
        conn.execute(text(
            "ALTER TABLE holdings MODIFY COLUMN tier ENUM('CORE','GROWTH','GAMBLE') NOT NULL"
        ))
        logger.info("Updated tier enum column definition")


def init_db():
    """Create all tables and run migrations."""
    # Import all model modules so they register with Base.metadata
    import src.db.models  # noqa: F401
    import src.db.models_market_data  # noqa: F401
    import src.db.models_insider  # noqa: F401
    import src.db.models_institutional  # noqa: F401
    import src.db.models_auth  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Run migrations for existing tables
    _migrate_user_columns()
    _migrate_tier_rename()
