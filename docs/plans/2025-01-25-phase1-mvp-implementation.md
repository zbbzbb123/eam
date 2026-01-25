# EAM Phase 1 MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the foundational MVP with project structure, database setup, holdings CRUD, basic quote collection, and simple dashboard.

**Architecture:** Python FastAPI backend with SQLAlchemy ORM for MySQL, separate collectors for market data. Vue 3 frontend with Vite for the dashboard. Docker Compose for local development.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Pydantic, AkShare, yfinance, Vue 3, Vite, MySQL 8.0, Docker

---

## Prerequisites

Before starting, ensure you have installed:
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Git

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `.env.example`
- Create: `.gitignore`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "eam"
version = "0.1.0"
description = "Easy Asset Management - Personal Investment Decision System"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "sqlalchemy>=2.0.0",
    "pymysql>=1.1.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "python-dotenv>=1.0.0",
    "akshare>=1.12.0",
    "yfinance>=0.2.36",
    "apscheduler>=3.10.0",
    "httpx>=0.26.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "httpx>=0.26.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 2: Create src/__init__.py**

```python
"""EAM - Easy Asset Management"""
```

**Step 3: Create src/config.py**

```python
"""Application configuration."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "mysql+pymysql://root:password@localhost:3306/eam"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # External APIs (optional for MVP)
    tushare_token: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

**Step 4: Create .env.example**

```bash
# Database
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/eam

# API Server
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=true

# External APIs (optional)
TUSHARE_TOKEN=
```

**Step 5: Create .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
ENV/
.eggs/
*.egg-info/
dist/
build/

# Environment
.env
.env.local

# IDE
.idea/
.vscode/
*.swp
*.swo

# Testing
.pytest_cache/
.coverage
htmlcov/

# Docker
docker-compose.override.yml

# OS
.DS_Store
Thumbs.db

# Node (frontend)
node_modules/
web/dist/
```

**Step 6: Create directory structure**

Run:
```bash
mkdir -p src/{api,db,collectors,analyzers,output,utils}
mkdir -p tests/{api,db,collectors}
mkdir -p web/src/{views,components,api}
touch src/api/__init__.py src/db/__init__.py src/collectors/__init__.py
touch src/analyzers/__init__.py src/output/__init__.py src/utils/__init__.py
```

**Step 7: Commit**

```bash
git add -A
git commit -m "chore: initialize project structure with pyproject.toml and config"
```

---

## Task 2: Docker Compose Setup

**Files:**
- Create: `docker-compose.yml`
- Create: `Dockerfile`

**Step 1: Create docker-compose.yml**

```yaml
version: '3.8'

services:
  mysql:
    image: mysql:8.0
    container_name: eam-mysql
    environment:
      MYSQL_ROOT_PASSWORD: password
      MYSQL_DATABASE: eam
      MYSQL_CHARSET: utf8mb4
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build: .
    container_name: eam-api
    environment:
      - DATABASE_URL=mysql+pymysql://root:password@mysql:3306/eam
      - DEBUG=true
    ports:
      - "8000:8000"
    volumes:
      - ./src:/app/src
      - ./tests:/app/tests
    depends_on:
      mysql:
        condition: service_healthy
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  mysql_data:
```

**Step 2: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir .

# Expose port
EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 3: Commit**

```bash
git add docker-compose.yml Dockerfile
git commit -m "chore: add Docker Compose setup for MySQL and API"
```

---

## Task 3: Database Models - Holdings

**Files:**
- Create: `src/db/models.py`
- Create: `src/db/database.py`
- Create: `tests/db/__init__.py`
- Create: `tests/db/test_models.py`

**Step 1: Create src/db/database.py**

```python
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
    Base.metadata.create_all(bind=engine)
```

**Step 2: Create src/db/models.py**

```python
"""SQLAlchemy models for EAM."""
from datetime import datetime, date
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import (
    String, Text, Enum, DECIMAL, Integer, BigInteger,
    DateTime, Date, Boolean, JSON, ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.db.database import Base


class Market(PyEnum):
    """Stock market enum."""
    US = "US"
    HK = "HK"
    CN = "CN"


class Tier(PyEnum):
    """Portfolio tier enum."""
    STABLE = "stable"
    MEDIUM = "medium"
    GAMBLE = "gamble"


class HoldingStatus(PyEnum):
    """Holding status enum."""
    ACTIVE = "active"
    CLOSED = "closed"


class Holding(Base):
    """Holdings table - tracks current positions."""
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    market: Mapped[Market] = mapped_column(Enum(Market), nullable=False)
    tier: Mapped[Tier] = mapped_column(Enum(Tier), nullable=False, index=True)

    quantity: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)
    avg_cost: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)

    first_buy_date: Mapped[date] = mapped_column(Date, nullable=False)
    buy_reason: Mapped[str] = mapped_column(Text, nullable=False)

    stop_loss_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)
    take_profit_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)

    custom_keywords: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[HoldingStatus] = mapped_column(
        Enum(HoldingStatus), default=HoldingStatus.ACTIVE, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction", back_populates="holding", cascade="all, delete-orphan"
    )


class TransactionAction(PyEnum):
    """Transaction action enum."""
    BUY = "buy"
    SELL = "sell"


class Transaction(Base):
    """Transaction history table."""
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    holding_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("holdings.id"), nullable=False, index=True
    )

    action: Mapped[TransactionAction] = mapped_column(Enum(TransactionAction), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)
    price: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)

    reason: Mapped[str] = mapped_column(Text, nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relationships
    holding: Mapped["Holding"] = relationship("Holding", back_populates="transactions")


class DailyQuote(Base):
    """Daily stock quotes table."""
    __tablename__ = "daily_quotes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    market: Mapped[Market] = mapped_column(Enum(Market), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    open: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)
    high: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)
    low: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)
    close: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 4), nullable=True)
    volume: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        # Unique constraint on symbol + market + trade_date
        {"mysql_charset": "utf8mb4"},
    )
```

