# EAM Phase 2: Signals and Alerts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build sector analyzers that generate investment signals, store them in database, and send Telegram alerts for important events.

**Architecture:** Analyzers fetch data from external APIs (FRED, yfinance), generate signals based on predefined rules, store signals in MySQL, and optionally push to Telegram. APScheduler runs analyzers periodically.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, APScheduler, python-telegram-bot, FRED API, yfinance

---

## Prerequisites

- Phase 1 MVP completed and running
- Docker Compose services up
- Telegram Bot Token (create via @BotFather)
- FRED API Key (free at https://fred.stlouisfed.org/docs/api/api_key.html)

---

## Task 1: Signal Database Model

**Files:**
- Modify: `src/db/models.py`
- Modify: `src/api/schemas.py`
- Create: `tests/db/test_signal_model.py`

**Step 1: Write the failing test**

Create `tests/db/test_signal_model.py`:

```python
"""Tests for Signal model."""
import pytest
from datetime import datetime
from decimal import Decimal

from src.db.models import Signal, SignalType, SignalSeverity, SignalStatus


class TestSignalModel:
    """Tests for Signal model."""

    def test_signal_creation(self):
        """Test creating a Signal instance."""
        signal = Signal(
            signal_type=SignalType.SECTOR,
            sector="tech",
            title="AI Capex Surge",
            description="Mag 7 capex increased 25% QoQ",
            severity=SignalSeverity.INFO,
            source="earnings_reports",
            data={"capex_growth": 0.25, "companies": ["NVDA", "MSFT"]},
        )

        assert signal.signal_type == SignalType.SECTOR
        assert signal.sector == "tech"
        assert signal.severity == SignalSeverity.INFO
        assert signal.status == SignalStatus.ACTIVE

    def test_signal_with_related_symbols(self):
        """Test signal with related symbols."""
        signal = Signal(
            signal_type=SignalType.PRICE,
            title="NVDA hits 52-week high",
            description="NVIDIA reached new all-time high",
            severity=SignalSeverity.MEDIUM,
            source="price_monitor",
            related_symbols=["NVDA"],
        )

        assert signal.related_symbols == ["NVDA"]
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec api pytest tests/db/test_signal_model.py -v`
Expected: FAIL with "cannot import name 'Signal'"

**Step 3: Add Signal model to src/db/models.py**

Add these enums and model after the DailyQuote class:

```python
class SignalType(PyEnum):
    """Signal type enum."""
    SECTOR = "sector"      # Sector-level signal (tech, precious metals, etc.)
    PRICE = "price"        # Price alert (stop loss, take profit, 52-week high/low)
    MACRO = "macro"        # Macroeconomic signal (FOMC, CPI, etc.)
    SMART_MONEY = "smart_money"  # Institutional/insider activity
    HOLDING = "holding"    # Holding-specific signal


class SignalSeverity(PyEnum):
    """Signal severity enum."""
    INFO = "info"          # Informational
    LOW = "low"            # Low importance
    MEDIUM = "medium"      # Medium importance
    HIGH = "high"          # High importance - requires attention
    CRITICAL = "critical"  # Critical - immediate action needed


class SignalStatus(PyEnum):
    """Signal status enum."""
    ACTIVE = "active"      # Signal is active/unread
    READ = "read"          # User has read the signal
    ARCHIVED = "archived"  # Signal is archived


class Signal(Base):
    """Investment signals table."""
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    signal_type: Mapped[SignalType] = mapped_column(Enum(SignalType), nullable=False, index=True)
    sector: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    severity: Mapped[SignalSeverity] = mapped_column(Enum(SignalSeverity), nullable=False, index=True)
    status: Mapped[SignalStatus] = mapped_column(
        Enum(SignalStatus), default=SignalStatus.ACTIVE, index=True
    )

    source: Mapped[str] = mapped_column(String(100), nullable=False)
    data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    related_symbols: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Optional link to holding
    holding_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("holdings.id"), nullable=True, index=True
    )

    # Telegram notification tracking
    telegram_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __init__(self, **kwargs):
        if 'status' not in kwargs:
            kwargs['status'] = SignalStatus.ACTIVE
        if 'telegram_sent' not in kwargs:
            kwargs['telegram_sent'] = False
        super().__init__(**kwargs)

    __table_args__ = (
        {"mysql_charset": "utf8mb4"},
    )
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec api pytest tests/db/test_signal_model.py -v`
Expected: PASS (2 tests)

**Step 5: Add Signal schemas to src/api/schemas.py**

Add after the PortfolioOverview class:

```python
# ===== Signal Schemas =====

class SignalTypeEnum(str, Enum):
    """Signal type enum."""
    SECTOR = "sector"
    PRICE = "price"
    MACRO = "macro"
    SMART_MONEY = "smart_money"
    HOLDING = "holding"


class SignalSeverityEnum(str, Enum):
    """Signal severity enum."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SignalStatusEnum(str, Enum):
    """Signal status enum."""
    ACTIVE = "active"
    READ = "read"
    ARCHIVED = "archived"


class SignalCreate(BaseModel):
    """Schema for creating a signal."""
    signal_type: SignalTypeEnum
    sector: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    severity: SignalSeverityEnum
    source: str = Field(..., min_length=1, max_length=100)
    data: Optional[dict] = None
    related_symbols: Optional[List[str]] = None
    holding_id: Optional[int] = None
    expires_at: Optional[datetime] = None


class SignalResponse(BaseModel):
    """Schema for signal response."""
    id: int
    signal_type: SignalTypeEnum
    sector: Optional[str] = None
    title: str
    description: str
    severity: SignalSeverityEnum
    status: SignalStatusEnum
    source: str
    data: Optional[dict] = None
    related_symbols: Optional[List[str]] = None
    holding_id: Optional[int] = None
    telegram_sent: bool
    telegram_sent_at: Optional[datetime] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SignalUpdate(BaseModel):
    """Schema for updating a signal."""
    status: Optional[SignalStatusEnum] = None
```

**Step 6: Commit**

```bash
git add src/db/models.py src/api/schemas.py tests/db/test_signal_model.py
git commit -m "feat: add Signal model for storing investment signals"
```

---

## Task 2: Signals API Endpoints

**Files:**
- Create: `src/api/signals.py`
- Modify: `src/main.py`
- Create: `tests/api/test_signals.py`

**Step 1: Write the failing test**

Create `tests/api/test_signals.py`:

```python
"""Tests for Signals API."""
import pytest
from datetime import datetime

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
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec api pytest tests/api/test_signals.py -v`
Expected: FAIL with "404 Not Found" (router not registered)

**Step 3: Create src/api/signals.py**

```python
"""Signals API endpoints."""
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.db.database import get_db
from src.db.models import Signal, SignalType, SignalSeverity, SignalStatus
from src.api.schemas import (
    SignalCreate, SignalResponse, SignalUpdate,
    SignalTypeEnum, SignalSeverityEnum, SignalStatusEnum
)

router = APIRouter(prefix="/signals", tags=["signals"])

# Severity ordering for filtering
SEVERITY_ORDER = {
    SignalSeverity.INFO: 0,
    SignalSeverity.LOW: 1,
    SignalSeverity.MEDIUM: 2,
    SignalSeverity.HIGH: 3,
    SignalSeverity.CRITICAL: 4,
}


@router.post("", response_model=SignalResponse, status_code=status.HTTP_201_CREATED)
def create_signal(signal: SignalCreate, db: Session = Depends(get_db)):
    """Create a new signal."""
    db_signal = Signal(
        signal_type=SignalType[signal.signal_type.value.upper()],
        sector=signal.sector,
        title=signal.title,
        description=signal.description,
        severity=SignalSeverity[signal.severity.value.upper()],
        source=signal.source,
        data=signal.data,
        related_symbols=signal.related_symbols,
        holding_id=signal.holding_id,
        expires_at=signal.expires_at,
    )
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.get("", response_model=List[SignalResponse])
def list_signals(
    signal_type: Optional[SignalTypeEnum] = None,
    sector: Optional[str] = None,
    min_severity: Optional[SignalSeverityEnum] = None,
    status: Optional[SignalStatusEnum] = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """List signals with optional filters."""
    query = select(Signal)

    if signal_type:
        query = query.where(Signal.signal_type == SignalType[signal_type.value.upper()])
    if sector:
        query = query.where(Signal.sector == sector)
    if status:
        query = query.where(Signal.status == SignalStatus[status.value.upper()])
    if min_severity:
        min_level = SEVERITY_ORDER[SignalSeverity[min_severity.value.upper()]]
        valid_severities = [s for s, level in SEVERITY_ORDER.items() if level >= min_level]
        query = query.where(Signal.severity.in_(valid_severities))

    query = query.order_by(Signal.created_at.desc()).limit(limit)

    result = db.execute(query)
    return result.scalars().all()


@router.get("/{signal_id}", response_model=SignalResponse)
def get_signal(signal_id: int, db: Session = Depends(get_db)):
    """Get a specific signal by ID."""
    signal = db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal {signal_id} not found"
        )
    return signal


@router.patch("/{signal_id}", response_model=SignalResponse)
def update_signal(
    signal_id: int,
    update: SignalUpdate,
    db: Session = Depends(get_db),
):
    """Update a signal (mainly for status changes)."""
    signal = db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal {signal_id} not found"
        )

    if update.status:
        signal.status = SignalStatus[update.status.value.upper()]

    db.commit()
    db.refresh(signal)
    return signal


@router.post("/{signal_id}/mark-read", response_model=SignalResponse)
def mark_signal_read(signal_id: int, db: Session = Depends(get_db)):
    """Mark a signal as read."""
    signal = db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal {signal_id} not found"
        )

    signal.status = SignalStatus.READ
    db.commit()
    db.refresh(signal)
    return signal


@router.delete("/{signal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_signal(signal_id: int, db: Session = Depends(get_db)):
    """Delete a signal."""
    signal = db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal {signal_id} not found"
        )

    db.delete(signal)
    db.commit()
```

**Step 4: Update src/main.py to include signals router**

Add import and router registration:

```python
from src.api.signals import router as signals_router

# In the routers section:
app.include_router(signals_router, prefix="/api")
```

**Step 5: Run test to verify it passes**

Run: `docker compose exec api pytest tests/api/test_signals.py -v`
Expected: PASS (6 tests)

**Step 6: Commit**

```bash
git add src/api/signals.py src/main.py tests/api/test_signals.py
git commit -m "feat: add Signals API for CRUD operations"
```

---

## Task 3: Base Analyzer Class

**Files:**
- Create: `src/analyzers/base.py`
- Create: `tests/analyzers/__init__.py`
- Create: `tests/analyzers/test_base_analyzer.py`

**Step 1: Write the failing test**

Create `tests/analyzers/__init__.py`:

```python
"""Analyzer tests."""
```

Create `tests/analyzers/test_base_analyzer.py`:

```python
"""Tests for base analyzer."""
import pytest
from datetime import datetime
from typing import List

from src.analyzers.base import BaseAnalyzer, AnalyzerResult
from src.db.models import SignalSeverity


class TestAnalyzerResult:
    """Tests for AnalyzerResult."""

    def test_analyzer_result_creation(self):
        """Test creating an AnalyzerResult."""
        result = AnalyzerResult(
            title="Test Signal",
            description="This is a test",
            severity=SignalSeverity.MEDIUM,
            data={"key": "value"},
            related_symbols=["AAPL"],
        )

        assert result.title == "Test Signal"
        assert result.severity == SignalSeverity.MEDIUM
        assert result.data == {"key": "value"}


class MockAnalyzer(BaseAnalyzer):
    """Mock analyzer for testing."""

    @property
    def name(self) -> str:
        return "mock_analyzer"

    @property
    def sector(self) -> str:
        return "test"

    def analyze(self) -> List[AnalyzerResult]:
        return [
            AnalyzerResult(
                title="Mock Signal",
                description="Mock description",
                severity=SignalSeverity.LOW,
            )
        ]


class TestBaseAnalyzer:
    """Tests for BaseAnalyzer."""

    def test_analyzer_name(self):
        """Test analyzer has a name."""
        analyzer = MockAnalyzer()
        assert analyzer.name == "mock_analyzer"

    def test_analyzer_sector(self):
        """Test analyzer has a sector."""
        analyzer = MockAnalyzer()
        assert analyzer.sector == "test"

    def test_analyze_returns_results(self):
        """Test analyze returns AnalyzerResult list."""
        analyzer = MockAnalyzer()
        results = analyzer.analyze()

        assert len(results) == 1
        assert results[0].title == "Mock Signal"
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec api pytest tests/analyzers/test_base_analyzer.py -v`
Expected: FAIL with "cannot import name 'BaseAnalyzer'"

**Step 3: Create src/analyzers/base.py**

```python
"""Base analyzer class and result model."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Any
from datetime import datetime

from src.db.models import SignalSeverity


@dataclass
class AnalyzerResult:
    """Result from an analyzer."""
    title: str
    description: str
    severity: SignalSeverity
    data: Optional[dict] = field(default_factory=dict)
    related_symbols: Optional[List[str]] = field(default_factory=list)
    expires_at: Optional[datetime] = None


class BaseAnalyzer(ABC):
    """Abstract base class for all analyzers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the analyzer name (used as signal source)."""
        pass

    @property
    @abstractmethod
    def sector(self) -> str:
        """Return the sector this analyzer covers."""
        pass

    @abstractmethod
    def analyze(self) -> List[AnalyzerResult]:
        """
        Run the analysis and return a list of signals.

        Returns:
            List of AnalyzerResult objects representing detected signals.
        """
        pass

    def should_generate_signal(self, result: AnalyzerResult) -> bool:
        """
        Determine if a result should generate a signal.
        Override in subclasses for custom logic.

        Args:
            result: The analyzer result to evaluate.

        Returns:
            True if signal should be generated, False otherwise.
        """
        return True
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec api pytest tests/analyzers/test_base_analyzer.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add src/analyzers/base.py tests/analyzers/
git commit -m "feat: add BaseAnalyzer class and AnalyzerResult dataclass"
```

---

## Task 4: Precious Metals Analyzer

**Files:**
- Create: `src/analyzers/precious_metals.py`
- Create: `tests/analyzers/test_precious_metals.py`

**Step 1: Write the failing test**

Create `tests/analyzers/test_precious_metals.py`:

```python
"""Tests for precious metals analyzer."""
import pytest
from unittest.mock import patch, Mock
from decimal import Decimal

from src.analyzers.precious_metals import PreciousMetalsAnalyzer
from src.db.models import SignalSeverity


class TestPreciousMetalsAnalyzer:
    """Tests for PreciousMetalsAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return PreciousMetalsAnalyzer()

    def test_analyzer_name(self, analyzer):
        """Test analyzer name."""
        assert analyzer.name == "precious_metals_analyzer"

    def test_analyzer_sector(self, analyzer):
        """Test analyzer sector."""
        assert analyzer.sector == "precious_metals"

    def test_gold_silver_ratio_high(self, analyzer):
        """Test signal when gold/silver ratio is high (silver undervalued)."""
        with patch.object(analyzer, '_get_gold_price', return_value=2000.0):
            with patch.object(analyzer, '_get_silver_price', return_value=22.0):
                # Ratio = 2000/22 = 90.9 (> 85)
                results = analyzer.analyze()

                # Should have at least one signal about silver being undervalued
                silver_signals = [r for r in results if "silver" in r.title.lower()]
                assert len(silver_signals) >= 1
                assert any(r.severity in [SignalSeverity.MEDIUM, SignalSeverity.HIGH]
                          for r in silver_signals)

    def test_gold_silver_ratio_low(self, analyzer):
        """Test signal when gold/silver ratio is low (silver overvalued)."""
        with patch.object(analyzer, '_get_gold_price', return_value=2000.0):
            with patch.object(analyzer, '_get_silver_price', return_value=35.0):
                # Ratio = 2000/35 = 57.1 (< 65)
                results = analyzer.analyze()

                silver_signals = [r for r in results if "silver" in r.title.lower()]
                assert len(silver_signals) >= 1

    def test_gold_silver_ratio_normal(self, analyzer):
        """Test no signal when ratio is normal."""
        with patch.object(analyzer, '_get_gold_price', return_value=2000.0):
            with patch.object(analyzer, '_get_silver_price', return_value=26.67):
                # Ratio = 2000/26.67 = 75 (between 65 and 85)
                with patch.object(analyzer, '_get_tips_yield', return_value=1.5):
                    results = analyzer.analyze()

                    # Should have no gold/silver ratio signals
                    ratio_signals = [r for r in results
                                    if "ratio" in r.title.lower() or "silver" in r.title.lower()]
                    assert len(ratio_signals) == 0

    def test_tips_yield_signal(self, analyzer):
        """Test signal based on TIPS yield."""
        with patch.object(analyzer, '_get_gold_price', return_value=2000.0):
            with patch.object(analyzer, '_get_silver_price', return_value=26.67):
                with patch.object(analyzer, '_get_tips_yield', return_value=-0.5):
                    # Negative real yield is bullish for gold
                    results = analyzer.analyze()

                    tips_signals = [r for r in results if "tips" in r.title.lower() or "yield" in r.title.lower()]
                    assert len(tips_signals) >= 1
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec api pytest tests/analyzers/test_precious_metals.py -v`
Expected: FAIL with "cannot import name 'PreciousMetalsAnalyzer'"

**Step 3: Create src/analyzers/precious_metals.py**

```python
"""Precious metals sector analyzer."""
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from src.analyzers.base import BaseAnalyzer, AnalyzerResult
from src.db.models import SignalSeverity
from src.collectors.structured.yfinance_collector import YFinanceCollector

logger = logging.getLogger(__name__)

# Thresholds
GOLD_SILVER_RATIO_HIGH = 85  # Silver undervalued when ratio > 85
GOLD_SILVER_RATIO_LOW = 65   # Silver overvalued when ratio < 65
TIPS_YIELD_BULLISH = 1.0     # Gold bullish when real yield < 1%
TIPS_YIELD_VERY_BULLISH = 0  # Gold very bullish when real yield < 0


class PreciousMetalsAnalyzer(BaseAnalyzer):
    """
    Analyzer for precious metals sector (Gold & Silver).

    Monitors:
    - Gold/Silver ratio (>85 silver undervalued, <65 silver overvalued)
    - US Real Interest Rate (TIPS yield) - core driver for gold
    - Central bank gold purchases (future enhancement)

    Related ETFs: GLD, IAU, SLV, 518880 (A-share gold ETF)
    """

    RELATED_ETFS = ["GLD", "IAU", "SLV"]

    def __init__(self):
        self._collector = YFinanceCollector()

    @property
    def name(self) -> str:
        return "precious_metals_analyzer"

    @property
    def sector(self) -> str:
        return "precious_metals"

    def _get_gold_price(self) -> Optional[float]:
        """Get current gold price via GLD ETF."""
        try:
            quote = self._collector.fetch_latest_quote("GLD")
            if quote and quote.close:
                # GLD represents ~1/10 oz of gold, multiply by 10 for rough gold price
                return quote.close * 10
        except Exception as e:
            logger.error(f"Error fetching gold price: {e}")
        return None

    def _get_silver_price(self) -> Optional[float]:
        """Get current silver price via SLV ETF."""
        try:
            quote = self._collector.fetch_latest_quote("SLV")
            if quote and quote.close:
                # SLV represents ~1 oz of silver
                return quote.close
        except Exception as e:
            logger.error(f"Error fetching silver price: {e}")
        return None

    def _get_tips_yield(self) -> Optional[float]:
        """
        Get 10-year TIPS yield (real interest rate).
        Uses TIP ETF as proxy - in production, use FRED API for actual TIPS yield.
        """
        # For MVP, return a placeholder. In production, use FRED API.
        # FRED series: DFII10 (10-Year Treasury Inflation-Indexed Security)
        return None

    def analyze(self) -> List[AnalyzerResult]:
        """Analyze precious metals indicators and generate signals."""
        results = []

        gold_price = self._get_gold_price()
        silver_price = self._get_silver_price()
        tips_yield = self._get_tips_yield()

        # Analyze gold/silver ratio
        if gold_price and silver_price and silver_price > 0:
            ratio = gold_price / silver_price
            ratio_result = self._analyze_gold_silver_ratio(ratio, gold_price, silver_price)
            if ratio_result:
                results.append(ratio_result)

        # Analyze TIPS yield
        if tips_yield is not None:
            tips_result = self._analyze_tips_yield(tips_yield)
            if tips_result:
                results.append(tips_result)

        return results

    def _analyze_gold_silver_ratio(
        self,
        ratio: float,
        gold_price: float,
        silver_price: float
    ) -> Optional[AnalyzerResult]:
        """Analyze gold/silver ratio for trading signals."""

        if ratio > GOLD_SILVER_RATIO_HIGH:
            return AnalyzerResult(
                title="Silver Undervalued - High Gold/Silver Ratio",
                description=(
                    f"Gold/Silver ratio at {ratio:.1f} (threshold: >{GOLD_SILVER_RATIO_HIGH}). "
                    f"Historically high ratio suggests silver is undervalued relative to gold. "
                    f"Gold: ${gold_price:.2f}, Silver: ${silver_price:.2f}. "
                    f"Consider adding silver exposure (SLV) or rotating from gold to silver."
                ),
                severity=SignalSeverity.MEDIUM,
                data={
                    "gold_silver_ratio": round(ratio, 2),
                    "gold_price": round(gold_price, 2),
                    "silver_price": round(silver_price, 2),
                    "signal": "silver_undervalued",
                },
                related_symbols=["SLV", "GLD"],
            )

        elif ratio < GOLD_SILVER_RATIO_LOW:
            return AnalyzerResult(
                title="Silver Overvalued - Low Gold/Silver Ratio",
                description=(
                    f"Gold/Silver ratio at {ratio:.1f} (threshold: <{GOLD_SILVER_RATIO_LOW}). "
                    f"Historically low ratio suggests silver may be overvalued. "
                    f"Gold: ${gold_price:.2f}, Silver: ${silver_price:.2f}. "
                    f"Consider reducing silver exposure or rotating to gold."
                ),
                severity=SignalSeverity.LOW,
                data={
                    "gold_silver_ratio": round(ratio, 2),
                    "gold_price": round(gold_price, 2),
                    "silver_price": round(silver_price, 2),
                    "signal": "silver_overvalued",
                },
                related_symbols=["SLV", "GLD"],
            )

        return None

    def _analyze_tips_yield(self, tips_yield: float) -> Optional[AnalyzerResult]:
        """Analyze TIPS yield for gold outlook."""

        if tips_yield < TIPS_YIELD_VERY_BULLISH:
            return AnalyzerResult(
                title="Negative Real Yields - Very Bullish for Gold",
                description=(
                    f"10-Year TIPS yield at {tips_yield:.2f}% (negative real rates). "
                    f"Negative real interest rates are historically very bullish for gold "
                    f"as the opportunity cost of holding gold is negative. "
                    f"Consider increasing gold exposure."
                ),
                severity=SignalSeverity.HIGH,
                data={
                    "tips_yield": round(tips_yield, 2),
                    "signal": "very_bullish_gold",
                },
                related_symbols=["GLD", "IAU"],
            )

        elif tips_yield < TIPS_YIELD_BULLISH:
            return AnalyzerResult(
                title="Low Real Yields - Bullish for Gold",
                description=(
                    f"10-Year TIPS yield at {tips_yield:.2f}% (below {TIPS_YIELD_BULLISH}%). "
                    f"Low real interest rates support gold prices. "
                    f"Maintain or consider adding gold exposure."
                ),
                severity=SignalSeverity.MEDIUM,
                data={
                    "tips_yield": round(tips_yield, 2),
                    "signal": "bullish_gold",
                },
                related_symbols=["GLD", "IAU"],
            )

        return None
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec api pytest tests/analyzers/test_precious_metals.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add src/analyzers/precious_metals.py tests/analyzers/test_precious_metals.py
git commit -m "feat: add PreciousMetalsAnalyzer for gold/silver signals"
```

---

## Task 5: Telegram Notification Service

**Files:**
- Modify: `src/config.py`
- Create: `src/services/__init__.py`
- Create: `src/services/telegram.py`
- Create: `tests/services/__init__.py`
- Create: `tests/services/test_telegram.py`

**Step 1: Update src/config.py with Telegram settings**

Add to Settings class:

```python
    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = False
```

**Step 2: Write the failing test**

Create `tests/services/__init__.py`:

```python
"""Service tests."""
```

Create `tests/services/test_telegram.py`:

```python
"""Tests for Telegram service."""
import pytest
from unittest.mock import patch, Mock, AsyncMock
from datetime import datetime

from src.services.telegram import TelegramService, format_signal_message
from src.db.models import Signal, SignalType, SignalSeverity, SignalStatus


class TestFormatSignalMessage:
    """Tests for message formatting."""

    def test_format_signal_message(self):
        """Test formatting a signal as Telegram message."""
        signal = Signal(
            id=1,
            signal_type=SignalType.SECTOR,
            sector="precious_metals",
            title="Silver Undervalued",
            description="Gold/Silver ratio at 90. Consider adding silver.",
            severity=SignalSeverity.MEDIUM,
            source="precious_metals_analyzer",
            related_symbols=["SLV", "GLD"],
        )

        message = format_signal_message(signal)

        assert "Silver Undervalued" in message
        assert "MEDIUM" in message
        assert "precious_metals" in message
        assert "SLV" in message

    def test_format_critical_signal(self):
        """Test that critical signals have special formatting."""
        signal = Signal(
            id=2,
            signal_type=SignalType.PRICE,
            title="Stop Loss Triggered",
            description="NVDA hit stop loss at $800",
            severity=SignalSeverity.CRITICAL,
            source="price_monitor",
            related_symbols=["NVDA"],
        )

        message = format_signal_message(signal)

        assert "CRITICAL" in message
        assert "Stop Loss" in message


class TestTelegramService:
    """Tests for TelegramService."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock()
        settings.telegram_bot_token = "test_token"
        settings.telegram_chat_id = "123456"
        settings.telegram_enabled = True
        return settings

    def test_service_disabled_when_no_token(self):
        """Test service is disabled without token."""
        settings = Mock()
        settings.telegram_bot_token = ""
        settings.telegram_chat_id = ""
        settings.telegram_enabled = False

        service = TelegramService(settings)
        assert not service.is_enabled()

    def test_service_enabled_with_config(self, mock_settings):
        """Test service is enabled with proper config."""
        service = TelegramService(mock_settings)
        assert service.is_enabled()

    @pytest.mark.asyncio
    async def test_send_signal_when_disabled(self):
        """Test that send_signal returns False when disabled."""
        settings = Mock()
        settings.telegram_bot_token = ""
        settings.telegram_chat_id = ""
        settings.telegram_enabled = False

        service = TelegramService(settings)
        signal = Signal(
            signal_type=SignalType.SECTOR,
            title="Test",
            description="Test",
            severity=SignalSeverity.LOW,
            source="test",
        )

        result = await service.send_signal(signal)
        assert result is False
```

**Step 3: Run test to verify it fails**

Run: `docker compose exec api pytest tests/services/test_telegram.py -v`
Expected: FAIL with "cannot import name 'TelegramService'"

**Step 4: Create src/services/__init__.py**

```python
"""Services module."""
```

**Step 5: Create src/services/telegram.py**

```python
"""Telegram notification service."""
import asyncio
import logging
from typing import Optional

from src.db.models import Signal, SignalSeverity

logger = logging.getLogger(__name__)

# Severity emoji mapping
SEVERITY_EMOJI = {
    SignalSeverity.INFO: "ℹ️",
    SignalSeverity.LOW: "🔵",
    SignalSeverity.MEDIUM: "🟡",
    SignalSeverity.HIGH: "🟠",
    SignalSeverity.CRITICAL: "🔴",
}


def format_signal_message(signal: Signal) -> str:
    """
    Format a signal as a Telegram message.

    Args:
        signal: The signal to format.

    Returns:
        Formatted message string.
    """
    emoji = SEVERITY_EMOJI.get(signal.severity, "📊")
    severity_name = signal.severity.value.upper()

    lines = [
        f"{emoji} *{signal.title}*",
        f"",
        f"📊 Severity: {severity_name}",
    ]

    if signal.sector:
        lines.append(f"📁 Sector: {signal.sector}")

    lines.append(f"")
    lines.append(signal.description)

    if signal.related_symbols:
        symbols = ", ".join(signal.related_symbols)
        lines.append(f"")
        lines.append(f"🏷️ Symbols: {symbols}")

    lines.append(f"")
    lines.append(f"_Source: {signal.source}_")

    return "\n".join(lines)


class TelegramService:
    """Service for sending Telegram notifications."""

    def __init__(self, settings):
        """
        Initialize Telegram service.

        Args:
            settings: Application settings with Telegram config.
        """
        self._token = settings.telegram_bot_token
        self._chat_id = settings.telegram_chat_id
        self._enabled = settings.telegram_enabled
        self._bot = None

    def is_enabled(self) -> bool:
        """Check if Telegram notifications are enabled."""
        return bool(self._enabled and self._token and self._chat_id)

    async def _get_bot(self):
        """Get or create bot instance."""
        if self._bot is None:
            try:
                from telegram import Bot
                self._bot = Bot(token=self._token)
            except ImportError:
                logger.warning("python-telegram-bot not installed")
                return None
        return self._bot

    async def send_signal(self, signal: Signal) -> bool:
        """
        Send a signal notification via Telegram.

        Args:
            signal: The signal to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self.is_enabled():
            logger.debug("Telegram notifications disabled")
            return False

        try:
            bot = await self._get_bot()
            if not bot:
                return False

            message = format_signal_message(signal)

            await bot.send_message(
                chat_id=self._chat_id,
                text=message,
                parse_mode="Markdown",
            )

            logger.info(f"Sent Telegram notification for signal {signal.id}")
            return True

        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
            return False

    async def send_message(self, text: str) -> bool:
        """
        Send a custom message via Telegram.

        Args:
            text: The message text.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self.is_enabled():
            return False

        try:
            bot = await self._get_bot()
            if not bot:
                return False

            await bot.send_message(
                chat_id=self._chat_id,
                text=text,
                parse_mode="Markdown",
            )
            return True

        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False


def get_telegram_service():
    """Get TelegramService instance with current settings."""
    from src.config import get_settings
    return TelegramService(get_settings())
```

**Step 6: Add python-telegram-bot to pyproject.toml**

Add to dependencies:

```toml
    "python-telegram-bot>=21.0",
```

**Step 7: Run test to verify it passes**

Run: `docker compose exec api pytest tests/services/test_telegram.py -v`
Expected: PASS (4 tests)

**Step 8: Commit**

```bash
git add src/config.py src/services/ tests/services/ pyproject.toml
git commit -m "feat: add Telegram notification service"
```

---

## Task 6: Analyzer Runner Service

**Files:**
- Create: `src/services/analyzer_runner.py`
- Create: `tests/services/test_analyzer_runner.py`

**Step 1: Write the failing test**

Create `tests/services/test_analyzer_runner.py`:

```python
"""Tests for analyzer runner service."""
import pytest
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime

from src.services.analyzer_runner import AnalyzerRunner
from src.analyzers.base import AnalyzerResult
from src.db.models import SignalSeverity


class TestAnalyzerRunner:
    """Tests for AnalyzerRunner."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = MagicMock()
        session.add = MagicMock()
        session.commit = MagicMock()
        session.refresh = MagicMock()
        return session

    @pytest.fixture
    def mock_analyzer(self):
        """Create mock analyzer."""
        analyzer = MagicMock()
        analyzer.name = "test_analyzer"
        analyzer.sector = "test"
        analyzer.analyze.return_value = [
            AnalyzerResult(
                title="Test Signal",
                description="Test description",
                severity=SignalSeverity.MEDIUM,
                data={"key": "value"},
                related_symbols=["TEST"],
            )
        ]
        return analyzer

    def test_run_analyzer_creates_signals(self, mock_db_session, mock_analyzer):
        """Test that running an analyzer creates signals in database."""
        runner = AnalyzerRunner(mock_db_session)

        signals = runner.run_analyzer(mock_analyzer)

        assert len(signals) == 1
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    def test_run_analyzer_with_no_results(self, mock_db_session):
        """Test analyzer that returns no results."""
        analyzer = MagicMock()
        analyzer.name = "empty_analyzer"
        analyzer.sector = "test"
        analyzer.analyze.return_value = []

        runner = AnalyzerRunner(mock_db_session)
        signals = runner.run_analyzer(analyzer)

        assert len(signals) == 0
        mock_db_session.add.assert_not_called()

    def test_run_all_analyzers(self, mock_db_session, mock_analyzer):
        """Test running all registered analyzers."""
        runner = AnalyzerRunner(mock_db_session)
        runner.register_analyzer(mock_analyzer)

        all_signals = runner.run_all()

        assert len(all_signals) == 1
        mock_analyzer.analyze.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec api pytest tests/services/test_analyzer_runner.py -v`
Expected: FAIL with "cannot import name 'AnalyzerRunner'"

**Step 3: Create src/services/analyzer_runner.py**

```python
"""Analyzer runner service."""
import logging
from typing import List, Optional
from datetime import datetime

from sqlalchemy.orm import Session

from src.analyzers.base import BaseAnalyzer, AnalyzerResult
from src.db.models import Signal, SignalType, SignalSeverity
from src.services.telegram import TelegramService, get_telegram_service

logger = logging.getLogger(__name__)


class AnalyzerRunner:
    """
    Service for running analyzers and creating signals.

    Manages analyzer registration, execution, and signal persistence.
    """

    def __init__(self, db: Session, telegram_service: Optional[TelegramService] = None):
        """
        Initialize the analyzer runner.

        Args:
            db: Database session for persisting signals.
            telegram_service: Optional Telegram service for notifications.
        """
        self._db = db
        self._telegram = telegram_service
        self._analyzers: List[BaseAnalyzer] = []

    def register_analyzer(self, analyzer: BaseAnalyzer) -> None:
        """
        Register an analyzer to be run.

        Args:
            analyzer: The analyzer to register.
        """
        self._analyzers.append(analyzer)
        logger.info(f"Registered analyzer: {analyzer.name}")

    def run_analyzer(self, analyzer: BaseAnalyzer) -> List[Signal]:
        """
        Run a single analyzer and persist results.

        Args:
            analyzer: The analyzer to run.

        Returns:
            List of created Signal objects.
        """
        logger.info(f"Running analyzer: {analyzer.name}")
        signals = []

        try:
            results = analyzer.analyze()

            for result in results:
                signal = self._create_signal(analyzer, result)
                signals.append(signal)

            logger.info(f"Analyzer {analyzer.name} generated {len(signals)} signals")

        except Exception as e:
            logger.error(f"Error running analyzer {analyzer.name}: {e}")

        return signals

    def _create_signal(self, analyzer: BaseAnalyzer, result: AnalyzerResult) -> Signal:
        """
        Create and persist a signal from an analyzer result.

        Args:
            analyzer: The analyzer that generated the result.
            result: The analyzer result.

        Returns:
            The created Signal object.
        """
        signal = Signal(
            signal_type=SignalType.SECTOR,
            sector=analyzer.sector,
            title=result.title,
            description=result.description,
            severity=result.severity,
            source=analyzer.name,
            data=result.data,
            related_symbols=result.related_symbols,
            expires_at=result.expires_at,
        )

        self._db.add(signal)
        self._db.commit()
        self._db.refresh(signal)

        logger.debug(f"Created signal: {signal.id} - {signal.title}")

        return signal

    def run_all(self) -> List[Signal]:
        """
        Run all registered analyzers.

        Returns:
            List of all created signals.
        """
        all_signals = []

        for analyzer in self._analyzers:
            signals = self.run_analyzer(analyzer)
            all_signals.extend(signals)

        return all_signals

    async def run_all_with_notifications(self) -> List[Signal]:
        """
        Run all analyzers and send Telegram notifications for important signals.

        Returns:
            List of all created signals.
        """
        all_signals = self.run_all()

        if self._telegram and self._telegram.is_enabled():
            for signal in all_signals:
                # Only notify for MEDIUM severity and above
                if signal.severity in [
                    SignalSeverity.MEDIUM,
                    SignalSeverity.HIGH,
                    SignalSeverity.CRITICAL,
                ]:
                    success = await self._telegram.send_signal(signal)
                    if success:
                        signal.telegram_sent = True
                        signal.telegram_sent_at = datetime.utcnow()
                        self._db.commit()

        return all_signals
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec api pytest tests/services/test_analyzer_runner.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/services/analyzer_runner.py tests/services/test_analyzer_runner.py
git commit -m "feat: add AnalyzerRunner service for executing analyzers"
```

---

## Task 7: Macro Analyzer (FOMC, Economic Indicators)

**Files:**
- Create: `src/analyzers/macro.py`
- Create: `tests/analyzers/test_macro.py`

**Step 1: Write the failing test**

Create `tests/analyzers/test_macro.py`:

```python
"""Tests for macro analyzer."""
import pytest
from unittest.mock import patch, Mock
from datetime import date, datetime, timedelta

from src.analyzers.macro import MacroAnalyzer
from src.db.models import SignalSeverity


class TestMacroAnalyzer:
    """Tests for MacroAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return MacroAnalyzer()

    def test_analyzer_name(self, analyzer):
        """Test analyzer name."""
        assert analyzer.name == "macro_analyzer"

    def test_analyzer_sector(self, analyzer):
        """Test analyzer sector."""
        assert analyzer.sector == "macro"

    def test_fomc_meeting_upcoming(self, analyzer):
        """Test signal for upcoming FOMC meeting."""
        # Mock an FOMC meeting 3 days from now
        future_date = date.today() + timedelta(days=3)

        with patch.object(analyzer, '_get_next_fomc_date', return_value=future_date):
            with patch.object(analyzer, '_get_fed_funds_rate', return_value=5.25):
                results = analyzer.analyze()

                fomc_signals = [r for r in results if "fomc" in r.title.lower()]
                assert len(fomc_signals) >= 1

    def test_no_signal_when_fomc_far_away(self, analyzer):
        """Test no signal when FOMC meeting is far away."""
        # Mock an FOMC meeting 30 days from now
        future_date = date.today() + timedelta(days=30)

        with patch.object(analyzer, '_get_next_fomc_date', return_value=future_date):
            with patch.object(analyzer, '_get_fed_funds_rate', return_value=5.25):
                results = analyzer.analyze()

                fomc_signals = [r for r in results if "fomc" in r.title.lower()]
                assert len(fomc_signals) == 0

    def test_high_interest_rate_signal(self, analyzer):
        """Test signal for high interest rates."""
        with patch.object(analyzer, '_get_next_fomc_date', return_value=None):
            with patch.object(analyzer, '_get_fed_funds_rate', return_value=6.0):
                results = analyzer.analyze()

                rate_signals = [r for r in results if "rate" in r.title.lower()]
                # High rates should generate a signal
                assert any(r.severity in [SignalSeverity.MEDIUM, SignalSeverity.HIGH]
                          for r in rate_signals) or len(rate_signals) == 0
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec api pytest tests/analyzers/test_macro.py -v`
Expected: FAIL with "cannot import name 'MacroAnalyzer'"

**Step 3: Create src/analyzers/macro.py**

```python
"""Macroeconomic and geopolitical analyzer."""
from typing import List, Optional
from datetime import date, datetime, timedelta
import logging

from src.analyzers.base import BaseAnalyzer, AnalyzerResult
from src.db.models import SignalSeverity

logger = logging.getLogger(__name__)

# 2025 FOMC Meeting Dates (approximate - check Fed calendar)
FOMC_DATES_2025 = [
    date(2025, 1, 29),
    date(2025, 3, 19),
    date(2025, 5, 7),
    date(2025, 6, 18),
    date(2025, 7, 30),
    date(2025, 9, 17),
    date(2025, 11, 5),
    date(2025, 12, 17),
]

# 2026 FOMC Meeting Dates (approximate)
FOMC_DATES_2026 = [
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 5, 6),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),
    date(2026, 11, 4),
    date(2026, 12, 16),
]

ALL_FOMC_DATES = FOMC_DATES_2025 + FOMC_DATES_2026

# Thresholds
FOMC_WARNING_DAYS = 7  # Alert when FOMC is within this many days
HIGH_RATE_THRESHOLD = 5.0  # Fed funds rate considered "high"


class MacroAnalyzer(BaseAnalyzer):
    """
    Analyzer for macroeconomic and geopolitical factors.

    Monitors:
    - FOMC meeting schedule and rate decisions
    - Fed Funds Rate levels
    - Key economic indicators (CPI, GDP, PMI) - future enhancement
    - Geopolitical tension index - future enhancement

    Related assets: SGOV (short-term treasuries), TLT (long bonds), SPY
    """

    RELATED_ETFS = ["SGOV", "TLT", "SPY", "QQQ"]

    @property
    def name(self) -> str:
        return "macro_analyzer"

    @property
    def sector(self) -> str:
        return "macro"

    def _get_next_fomc_date(self) -> Optional[date]:
        """Get the next FOMC meeting date."""
        today = date.today()
        for fomc_date in ALL_FOMC_DATES:
            if fomc_date >= today:
                return fomc_date
        return None

    def _get_fed_funds_rate(self) -> Optional[float]:
        """
        Get current Fed Funds Rate.
        In production, use FRED API (series: FEDFUNDS or DFF).
        """
        # Placeholder - in production fetch from FRED
        return 5.25  # As of late 2024

    def analyze(self) -> List[AnalyzerResult]:
        """Analyze macroeconomic indicators and generate signals."""
        results = []

        # Check FOMC schedule
        next_fomc = self._get_next_fomc_date()
        if next_fomc:
            fomc_result = self._analyze_fomc_schedule(next_fomc)
            if fomc_result:
                results.append(fomc_result)

        # Check interest rate environment
        fed_rate = self._get_fed_funds_rate()
        if fed_rate is not None:
            rate_result = self._analyze_rate_environment(fed_rate)
            if rate_result:
                results.append(rate_result)

        return results

    def _analyze_fomc_schedule(self, next_fomc: date) -> Optional[AnalyzerResult]:
        """Generate signal for upcoming FOMC meeting."""
        days_until = (next_fomc - date.today()).days

        if days_until <= FOMC_WARNING_DAYS:
            severity = SignalSeverity.HIGH if days_until <= 3 else SignalSeverity.MEDIUM

            return AnalyzerResult(
                title=f"FOMC Meeting in {days_until} Days",
                description=(
                    f"Federal Reserve FOMC meeting scheduled for {next_fomc.strftime('%B %d, %Y')}. "
                    f"Market volatility typically increases around FOMC announcements. "
                    f"Review positions and consider hedging strategies. "
                    f"Key watch: rate decision, dot plot, Powell's press conference."
                ),
                severity=severity,
                data={
                    "fomc_date": next_fomc.isoformat(),
                    "days_until": days_until,
                },
                related_symbols=self.RELATED_ETFS,
                expires_at=datetime.combine(next_fomc + timedelta(days=1), datetime.min.time()),
            )

        return None

    def _analyze_rate_environment(self, fed_rate: float) -> Optional[AnalyzerResult]:
        """Analyze the interest rate environment."""

        if fed_rate >= HIGH_RATE_THRESHOLD:
            return AnalyzerResult(
                title=f"High Interest Rate Environment ({fed_rate:.2f}%)",
                description=(
                    f"Fed Funds Rate at {fed_rate:.2f}%, which is historically high. "
                    f"High rates typically pressure growth stocks and favor value/dividend stocks. "
                    f"Short-duration treasuries (SGOV) offer attractive risk-free returns. "
                    f"Consider reducing duration risk in bond holdings."
                ),
                severity=SignalSeverity.INFO,
                data={
                    "fed_funds_rate": fed_rate,
                    "signal": "high_rate_environment",
                },
                related_symbols=["SGOV", "SCHD", "VYM"],
            )

        return None
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec api pytest tests/analyzers/test_macro.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add src/analyzers/macro.py tests/analyzers/test_macro.py
git commit -m "feat: add MacroAnalyzer for FOMC and rate environment signals"
```

---

## Task 8: Price Alert Analyzer

**Files:**
- Create: `src/analyzers/price_alerts.py`
- Create: `tests/analyzers/test_price_alerts.py`

**Step 1: Write the failing test**

Create `tests/analyzers/test_price_alerts.py`:

```python
"""Tests for price alert analyzer."""
import pytest
from unittest.mock import patch, Mock, MagicMock
from decimal import Decimal
from datetime import date

from src.analyzers.price_alerts import PriceAlertAnalyzer
from src.db.models import Holding, Market, Tier, SignalSeverity
from src.collectors.base import QuoteData


class TestPriceAlertAnalyzer:
    """Tests for PriceAlertAnalyzer."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def sample_holding(self):
        """Create a sample holding."""
        holding = Holding(
            id=1,
            symbol="NVDA",
            market=Market.US,
            tier=Tier.GAMBLE,
            quantity=Decimal("10"),
            avg_cost=Decimal("900"),
            first_buy_date=date(2025, 1, 1),
            buy_reason="AI play",
            stop_loss_price=Decimal("800"),
            take_profit_price=Decimal("1100"),
        )
        return holding

    def test_analyzer_name(self, mock_db):
        """Test analyzer name."""
        analyzer = PriceAlertAnalyzer(mock_db)
        assert analyzer.name == "price_alert_analyzer"

    def test_analyzer_sector(self, mock_db):
        """Test analyzer sector."""
        analyzer = PriceAlertAnalyzer(mock_db)
        assert analyzer.sector == "price"

    def test_stop_loss_triggered(self, mock_db, sample_holding):
        """Test signal when stop loss is triggered."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = [sample_holding]

        analyzer = PriceAlertAnalyzer(mock_db)

        # Mock price below stop loss
        with patch.object(analyzer, '_get_current_price', return_value=780.0):
            results = analyzer.analyze()

            stop_loss_signals = [r for r in results if "stop" in r.title.lower()]
            assert len(stop_loss_signals) == 1
            assert stop_loss_signals[0].severity == SignalSeverity.CRITICAL

    def test_take_profit_triggered(self, mock_db, sample_holding):
        """Test signal when take profit is triggered."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = [sample_holding]

        analyzer = PriceAlertAnalyzer(mock_db)

        # Mock price above take profit
        with patch.object(analyzer, '_get_current_price', return_value=1150.0):
            results = analyzer.analyze()

            take_profit_signals = [r for r in results if "profit" in r.title.lower()]
            assert len(take_profit_signals) == 1
            assert take_profit_signals[0].severity == SignalSeverity.HIGH

    def test_large_daily_move(self, mock_db, sample_holding):
        """Test signal for large daily price move."""
        sample_holding.stop_loss_price = None
        sample_holding.take_profit_price = None
        mock_db.execute.return_value.scalars.return_value.all.return_value = [sample_holding]

        analyzer = PriceAlertAnalyzer(mock_db)

        # Mock 8% daily drop
        with patch.object(analyzer, '_get_current_price', return_value=850.0):
            with patch.object(analyzer, '_get_previous_close', return_value=920.0):
                results = analyzer.analyze()

                move_signals = [r for r in results if "move" in r.title.lower() or "drop" in r.title.lower()]
                assert len(move_signals) >= 1

    def test_no_signal_normal_price(self, mock_db, sample_holding):
        """Test no signal when price is normal."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = [sample_holding]

        analyzer = PriceAlertAnalyzer(mock_db)

        # Mock price in normal range
        with patch.object(analyzer, '_get_current_price', return_value=950.0):
            with patch.object(analyzer, '_get_previous_close', return_value=945.0):
                results = analyzer.analyze()

                # Should have no alerts
                assert len(results) == 0
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec api pytest tests/analyzers/test_price_alerts.py -v`
Expected: FAIL with "cannot import name 'PriceAlertAnalyzer'"

**Step 3: Create src/analyzers/price_alerts.py**

```python
"""Price alert analyzer for holdings."""
from typing import List, Optional
from decimal import Decimal
import logging

from sqlalchemy.orm import Session
from sqlalchemy import select

from src.analyzers.base import BaseAnalyzer, AnalyzerResult
from src.db.models import Holding, HoldingStatus, Market, SignalSeverity
from src.collectors.structured.yfinance_collector import YFinanceCollector
from src.collectors.structured.akshare_collector import AkShareCollector

logger = logging.getLogger(__name__)

# Thresholds
LARGE_MOVE_THRESHOLD = 0.05  # 5% daily move triggers alert


class PriceAlertAnalyzer(BaseAnalyzer):
    """
    Analyzer for price-based alerts on holdings.

    Monitors:
    - Stop loss triggers
    - Take profit triggers
    - Large daily moves (>5%)
    - 52-week high/low (future enhancement)
    """

    def __init__(self, db: Session):
        """
        Initialize price alert analyzer.

        Args:
            db: Database session for fetching holdings.
        """
        self._db = db
        self._us_collector = YFinanceCollector()
        self._cn_collector = AkShareCollector()

    @property
    def name(self) -> str:
        return "price_alert_analyzer"

    @property
    def sector(self) -> str:
        return "price"

    def _get_current_price(self, symbol: str, market: Market) -> Optional[float]:
        """Get current price for a symbol."""
        try:
            if market == Market.US:
                quote = self._us_collector.fetch_latest_quote(symbol)
            else:
                quote = self._cn_collector.fetch_latest_quote(symbol, market.value)

            if quote and quote.close:
                return float(quote.close)
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
        return None

    def _get_previous_close(self, symbol: str, market: Market) -> Optional[float]:
        """Get previous close price."""
        # For MVP, return None - in production, fetch from database or calculate
        return None

    def analyze(self) -> List[AnalyzerResult]:
        """Analyze prices for all active holdings."""
        results = []

        # Get all active holdings
        holdings = self._db.execute(
            select(Holding).where(Holding.status == HoldingStatus.ACTIVE)
        ).scalars().all()

        for holding in holdings:
            current_price = self._get_current_price(holding.symbol, holding.market)
            if current_price is None:
                continue

            # Check stop loss
            if holding.stop_loss_price:
                stop_loss_result = self._check_stop_loss(holding, current_price)
                if stop_loss_result:
                    results.append(stop_loss_result)
                    continue  # Don't check other conditions if stop loss triggered

            # Check take profit
            if holding.take_profit_price:
                take_profit_result = self._check_take_profit(holding, current_price)
                if take_profit_result:
                    results.append(take_profit_result)
                    continue

            # Check large daily move
            prev_close = self._get_previous_close(holding.symbol, holding.market)
            if prev_close:
                move_result = self._check_large_move(holding, current_price, prev_close)
                if move_result:
                    results.append(move_result)

        return results

    def _check_stop_loss(
        self,
        holding: Holding,
        current_price: float
    ) -> Optional[AnalyzerResult]:
        """Check if stop loss is triggered."""
        stop_loss = float(holding.stop_loss_price)

        if current_price <= stop_loss:
            loss_pct = ((current_price - float(holding.avg_cost)) / float(holding.avg_cost)) * 100

            return AnalyzerResult(
                title=f"🚨 STOP LOSS TRIGGERED: {holding.symbol}",
                description=(
                    f"{holding.symbol} has hit stop loss at ${stop_loss:.2f}. "
                    f"Current price: ${current_price:.2f}. "
                    f"Your avg cost: ${float(holding.avg_cost):.2f}. "
                    f"Position P/L: {loss_pct:.1f}%. "
                    f"Consider executing stop loss order."
                ),
                severity=SignalSeverity.CRITICAL,
                data={
                    "symbol": holding.symbol,
                    "current_price": current_price,
                    "stop_loss": stop_loss,
                    "avg_cost": float(holding.avg_cost),
                    "loss_pct": round(loss_pct, 2),
                    "alert_type": "stop_loss",
                },
                related_symbols=[holding.symbol],
            )

        return None

    def _check_take_profit(
        self,
        holding: Holding,
        current_price: float
    ) -> Optional[AnalyzerResult]:
        """Check if take profit is triggered."""
        take_profit = float(holding.take_profit_price)

        if current_price >= take_profit:
            gain_pct = ((current_price - float(holding.avg_cost)) / float(holding.avg_cost)) * 100

            return AnalyzerResult(
                title=f"🎯 TAKE PROFIT REACHED: {holding.symbol}",
                description=(
                    f"{holding.symbol} has reached take profit target at ${take_profit:.2f}. "
                    f"Current price: ${current_price:.2f}. "
                    f"Your avg cost: ${float(holding.avg_cost):.2f}. "
                    f"Position gain: +{gain_pct:.1f}%. "
                    f"Consider taking profits or adjusting target."
                ),
                severity=SignalSeverity.HIGH,
                data={
                    "symbol": holding.symbol,
                    "current_price": current_price,
                    "take_profit": take_profit,
                    "avg_cost": float(holding.avg_cost),
                    "gain_pct": round(gain_pct, 2),
                    "alert_type": "take_profit",
                },
                related_symbols=[holding.symbol],
            )

        return None

    def _check_large_move(
        self,
        holding: Holding,
        current_price: float,
        prev_close: float
    ) -> Optional[AnalyzerResult]:
        """Check for large daily price move."""
        change_pct = (current_price - prev_close) / prev_close

        if abs(change_pct) >= LARGE_MOVE_THRESHOLD:
            direction = "up" if change_pct > 0 else "down"
            emoji = "📈" if change_pct > 0 else "📉"

            return AnalyzerResult(
                title=f"{emoji} Large Move: {holding.symbol} {direction} {abs(change_pct)*100:.1f}%",
                description=(
                    f"{holding.symbol} moved {direction} {abs(change_pct)*100:.1f}% today. "
                    f"Previous close: ${prev_close:.2f}, Current: ${current_price:.2f}. "
                    f"Review news and consider if position adjustment needed."
                ),
                severity=SignalSeverity.MEDIUM,
                data={
                    "symbol": holding.symbol,
                    "current_price": current_price,
                    "prev_close": prev_close,
                    "change_pct": round(change_pct * 100, 2),
                    "alert_type": "large_move",
                },
                related_symbols=[holding.symbol],
            )

        return None
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec api pytest tests/analyzers/test_price_alerts.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add src/analyzers/price_alerts.py tests/analyzers/test_price_alerts.py
git commit -m "feat: add PriceAlertAnalyzer for stop loss and take profit alerts"
```

---

## Task 9: Analyzer API Endpoint

**Files:**
- Create: `src/api/analyzers.py`
- Modify: `src/main.py`
- Create: `tests/api/test_analyzers_api.py`

**Step 1: Write the failing test**

Create `tests/api/test_analyzers_api.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec api pytest tests/api/test_analyzers_api.py -v`
Expected: FAIL (router not found)

**Step 3: Create src/api/analyzers.py**

```python
"""Analyzers API endpoints."""
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.analyzers.precious_metals import PreciousMetalsAnalyzer
from src.analyzers.macro import MacroAnalyzer
from src.analyzers.price_alerts import PriceAlertAnalyzer
from src.services.analyzer_runner import AnalyzerRunner

router = APIRouter(prefix="/analyzers", tags=["analyzers"])

# Registry of available analyzers
ANALYZER_REGISTRY = {
    "precious_metals": {
        "name": "Precious Metals Analyzer",
        "description": "Monitors gold/silver ratio and TIPS yields",
        "class": PreciousMetalsAnalyzer,
        "requires_db": False,
    },
    "macro": {
        "name": "Macro Analyzer",
        "description": "Monitors FOMC schedule and interest rate environment",
        "class": MacroAnalyzer,
        "requires_db": False,
    },
    "price_alerts": {
        "name": "Price Alert Analyzer",
        "description": "Monitors stop loss and take profit levels for holdings",
        "class": PriceAlertAnalyzer,
        "requires_db": True,
    },
}


@router.get("")
def list_analyzers() -> Dict[str, Any]:
    """List all available analyzers."""
    analyzers = []
    for key, info in ANALYZER_REGISTRY.items():
        analyzers.append({
            "id": key,
            "name": info["name"],
            "description": info["description"],
        })
    return {"analyzers": analyzers}


@router.post("/{analyzer_id}/run")
def run_analyzer(analyzer_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Run a specific analyzer and create signals."""
    if analyzer_id not in ANALYZER_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analyzer '{analyzer_id}' not found"
        )

    info = ANALYZER_REGISTRY[analyzer_id]

    # Create analyzer instance
    if info["requires_db"]:
        analyzer = info["class"](db)
    else:
        analyzer = info["class"]()

    # Run analyzer
    runner = AnalyzerRunner(db)
    signals = runner.run_analyzer(analyzer)

    return {
        "analyzer": analyzer_id,
        "signals_created": len(signals),
        "signal_ids": [s.id for s in signals],
    }


@router.post("/run-all")
def run_all_analyzers(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Run all analyzers and create signals."""
    runner = AnalyzerRunner(db)

    # Register all analyzers
    for key, info in ANALYZER_REGISTRY.items():
        if info["requires_db"]:
            analyzer = info["class"](db)
        else:
            analyzer = info["class"]()
        runner.register_analyzer(analyzer)

    # Run all
    signals = runner.run_all()

    return {
        "total_signals": len(signals),
        "signal_ids": [s.id for s in signals],
        "analyzers_run": list(ANALYZER_REGISTRY.keys()),
    }
```

**Step 4: Update src/main.py to include analyzers router**

Add import and router registration:

```python
from src.api.analyzers import router as analyzers_router

# In the routers section:
app.include_router(analyzers_router, prefix="/api")
```

**Step 5: Run test to verify it passes**

Run: `docker compose exec api pytest tests/api/test_analyzers_api.py -v`
Expected: PASS (4 tests)

**Step 6: Commit**

```bash
git add src/api/analyzers.py src/main.py tests/api/test_analyzers_api.py
git commit -m "feat: add Analyzers API for running signal generation"
```

---

## Task 10: Integration Testing and Final Verification

**Step 1: Run all tests**

```bash
docker compose exec api pytest tests/ -v --tb=short
```

Expected: All tests PASS

**Step 2: Test full workflow manually**

```bash
# 1. Create a holding with stop loss
curl -X POST http://localhost:8000/api/holdings -H "Content-Type: application/json" -d '{
  "symbol": "NVDA",
  "market": "US",
  "tier": "gamble",
  "quantity": "10",
  "avg_cost": "900",
  "first_buy_date": "2025-01-01",
  "buy_reason": "AI play",
  "stop_loss_price": "800",
  "take_profit_price": "1100"
}'

# 2. List available analyzers
curl http://localhost:8000/api/analyzers

# 3. Run precious metals analyzer
curl -X POST http://localhost:8000/api/analyzers/precious_metals/run

# 4. Run all analyzers
curl -X POST http://localhost:8000/api/analyzers/run-all

# 5. List generated signals
curl http://localhost:8000/api/signals

# 6. Filter signals by severity
curl "http://localhost:8000/api/signals?min_severity=medium"
```

**Step 3: Update .env.example with new settings**

Add to `.env.example`:

```bash
# Telegram Notifications
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_ENABLED=false

# FRED API (for macro data)
FRED_API_KEY=
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete Phase 2 with signals, analyzers, and Telegram integration"
```

---

## Summary

Phase 2 is complete with:

1. **Signal Model**: Database storage for investment signals with severity, status, and Telegram tracking
2. **Signals API**: CRUD operations for signals with filtering
3. **Base Analyzer**: Abstract class for all analyzers
4. **Precious Metals Analyzer**: Gold/silver ratio and TIPS yield monitoring
5. **Macro Analyzer**: FOMC schedule and rate environment tracking
6. **Price Alert Analyzer**: Stop loss and take profit monitoring for holdings
7. **Telegram Service**: Send notifications for important signals
8. **Analyzer Runner**: Service for executing analyzers and persisting results
9. **Analyzers API**: Endpoints to list and run analyzers

**Next Phase (Phase 3)** will add:
- Scheduled jobs (APScheduler) for automatic analyzer execution
- Weekly report generation
- Vue.js frontend dashboard
- More sophisticated analyzers (smart money tracking, sentiment)
