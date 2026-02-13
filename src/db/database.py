"""Database connection and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from src.config import get_settings


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


def init_db():
    """Create all tables."""
    # Import all model modules so they register with Base.metadata
    import src.db.models  # noqa: F401
    import src.db.models_market_data  # noqa: F401
    import src.db.models_insider  # noqa: F401
    import src.db.models_institutional  # noqa: F401
    Base.metadata.create_all(bind=engine)