**Step 3: Create tests/db/__init__.py**

```python
"""Database tests."""
```

**Step 4: Write test for models - tests/db/test_models.py**

```python
"""Tests for database models."""
import pytest
from datetime import date, datetime
from decimal import Decimal

from src.db.models import (
    Holding, Transaction, DailyQuote,
    Market, Tier, HoldingStatus, TransactionAction
)


class TestHoldingModel:
    """Tests for Holding model."""

    def test_holding_creation(self):
        """Test creating a Holding instance."""
        holding = Holding(
            symbol="NVDA",
            market=Market.US,
            tier=Tier.GAMBLE,
            quantity=Decimal("10.0"),
            avg_cost=Decimal("890.00"),
            first_buy_date=date(2025, 1, 20),
            buy_reason="AI compute play before earnings",
            stop_loss_price=Decimal("800.00"),
            take_profit_price=Decimal("1050.00"),
        )

        assert holding.symbol == "NVDA"
        assert holding.market == Market.US
        assert holding.tier == Tier.GAMBLE
        assert holding.quantity == Decimal("10.0")
        assert holding.avg_cost == Decimal("890.00")
        assert holding.buy_reason == "AI compute play before earnings"

    def test_holding_default_status(self):
        """Test that holding defaults to active status."""
        holding = Holding(
            symbol="VOO",
            market=Market.US,
            tier=Tier.STABLE,
            quantity=Decimal("50.0"),
            avg_cost=Decimal("450.00"),
            first_buy_date=date(2025, 1, 1),
            buy_reason="Core S&P 500 holding",
        )

        assert holding.status == HoldingStatus.ACTIVE


class TestTransactionModel:
    """Tests for Transaction model."""

    def test_transaction_creation(self):
        """Test creating a Transaction instance."""
        transaction = Transaction(
            holding_id=1,
            action=TransactionAction.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("890.00"),
            total_amount=Decimal("8900.00"),
            reason="Initial position",
            transaction_date=datetime(2025, 1, 20, 10, 30, 0),
        )

        assert transaction.action == TransactionAction.BUY
        assert transaction.quantity == Decimal("10.0")
        assert transaction.total_amount == Decimal("8900.00")


class TestDailyQuoteModel:
    """Tests for DailyQuote model."""

    def test_daily_quote_creation(self):
        """Test creating a DailyQuote instance."""
        quote = DailyQuote(
            symbol="NVDA",
            market=Market.US,
            trade_date=date(2025, 1, 24),
            open=Decimal("920.00"),
            high=Decimal("935.00"),
            low=Decimal("915.00"),
            close=Decimal("930.00"),
            volume=50000000,
        )

        assert quote.symbol == "NVDA"
        assert quote.close == Decimal("930.00")
        assert quote.volume == 50000000
```

**Step 5: Run tests to verify they pass**

Run:
```bash
pip install -e ".[dev]"
pytest tests/db/test_models.py -v
```

Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add src/db/ tests/db/
git commit -m "feat: add database models for holdings, transactions, and quotes"
```

---

## Task 4: Pydantic Schemas

**Files:**
- Create: `src/api/schemas.py`
- Create: `tests/api/__init__.py`
- Create: `tests/api/test_schemas.py`

**Step 1: Create src/api/schemas.py**

```python
"""Pydantic schemas for API request/response validation."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


class MarketEnum(str, Enum):
    """Stock market enum."""
    US = "US"
    HK = "HK"
    CN = "CN"


class TierEnum(str, Enum):
    """Portfolio tier enum."""
    STABLE = "stable"
    MEDIUM = "medium"
    GAMBLE = "gamble"


class HoldingStatusEnum(str, Enum):
    """Holding status enum."""
    ACTIVE = "active"
    CLOSED = "closed"


class TransactionActionEnum(str, Enum):
    """Transaction action enum."""
    BUY = "buy"
    SELL = "sell"


# ===== Holding Schemas =====

class HoldingBase(BaseModel):
    """Base schema for Holding."""
    symbol: str = Field(..., min_length=1, max_length=20)
    market: MarketEnum
    tier: TierEnum
    quantity: Decimal = Field(..., gt=0)
    avg_cost: Decimal = Field(..., gt=0)
    first_buy_date: date
    buy_reason: str = Field(..., min_length=1)
    stop_loss_price: Optional[Decimal] = Field(None, gt=0)
    take_profit_price: Optional[Decimal] = Field(None, gt=0)
    custom_keywords: Optional[List[str]] = None
    notes: Optional[str] = None


class HoldingCreate(HoldingBase):
    """Schema for creating a new holding."""
    pass


class HoldingUpdate(BaseModel):
    """Schema for updating a holding."""
    quantity: Optional[Decimal] = Field(None, gt=0)
    avg_cost: Optional[Decimal] = Field(None, gt=0)
    stop_loss_price: Optional[Decimal] = Field(None, gt=0)
    take_profit_price: Optional[Decimal] = Field(None, gt=0)
    custom_keywords: Optional[List[str]] = None
    notes: Optional[str] = None
    status: Optional[HoldingStatusEnum] = None


class HoldingResponse(HoldingBase):
    """Schema for holding response."""
    id: int
    status: HoldingStatusEnum
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===== Transaction Schemas =====

class TransactionBase(BaseModel):
    """Base schema for Transaction."""
    action: TransactionActionEnum
    quantity: Decimal = Field(..., gt=0)
    price: Decimal = Field(..., gt=0)
    reason: str = Field(..., min_length=1)
    transaction_date: datetime


class TransactionCreate(TransactionBase):
    """Schema for creating a new transaction."""
    holding_id: int


class TransactionResponse(TransactionBase):
    """Schema for transaction response."""
    id: int
    holding_id: int
    total_amount: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===== Daily Quote Schemas =====

class DailyQuoteResponse(BaseModel):
    """Schema for daily quote response."""
    symbol: str
    market: MarketEnum
    trade_date: date
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Optional[Decimal] = None
    volume: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# ===== Portfolio Overview Schemas =====

class TierAllocation(BaseModel):
    """Schema for tier allocation."""
    tier: TierEnum
    target_pct: Decimal
    actual_pct: Decimal
    drift_pct: Decimal
    market_value: Decimal


class PortfolioOverview(BaseModel):
    """Schema for portfolio overview."""
    total_value: Decimal
    allocations: List[TierAllocation]
    holdings_count: int
```

**Step 2: Create tests/api/__init__.py**

```python
"""API tests."""
```

**Step 3: Write test for schemas - tests/api/test_schemas.py**

```python
"""Tests for API schemas."""
import pytest
from datetime import date, datetime
from decimal import Decimal

from pydantic import ValidationError

from src.api.schemas import (
    HoldingCreate, HoldingUpdate, HoldingResponse,
    TransactionCreate, MarketEnum, TierEnum, TransactionActionEnum
)


class TestHoldingSchemas:
    """Tests for Holding schemas."""

    def test_holding_create_valid(self):
        """Test creating a valid HoldingCreate."""
        holding = HoldingCreate(
            symbol="NVDA",
            market=MarketEnum.US,
            tier=TierEnum.GAMBLE,
            quantity=Decimal("10.0"),
            avg_cost=Decimal("890.00"),
            first_buy_date=date(2025, 1, 20),
            buy_reason="AI compute play",
        )

        assert holding.symbol == "NVDA"
        assert holding.market == MarketEnum.US

    def test_holding_create_invalid_quantity(self):
        """Test that negative quantity is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            HoldingCreate(
                symbol="NVDA",
                market=MarketEnum.US,
                tier=TierEnum.GAMBLE,
                quantity=Decimal("-10.0"),
                avg_cost=Decimal("890.00"),
                first_buy_date=date(2025, 1, 20),
                buy_reason="AI compute play",
            )

        assert "greater than 0" in str(exc_info.value)

    def test_holding_create_empty_reason_rejected(self):
        """Test that empty buy_reason is rejected."""
        with pytest.raises(ValidationError):
            HoldingCreate(
                symbol="NVDA",
                market=MarketEnum.US,
                tier=TierEnum.GAMBLE,
                quantity=Decimal("10.0"),
                avg_cost=Decimal("890.00"),
                first_buy_date=date(2025, 1, 20),
                buy_reason="",
            )

    def test_holding_update_partial(self):
        """Test partial update with only some fields."""
        update = HoldingUpdate(
            stop_loss_price=Decimal("800.00"),
        )

        assert update.stop_loss_price == Decimal("800.00")
        assert update.quantity is None


class TestTransactionSchemas:
    """Tests for Transaction schemas."""

    def test_transaction_create_valid(self):
        """Test creating a valid TransactionCreate."""
        transaction = TransactionCreate(
            holding_id=1,
            action=TransactionActionEnum.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("890.00"),
            reason="Initial position",
            transaction_date=datetime(2025, 1, 20, 10, 30, 0),
        )

        assert transaction.action == TransactionActionEnum.BUY
        assert transaction.quantity == Decimal("10.0")
```

**Step 4: Run tests**

Run:
```bash
pytest tests/api/test_schemas.py -v
```

Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add src/api/schemas.py tests/api/
git commit -m "feat: add Pydantic schemas for API validation"
```

---

## Task 5: Holdings CRUD Operations

**Files:**
- Create: `src/api/holdings.py`
- Create: `tests/api/test_holdings.py`

**Step 1: Create src/api/holdings.py**

```python
"""Holdings API endpoints."""
from typing import List, Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.db.database import get_db
from src.db.models import Holding, Transaction, Market, Tier, HoldingStatus, TransactionAction
from src.api.schemas import (
    HoldingCreate, HoldingUpdate, HoldingResponse,
    TransactionCreate, TransactionResponse,
    TierEnum, MarketEnum, HoldingStatusEnum
)

router = APIRouter(prefix="/holdings", tags=["holdings"])


def _map_market(market: MarketEnum) -> Market:
    """Map API enum to DB enum."""
    return Market[market.value]


def _map_tier(tier: TierEnum) -> Tier:
    """Map API enum to DB enum."""
    return Tier[tier.value.upper()]


@router.post("", response_model=HoldingResponse, status_code=status.HTTP_201_CREATED)
def create_holding(holding: HoldingCreate, db: Session = Depends(get_db)):
    """Create a new holding."""
    db_holding = Holding(
        symbol=holding.symbol.upper(),
        market=_map_market(holding.market),
        tier=_map_tier(holding.tier),
        quantity=holding.quantity,
        avg_cost=holding.avg_cost,
        first_buy_date=holding.first_buy_date,
        buy_reason=holding.buy_reason,
        stop_loss_price=holding.stop_loss_price,
        take_profit_price=holding.take_profit_price,
        custom_keywords=holding.custom_keywords,
        notes=holding.notes,
    )
    db.add(db_holding)
    db.commit()
    db.refresh(db_holding)
    return db_holding


@router.get("", response_model=List[HoldingResponse])
def list_holdings(
    tier: Optional[TierEnum] = None,
    status: Optional[HoldingStatusEnum] = None,
    db: Session = Depends(get_db),
):
    """List all holdings with optional filters."""
    query = select(Holding)

    if tier:
        query = query.where(Holding.tier == _map_tier(tier))
    if status:
        query = query.where(Holding.status == HoldingStatus[status.value.upper()])

    query = query.order_by(Holding.tier, Holding.symbol)

    result = db.execute(query)
    return result.scalars().all()


@router.get("/{holding_id}", response_model=HoldingResponse)
def get_holding(holding_id: int, db: Session = Depends(get_db)):
    """Get a specific holding by ID."""
    holding = db.get(Holding, holding_id)
    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holding {holding_id} not found"
        )
    return holding


@router.patch("/{holding_id}", response_model=HoldingResponse)
def update_holding(
    holding_id: int,
    update: HoldingUpdate,
    db: Session = Depends(get_db),
):
    """Update a holding."""
    holding = db.get(Holding, holding_id)
    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holding {holding_id} not found"
        )

    update_data = update.model_dump(exclude_unset=True)

    # Map status enum if present
    if "status" in update_data and update_data["status"]:
        update_data["status"] = HoldingStatus[update_data["status"].value.upper()]

    for field, value in update_data.items():
        setattr(holding, field, value)

    db.commit()
    db.refresh(holding)
    return holding


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(holding_id: int, db: Session = Depends(get_db)):
    """Delete a holding."""
    holding = db.get(Holding, holding_id)
    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holding {holding_id} not found"
        )

    db.delete(holding)
    db.commit()


# ===== Transaction Endpoints =====

@router.post("/{holding_id}/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    holding_id: int,
    transaction: TransactionCreate,
    db: Session = Depends(get_db),
):
    """Create a new transaction for a holding."""
    holding = db.get(Holding, holding_id)
    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holding {holding_id} not found"
        )

    total_amount = transaction.quantity * transaction.price

    db_transaction = Transaction(
        holding_id=holding_id,
        action=TransactionAction[transaction.action.value.upper()],
        quantity=transaction.quantity,
        price=transaction.price,
        total_amount=total_amount,
        reason=transaction.reason,
        transaction_date=transaction.transaction_date,
    )

    db.add(db_transaction)

    # Update holding quantity and avg_cost
    if transaction.action.value == "buy":
        new_total_cost = (holding.quantity * holding.avg_cost) + total_amount
        holding.quantity += transaction.quantity
        holding.avg_cost = new_total_cost / holding.quantity
    else:  # sell
        holding.quantity -= transaction.quantity
        if holding.quantity <= 0:
            holding.status = HoldingStatus.CLOSED
            holding.quantity = Decimal("0")

    db.commit()
    db.refresh(db_transaction)
    return db_transaction


@router.get("/{holding_id}/transactions", response_model=List[TransactionResponse])
def list_transactions(holding_id: int, db: Session = Depends(get_db)):
    """List all transactions for a holding."""
    holding = db.get(Holding, holding_id)
    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holding {holding_id} not found"
        )

    query = select(Transaction).where(
        Transaction.holding_id == holding_id
    ).order_by(Transaction.transaction_date.desc())

    result = db.execute(query)
    return result.scalars().all()
```

**Step 2: Create tests/api/test_holdings.py**

```python
"""Tests for Holdings API."""
import pytest
from datetime import date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.main import app
from src.db.database import Base, get_db


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


@pytest.fixture(scope="function")
def client():
    """Create test client with fresh database."""
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


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
```

**Step 3: Create src/main.py for the tests to run**

```python
"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db.database import init_db
from src.api.holdings import router as holdings_router

app = FastAPI(
    title="EAM - Easy Asset Management",
    description="Personal Investment Decision System",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(holdings_router, prefix="/api")


@app.on_event("startup")
def startup():
    """Initialize database on startup."""
    init_db()


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
```

**Step 4: Run tests**

Run:
```bash
pytest tests/api/test_holdings.py -v
```

Expected: PASS (10 tests)

**Step 5: Commit**

```bash
git add src/api/holdings.py src/main.py tests/api/test_holdings.py
git commit -m "feat: add Holdings and Transactions CRUD API with tests"
```

---

## Task 6: Quote Collectors - yfinance

**Files:**
- Create: `src/collectors/base.py`
- Create: `src/collectors/structured/yfinance_collector.py`
- Create: `tests/collectors/__init__.py`
- Create: `tests/collectors/test_yfinance.py`

**Step 1: Create src/collectors/base.py**

```python
"""Base collector class."""
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date

from pydantic import BaseModel


class QuoteData(BaseModel):
    """Quote data model."""
    symbol: str
    trade_date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None


class BaseCollector(ABC):
    """Abstract base class for data collectors."""

    @abstractmethod
    def fetch_quotes(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[QuoteData]:
        """Fetch historical quotes for a symbol."""
        pass

    @abstractmethod
    def fetch_latest_quote(self, symbol: str) -> Optional[QuoteData]:
        """Fetch the latest quote for a symbol."""
        pass
```

**Step 2: Create src/collectors/structured/__init__.py**

```python
"""Structured data collectors."""
```

**Step 3: Create src/collectors/structured/yfinance_collector.py**

```python
"""Yahoo Finance collector for US stocks."""
from typing import List, Optional
from datetime import date, timedelta
import logging

import yfinance as yf

from src.collectors.base import BaseCollector, QuoteData

logger = logging.getLogger(__name__)


class YFinanceCollector(BaseCollector):
    """Collector for US stock data via Yahoo Finance."""

    def fetch_quotes(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[QuoteData]:
        """
        Fetch historical quotes for a US stock.

        Args:
            symbol: Stock symbol (e.g., "NVDA", "VOO")
            start_date: Start date for historical data
            end_date: End date for historical data

        Returns:
            List of QuoteData objects
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date + timedelta(days=1))

            if df.empty:
                logger.warning(f"No data found for {symbol}")
                return []

            quotes = []
            for idx, row in df.iterrows():
                quote = QuoteData(
                    symbol=symbol.upper(),
                    trade_date=idx.date(),
                    open=round(row["Open"], 4) if row["Open"] else None,
                    high=round(row["High"], 4) if row["High"] else None,
                    low=round(row["Low"], 4) if row["Low"] else None,
                    close=round(row["Close"], 4) if row["Close"] else None,
                    volume=int(row["Volume"]) if row["Volume"] else None,
                )
                quotes.append(quote)

            return quotes

        except Exception as e:
            logger.error(f"Error fetching quotes for {symbol}: {e}")
            raise

    def fetch_latest_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        Fetch the latest quote for a US stock.

        Args:
            symbol: Stock symbol

        Returns:
            QuoteData or None if not available
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="1d")

            if df.empty:
                return None

            row = df.iloc[-1]
            return QuoteData(
                symbol=symbol.upper(),
                trade_date=df.index[-1].date(),
                open=round(row["Open"], 4) if row["Open"] else None,
                high=round(row["High"], 4) if row["High"] else None,
                low=round(row["Low"], 4) if row["Low"] else None,
                close=round(row["Close"], 4) if row["Close"] else None,
                volume=int(row["Volume"]) if row["Volume"] else None,
            )

        except Exception as e:
            logger.error(f"Error fetching latest quote for {symbol}: {e}")
            return None

    def fetch_multiple_quotes(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date,
    ) -> dict[str, List[QuoteData]]:
        """
        Fetch historical quotes for multiple symbols.

        Args:
            symbols: List of stock symbols
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary mapping symbol to list of quotes
        """
        result = {}
        for symbol in symbols:
            try:
                quotes = self.fetch_quotes(symbol, start_date, end_date)
                result[symbol] = quotes
            except Exception as e:
                logger.error(f"Error fetching {symbol}: {e}")
                result[symbol] = []
        return result
```

**Step 4: Create tests/collectors/__init__.py**

```python
"""Collector tests."""
```

**Step 5: Write tests - tests/collectors/test_yfinance.py**

```python
"""Tests for yfinance collector."""
import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch
import pandas as pd

from src.collectors.structured.yfinance_collector import YFinanceCollector
from src.collectors.base import QuoteData


class TestYFinanceCollector:
    """Tests for YFinanceCollector."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return YFinanceCollector()

    @pytest.fixture
    def mock_history_data(self):
        """Create mock yfinance history data."""
        dates = pd.date_range(start="2025-01-20", end="2025-01-24", freq="B")
        data = {
            "Open": [880.0, 890.0, 900.0, 910.0],
            "High": [895.0, 905.0, 915.0, 925.0],
            "Low": [875.0, 885.0, 895.0, 905.0],
            "Close": [890.0, 900.0, 910.0, 920.0],
            "Volume": [1000000, 1100000, 1200000, 1300000],
        }
        return pd.DataFrame(data, index=dates[:4])

    def test_fetch_quotes_returns_quote_data(self, collector, mock_history_data):
        """Test that fetch_quotes returns QuoteData objects."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = mock_history_data

            quotes = collector.fetch_quotes(
                symbol="NVDA",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 24),
            )

            assert len(quotes) == 4
            assert all(isinstance(q, QuoteData) for q in quotes)
            assert quotes[0].symbol == "NVDA"
            assert quotes[0].close == 890.0

    def test_fetch_quotes_empty_result(self, collector):
        """Test handling of empty result."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = pd.DataFrame()

            quotes = collector.fetch_quotes(
                symbol="INVALID",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 24),
            )

            assert quotes == []

    def test_fetch_latest_quote(self, collector, mock_history_data):
        """Test fetching latest quote."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = mock_history_data.iloc[[-1]]

            quote = collector.fetch_latest_quote("NVDA")

            assert quote is not None
            assert quote.symbol == "NVDA"
            assert quote.close == 920.0

    def test_fetch_latest_quote_none_when_empty(self, collector):
        """Test that None is returned when no data."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = pd.DataFrame()

            quote = collector.fetch_latest_quote("INVALID")

            assert quote is None

    def test_fetch_multiple_quotes(self, collector, mock_history_data):
        """Test fetching quotes for multiple symbols."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = mock_history_data

            result = collector.fetch_multiple_quotes(
                symbols=["NVDA", "VOO"],
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 24),
            )

            assert "NVDA" in result
            assert "VOO" in result
            assert len(result["NVDA"]) == 4


# Integration test (skipped by default, run with: pytest -m integration)
@pytest.mark.integration
class TestYFinanceCollectorIntegration:
    """Integration tests that hit real Yahoo Finance API."""

    def test_fetch_real_quotes(self):
        """Test fetching real quotes from Yahoo Finance."""
        collector = YFinanceCollector()
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        quotes = collector.fetch_quotes("AAPL", start_date, end_date)

        assert len(quotes) > 0
        assert all(q.symbol == "AAPL" for q in quotes)
        assert all(q.close is not None for q in quotes)
```

**Step 6: Run tests**

Run:
```bash
pytest tests/collectors/test_yfinance.py -v -m "not integration"
```

Expected: PASS (5 tests)

**Step 7: Commit**

```bash
git add src/collectors/ tests/collectors/
git commit -m "feat: add yfinance collector for US stock quotes"
```

---

## Task 7: Quote Collectors - AkShare

**Files:**
- Create: `src/collectors/structured/akshare_collector.py`
- Create: `tests/collectors/test_akshare.py`

**Step 1: Create src/collectors/structured/akshare_collector.py**

```python
"""AkShare collector for A-share and HK stocks."""
from typing import List, Optional
from datetime import date
import logging

import akshare as ak

from src.collectors.base import BaseCollector, QuoteData

logger = logging.getLogger(__name__)


class AkShareCollector(BaseCollector):
    """Collector for A-share and HK stock data via AkShare."""

    def fetch_quotes(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        market: str = "CN",
    ) -> List[QuoteData]:
        """
        Fetch historical quotes for A-share or HK stock.

        Args:
            symbol: Stock symbol (e.g., "000001" for A-share, "00700" for HK)
            start_date: Start date
            end_date: End date
            market: "CN" for A-share, "HK" for Hong Kong

        Returns:
            List of QuoteData objects
        """
        try:
            if market == "CN":
                return self._fetch_cn_quotes(symbol, start_date, end_date)
            elif market == "HK":
                return self._fetch_hk_quotes(symbol, start_date, end_date)
            else:
                raise ValueError(f"Unsupported market: {market}")

        except Exception as e:
            logger.error(f"Error fetching quotes for {symbol}: {e}")
            raise

    def _fetch_cn_quotes(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[QuoteData]:
        """Fetch A-share quotes."""
        # Determine stock type by symbol prefix
        if symbol.startswith("6"):
            full_symbol = f"sh{symbol}"
        else:
            full_symbol = f"sz{symbol}"

        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust="qfq",  # 前复权
        )

        if df.empty:
            return []

        quotes = []
        for _, row in df.iterrows():
            quote = QuoteData(
                symbol=symbol,
                trade_date=row["日期"].date() if hasattr(row["日期"], "date") else row["日期"],
                open=round(float(row["开盘"]), 4),
                high=round(float(row["最高"]), 4),
                low=round(float(row["最低"]), 4),
                close=round(float(row["收盘"]), 4),
                volume=int(row["成交量"]),
            )
            quotes.append(quote)

        return quotes

    def _fetch_hk_quotes(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[QuoteData]:
        """Fetch HK stock quotes."""
        df = ak.stock_hk_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust="qfq",
        )

        if df.empty:
            return []

        quotes = []
        for _, row in df.iterrows():
            quote = QuoteData(
                symbol=symbol,
                trade_date=row["日期"].date() if hasattr(row["日期"], "date") else row["日期"],
                open=round(float(row["开盘"]), 4),
                high=round(float(row["最高"]), 4),
                low=round(float(row["最低"]), 4),
                close=round(float(row["收盘"]), 4),
                volume=int(row["成交量"]),
            )
            quotes.append(quote)

        return quotes

    def fetch_latest_quote(self, symbol: str, market: str = "CN") -> Optional[QuoteData]:
        """
        Fetch the latest quote.

        Args:
            symbol: Stock symbol
            market: "CN" or "HK"

        Returns:
            QuoteData or None
        """
        today = date.today()
        quotes = self.fetch_quotes(symbol, today, today, market)
        return quotes[-1] if quotes else None

    def fetch_northbound_flow(self, trade_date: date) -> dict:
        """
        Fetch northbound capital flow data.

        Args:
            trade_date: The trading date

        Returns:
            Dictionary with northbound flow data
        """
        try:
            df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
            if df.empty:
                return {}

            # Filter by date if possible
            return {
                "date": trade_date,
                "data": df.to_dict("records")[:10],  # Return recent records
            }
        except Exception as e:
            logger.error(f"Error fetching northbound flow: {e}")
            return {}
```

**Step 2: Write tests - tests/collectors/test_akshare.py**

```python
"""Tests for AkShare collector."""
import pytest
from datetime import date
from unittest.mock import patch, Mock
import pandas as pd

from src.collectors.structured.akshare_collector import AkShareCollector
from src.collectors.base import QuoteData


class TestAkShareCollector:
    """Tests for AkShareCollector."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return AkShareCollector()

    @pytest.fixture
    def mock_cn_data(self):
        """Create mock A-share data."""
        data = {
            "日期": pd.to_datetime(["2025-01-20", "2025-01-21", "2025-01-22"]),
            "开盘": [10.0, 10.5, 10.8],
            "最高": [10.5, 10.8, 11.0],
            "最低": [9.8, 10.2, 10.5],
            "收盘": [10.3, 10.6, 10.9],
            "成交量": [1000000, 1100000, 1200000],
        }
        return pd.DataFrame(data)

    def test_fetch_cn_quotes(self, collector, mock_cn_data):
        """Test fetching A-share quotes."""
        with patch("akshare.stock_zh_a_hist") as mock_fn:
            mock_fn.return_value = mock_cn_data

            quotes = collector.fetch_quotes(
                symbol="000001",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 22),
                market="CN",
            )

            assert len(quotes) == 3
            assert all(isinstance(q, QuoteData) for q in quotes)
            assert quotes[0].symbol == "000001"
            assert quotes[0].close == 10.3

    def test_fetch_quotes_empty_result(self, collector):
        """Test handling of empty result."""
        with patch("akshare.stock_zh_a_hist") as mock_fn:
            mock_fn.return_value = pd.DataFrame()

            quotes = collector.fetch_quotes(
                symbol="000001",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 22),
                market="CN",
            )

            assert quotes == []

    def test_fetch_hk_quotes(self, collector):
        """Test fetching HK stock quotes."""
        mock_hk_data = pd.DataFrame({
            "日期": pd.to_datetime(["2025-01-20"]),
            "开盘": [350.0],
            "最高": [360.0],
            "最低": [345.0],
            "收盘": [355.0],
            "成交量": [5000000],
        })

        with patch("akshare.stock_hk_hist") as mock_fn:
            mock_fn.return_value = mock_hk_data

            quotes = collector.fetch_quotes(
                symbol="00700",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 20),
                market="HK",
            )

            assert len(quotes) == 1
            assert quotes[0].symbol == "00700"
            assert quotes[0].close == 355.0

    def test_invalid_market_raises_error(self, collector):
        """Test that invalid market raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported market"):
            collector.fetch_quotes(
                symbol="AAPL",
                start_date=date(2025, 1, 20),
                end_date=date(2025, 1, 22),
                market="INVALID",
            )


# Integration test (skipped by default)
@pytest.mark.integration
class TestAkShareCollectorIntegration:
    """Integration tests that hit real AkShare API."""

    def test_fetch_real_cn_quotes(self):
        """Test fetching real A-share quotes."""
        collector = AkShareCollector()

        quotes = collector.fetch_quotes(
            symbol="000001",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 10),
            market="CN",
        )

        # May be empty if no trading days in range
        assert isinstance(quotes, list)
```

**Step 3: Run tests**

Run:
```bash
pytest tests/collectors/test_akshare.py -v -m "not integration"
```

Expected: PASS (4 tests)

**Step 4: Commit**

```bash
git add src/collectors/structured/akshare_collector.py tests/collectors/test_akshare.py
git commit -m "feat: add AkShare collector for A-share and HK stocks"
```

---

## Task 8: Quotes API Endpoint

**Files:**
- Create: `src/api/quotes.py`
- Modify: `src/main.py`
- Create: `tests/api/test_quotes.py`

**Step 1: Create src/api/quotes.py**

```python
"""Quotes API endpoints."""
from typing import List, Optional
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.db.database import get_db
from src.db.models import DailyQuote, Market
from src.api.schemas import DailyQuoteResponse, MarketEnum
from src.collectors.structured.yfinance_collector import YFinanceCollector
from src.collectors.structured.akshare_collector import AkShareCollector

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.get("/latest/{symbol}", response_model=Optional[DailyQuoteResponse])
def get_latest_quote(
    symbol: str,
    market: MarketEnum = Query(MarketEnum.US),
):
    """
    Get the latest quote for a symbol.
    Fetches directly from data source (not from database).
    """
    if market == MarketEnum.US:
        collector = YFinanceCollector()
        quote = collector.fetch_latest_quote(symbol)
    else:
        collector = AkShareCollector()
        quote = collector.fetch_latest_quote(symbol, market.value)

    if not quote:
        raise HTTPException(status_code=404, detail=f"No quote found for {symbol}")

    return DailyQuoteResponse(
        symbol=quote.symbol,
        market=market,
        trade_date=quote.trade_date,
        open=quote.open,
        high=quote.high,
        low=quote.low,
        close=quote.close,
        volume=quote.volume,
    )


@router.get("/history/{symbol}", response_model=List[DailyQuoteResponse])
def get_quote_history(
    symbol: str,
    market: MarketEnum = Query(MarketEnum.US),
    start_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    end_date: date = Query(default_factory=date.today),
):
    """
    Get historical quotes for a symbol.
    Fetches directly from data source.
    """
    if market == MarketEnum.US:
        collector = YFinanceCollector()
        quotes = collector.fetch_quotes(symbol, start_date, end_date)
    else:
        collector = AkShareCollector()
        quotes = collector.fetch_quotes(symbol, start_date, end_date, market.value)

    return [
        DailyQuoteResponse(
            symbol=q.symbol,
            market=market,
            trade_date=q.trade_date,
            open=q.open,
            high=q.high,
            low=q.low,
            close=q.close,
            volume=q.volume,
        )
        for q in quotes
    ]


@router.post("/sync/{symbol}")
def sync_quotes(
    symbol: str,
    market: MarketEnum = Query(MarketEnum.US),
    start_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    end_date: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
):
    """
    Sync historical quotes to database.
    Fetches from data source and stores in database.
    """
    if market == MarketEnum.US:
        collector = YFinanceCollector()
        quotes = collector.fetch_quotes(symbol, start_date, end_date)
    else:
        collector = AkShareCollector()
        quotes = collector.fetch_quotes(symbol, start_date, end_date, market.value)

    count = 0
    for q in quotes:
        # Check if quote already exists
        existing = db.execute(
            select(DailyQuote).where(
                DailyQuote.symbol == q.symbol,
                DailyQuote.market == Market[market.value],
                DailyQuote.trade_date == q.trade_date,
            )
        ).scalar_one_or_none()

        if not existing:
            db_quote = DailyQuote(
                symbol=q.symbol,
                market=Market[market.value],
                trade_date=q.trade_date,
                open=q.open,
                high=q.high,
                low=q.low,
                close=q.close,
                volume=q.volume,
            )
            db.add(db_quote)
            count += 1

    db.commit()

    return {"synced": count, "total": len(quotes)}
```

**Step 2: Update src/main.py to include quotes router**

```python
"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db.database import init_db
from src.api.holdings import router as holdings_router
from src.api.quotes import router as quotes_router

app = FastAPI(
    title="EAM - Easy Asset Management",
    description="Personal Investment Decision System",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(holdings_router, prefix="/api")
app.include_router(quotes_router, prefix="/api")


@app.on_event("startup")
def startup():
    """Initialize database on startup."""
    init_db()


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
```

**Step 3: Write tests - tests/api/test_quotes.py**

```python
"""Tests for Quotes API."""
import pytest
from datetime import date
from unittest.mock import patch, Mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.main import app
from src.db.database import Base, get_db
from src.collectors.base import QuoteData


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
            assert data["close"] == 930.0

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
```

**Step 4: Run tests**

Run:
```bash
pytest tests/api/test_quotes.py -v
```

Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add src/api/quotes.py src/main.py tests/api/test_quotes.py
git commit -m "feat: add Quotes API for fetching and syncing market data"
```

---

## Task 9: Portfolio Overview API

**Files:**
- Create: `src/api/portfolio.py`
- Modify: `src/main.py`
- Create: `tests/api/test_portfolio.py`

**Step 1: Create src/api/portfolio.py**

```python
"""Portfolio API endpoints."""
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from src.db.database import get_db
from src.db.models import Holding, Tier, HoldingStatus
from src.api.schemas import PortfolioOverview, TierAllocation, TierEnum
from src.collectors.structured.yfinance_collector import YFinanceCollector

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# Target allocations
TARGET_ALLOCATIONS = {
    Tier.STABLE: Decimal("40"),
    Tier.MEDIUM: Decimal("30"),
    Tier.GAMBLE: Decimal("30"),
}


def get_current_price(symbol: str, market: str) -> Decimal:
    """Get current price for a symbol."""
    if market == "US":
        collector = YFinanceCollector()
        quote = collector.fetch_latest_quote(symbol)
        if quote and quote.close:
            return Decimal(str(quote.close))
    # Fallback: return 0 if can't fetch price
    return Decimal("0")


@router.get("/overview", response_model=PortfolioOverview)
def get_portfolio_overview(db: Session = Depends(get_db)):
    """
    Get portfolio overview with tier allocations.
    """
    # Get all active holdings
    holdings = db.execute(
        select(Holding).where(Holding.status == HoldingStatus.ACTIVE)
    ).scalars().all()

    if not holdings:
        return PortfolioOverview(
            total_value=Decimal("0"),
            allocations=[
                TierAllocation(
                    tier=TierEnum.STABLE,
                    target_pct=TARGET_ALLOCATIONS[Tier.STABLE],
                    actual_pct=Decimal("0"),
                    drift_pct=Decimal("-40"),
                    market_value=Decimal("0"),
                ),
                TierAllocation(
                    tier=TierEnum.MEDIUM,
                    target_pct=TARGET_ALLOCATIONS[Tier.MEDIUM],
                    actual_pct=Decimal("0"),
                    drift_pct=Decimal("-30"),
                    market_value=Decimal("0"),
                ),
                TierAllocation(
                    tier=TierEnum.GAMBLE,
                    target_pct=TARGET_ALLOCATIONS[Tier.GAMBLE],
                    actual_pct=Decimal("0"),
                    drift_pct=Decimal("-30"),
                    market_value=Decimal("0"),
                ),
            ],
            holdings_count=0,
        )

    # Calculate market values by tier
    tier_values = {tier: Decimal("0") for tier in Tier}

    for holding in holdings:
        # For MVP, use avg_cost as price estimate (real implementation would fetch current price)
        market_value = holding.quantity * holding.avg_cost
        tier_values[holding.tier] += market_value

    total_value = sum(tier_values.values())

    # Calculate allocations
    allocations = []
    for tier in [Tier.STABLE, Tier.MEDIUM, Tier.GAMBLE]:
        if total_value > 0:
            actual_pct = (tier_values[tier] / total_value) * 100
        else:
            actual_pct = Decimal("0")

        target_pct = TARGET_ALLOCATIONS[tier]
        drift_pct = actual_pct - target_pct

        allocations.append(TierAllocation(
            tier=TierEnum(tier.value),
            target_pct=target_pct,
            actual_pct=round(actual_pct, 2),
            drift_pct=round(drift_pct, 2),
            market_value=round(tier_values[tier], 2),
        ))

    return PortfolioOverview(
        total_value=round(total_value, 2),
        allocations=allocations,
        holdings_count=len(holdings),
    )


@router.get("/rebalance-suggestions")
def get_rebalance_suggestions(db: Session = Depends(get_db)):
    """
    Get suggestions for rebalancing the portfolio.
    """
    overview = get_portfolio_overview(db)

    suggestions = []
    for allocation in overview.allocations:
        if abs(allocation.drift_pct) > 5:  # Only suggest if drift > 5%
            if allocation.drift_pct > 0:
                action = "reduce"
                amount = (allocation.drift_pct / 100) * overview.total_value
            else:
                action = "increase"
                amount = (abs(allocation.drift_pct) / 100) * overview.total_value

            suggestions.append({
                "tier": allocation.tier.value,
                "action": action,
                "amount": round(amount, 2),
                "drift_pct": allocation.drift_pct,
            })

    return {
        "needs_rebalance": len(suggestions) > 0,
        "suggestions": suggestions,
    }
```

**Step 2: Update src/main.py**

```python
"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db.database import init_db
from src.api.holdings import router as holdings_router
from src.api.quotes import router as quotes_router
from src.api.portfolio import router as portfolio_router

app = FastAPI(
    title="EAM - Easy Asset Management",
    description="Personal Investment Decision System",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(holdings_router, prefix="/api")
app.include_router(quotes_router, prefix="/api")
app.include_router(portfolio_router, prefix="/api")


@app.on_event("startup")
def startup():
    """Initialize database on startup."""
    init_db()


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
```

**Step 3: Write tests - tests/api/test_portfolio.py**

```python
"""Tests for Portfolio API."""
import pytest
from decimal import Decimal

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
        # Create holdings in each tier
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
```

**Step 4: Run tests**

Run:
```bash
pytest tests/api/test_portfolio.py -v
```

Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add src/api/portfolio.py src/main.py tests/api/test_portfolio.py
git commit -m "feat: add Portfolio API for overview and rebalance suggestions"
```

---

## Task 10: Run All Tests and Final Commit

**Step 1: Run all tests**

Run:
```bash
pytest tests/ -v --tb=short
```

Expected: All tests PASS

**Step 2: Start services and verify**

Run:
```bash
docker-compose up -d
```

Wait for services to start, then:
```bash
curl http://localhost:8000/health
```

Expected: `{"status":"healthy"}`

**Step 3: Test API manually**

```bash
# Create a holding
curl -X POST http://localhost:8000/api/holdings \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "VOO",
    "market": "US",
    "tier": "stable",
    "quantity": "50",
    "avg_cost": "450",
    "first_buy_date": "2025-01-01",
    "buy_reason": "Core S&P 500 holding"
  }'

# Get portfolio overview
curl http://localhost:8000/api/portfolio/overview
```

**Step 4: Final commit with all files**

```bash
git add -A
git commit -m "feat: complete Phase 1 MVP with holdings, quotes, and portfolio APIs"
```

---

## Summary

Phase 1 MVP is complete with:

1. **Project Structure**: Python project with FastAPI, SQLAlchemy, Docker
2. **Database Models**: Holdings, Transactions, DailyQuotes
3. **Holdings CRUD API**: Create, read, update, delete holdings and transactions
4. **Quote Collectors**: yfinance (US) and AkShare (A-share/HK)
5. **Quotes API**: Fetch and sync market data
6. **Portfolio API**: Overview with tier allocations and rebalance suggestions

**Next Phase (Phase 2)** will add:
- Three sector analyzers (Tech, Precious Metals, Geopolitical)
- Signal generation and storage
- Telegram alerts
