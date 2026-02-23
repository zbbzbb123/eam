# Watchlist Deep Analysis Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform existing Watchlist into a deep-analysis "Tracked Stocks" module with news/earnings data collection and enhanced LLM analysis in reports.

**Architecture:** Add two new DB tables (StockNews, StockEarnings), two new collectors (NewsCollector, EarningsCollector), enhance report_generator.py to inject news/earnings context into LLM prompts, and update the Watchlist frontend to show news/earnings data.

**Tech Stack:** Python/FastAPI, SQLAlchemy 2.0, akshare, yfinance, Vue 3

---

### Task 1: Add StockNews and StockEarnings database models

**Files:**
- Modify: `src/db/models_market_data.py` (append after YieldSpreadRecord class, ~line 264)
- Modify: `tests/db/test_models.py` (add model tests)

**Step 1: Write the failing test**

In `tests/db/test_models.py`, add:

```python
from src.db.models_market_data import StockNews, StockEarnings

def test_stock_news_model():
    news = StockNews(
        symbol="NVDA",
        market="US",
        title="NVIDIA Q4 earnings beat",
        summary="Revenue up 80% YoY",
        source="yahoo",
        url="https://example.com/news/1",
        published_at=datetime(2026, 2, 20, 10, 0),
    )
    assert news.symbol == "NVDA"
    assert news.market == "US"
    assert news.source == "yahoo"

def test_stock_earnings_model():
    earnings = StockEarnings(
        symbol="NVDA",
        market="US",
        period="2025Q4",
        revenue=Decimal("35000000000"),
        net_income=Decimal("18000000000"),
        eps=Decimal("0.89"),
        revenue_yoy=Decimal("0.80"),
        profit_yoy=Decimal("0.75"),
        source="yfinance",
    )
    assert earnings.symbol == "NVDA"
    assert earnings.period == "2025Q4"
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec api python -m pytest tests/db/test_models.py::test_stock_news_model tests/db/test_models.py::test_stock_earnings_model -v`
Expected: FAIL with ImportError (StockNews, StockEarnings not defined)

**Step 3: Write the models**

Append to `src/db/models_market_data.py` (after GeneratedReport class):

```python
class StockNews(Base):
    """Individual stock news articles from multiple sources."""
    __tablename__ = "stock_news"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(5), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # "eastmoney", "sina", "yahoo"
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_stock_news_symbol_published", "symbol", "market", "published_at"),
        UniqueConstraint('symbol', 'market', 'title', 'published_at', name='uq_stock_news_dedup'),
        {"mysql_charset": "utf8mb4"},
    )


class StockEarnings(Base):
    """Quarterly earnings data for tracked stocks."""
    __tablename__ = "stock_earnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(5), nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g. "2025Q4"
    revenue: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(20, 2), nullable=True)
    net_income: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(20, 2), nullable=True)
    eps: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 4), nullable=True)
    revenue_yoy: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 6), nullable=True)
    profit_yoy: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 6), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # "eastmoney", "yfinance"
    reported_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint('symbol', 'market', 'period', name='uq_stock_earnings_symbol_period'),
        {"mysql_charset": "utf8mb4"},
    )
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec api python -m pytest tests/db/test_models.py::test_stock_news_model tests/db/test_models.py::test_stock_earnings_model -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/db/models_market_data.py tests/db/test_models.py
git commit -m "feat: add StockNews and StockEarnings database models"
```

---

### Task 2: Add NewsCollector

**Files:**
- Create: `src/collectors/structured/news_collector.py`
- Create: `tests/collectors/test_news_collector.py`

**Step 1: Write the failing test**

Create `tests/collectors/test_news_collector.py`:

```python
"""Tests for NewsCollector."""
import pytest
from unittest.mock import patch, MagicMock
from src.collectors.structured.news_collector import NewsCollector, StockNewsItem


def test_collector_name():
    collector = NewsCollector()
    assert collector.name == "news_collector"


def test_fetch_cn_news_returns_list():
    """Test that CN news fetching returns a list of StockNewsItem."""
    collector = NewsCollector()
    with patch("src.collectors.structured.news_collector.ak") as mock_ak:
        import pandas as pd
        mock_ak.stock_news_em.return_value = pd.DataFrame({
            "新闻标题": ["Test headline"],
            "新闻内容": ["Summary text"],
            "发布时间": ["2026-02-20 10:00:00"],
            "新闻链接": ["https://example.com"],
        })
        result = collector.fetch_news_cn("000001")
        assert len(result) == 1
        assert isinstance(result[0], StockNewsItem)
        assert result[0].title == "Test headline"
        assert result[0].source == "eastmoney"


def test_fetch_us_news_returns_list():
    """Test that US news fetching returns a list of StockNewsItem."""
    collector = NewsCollector()
    with patch("src.collectors.structured.news_collector.yfinance.Ticker") as mock_ticker_cls:
        mock_ticker = MagicMock()
        mock_ticker.news = [
            {
                "title": "NVIDIA beats earnings",
                "publisher": "Yahoo Finance",
                "link": "https://example.com/nvda",
                "providerPublishTime": 1708416000,  # timestamp
            }
        ]
        mock_ticker_cls.return_value = mock_ticker
        result = collector.fetch_news_us("NVDA")
        assert len(result) >= 1
        assert result[0].source == "yahoo"


def test_fetch_all_news():
    """Test fetch_all with multiple symbols."""
    collector = NewsCollector()
    with patch.object(collector, "fetch_news_cn", return_value=[]) as mock_cn, \
         patch.object(collector, "fetch_news_us", return_value=[]) as mock_us:
        pairs = [("NVDA", "US"), ("000001", "CN"), ("01810", "HK")]
        result = collector.fetch_all(pairs)
        assert isinstance(result, list)
        mock_us.assert_called_once()  # NVDA
        mock_cn.assert_called_once()  # 000001
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec api python -m pytest tests/collectors/test_news_collector.py -v`
Expected: FAIL with ImportError

**Step 3: Write the NewsCollector**

Create `src/collectors/structured/news_collector.py`:

```python
"""News collector for individual stock news from multiple sources."""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import yfinance

logger = logging.getLogger(__name__)

try:
    import akshare as ak
except ImportError:
    ak = None


@dataclass
class StockNewsItem:
    """Data class for a single news article."""
    symbol: str
    market: str
    title: str
    summary: Optional[str] = None
    source: str = "unknown"
    url: Optional[str] = None
    published_at: Optional[datetime] = None


class NewsCollector:
    """Collects stock news from EastMoney (CN), Yahoo Finance (US/HK), and Sina."""

    @property
    def name(self) -> str:
        return "news_collector"

    def fetch_news_cn(self, symbol: str) -> List[StockNewsItem]:
        """Fetch news for a CN stock from EastMoney via akshare."""
        if ak is None:
            logger.warning("akshare not installed, skipping CN news")
            return []
        try:
            df = ak.stock_news_em(symbol=symbol)
            if df is None or df.empty:
                return []
            items = []
            for _, row in df.head(10).iterrows():
                published_at = None
                raw_time = row.get("发布时间") or row.get("新闻时间")
                if raw_time:
                    try:
                        published_at = datetime.strptime(str(raw_time), "%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        published_at = datetime.now()

                items.append(StockNewsItem(
                    symbol=symbol,
                    market="CN",
                    title=str(row.get("新闻标题", "")),
                    summary=str(row.get("新闻内容", ""))[:500] if row.get("新闻内容") else None,
                    source="eastmoney",
                    url=str(row.get("新闻链接", "")) if row.get("新闻链接") else None,
                    published_at=published_at,
                ))
            return items
        except Exception as e:
            logger.warning("Failed to fetch CN news for %s: %s", symbol, e)
            return []

    def fetch_news_us(self, symbol: str) -> List[StockNewsItem]:
        """Fetch news for a US/HK stock from Yahoo Finance."""
        try:
            ticker = yfinance.Ticker(symbol)
            news_list = ticker.news or []
            items = []
            for article in news_list[:10]:
                published_at = None
                ts = article.get("providerPublishTime")
                if ts:
                    try:
                        published_at = datetime.fromtimestamp(int(ts))
                    except (ValueError, TypeError, OSError):
                        published_at = datetime.now()

                title = article.get("title", "")
                if not title:
                    continue

                items.append(StockNewsItem(
                    symbol=symbol,
                    market="US",
                    title=title,
                    summary=None,  # Yahoo doesn't always provide summary
                    source="yahoo",
                    url=article.get("link"),
                    published_at=published_at,
                ))
            return items
        except Exception as e:
            logger.warning("Failed to fetch US news for %s: %s", symbol, e)
            return []

    def fetch_news_hk(self, symbol: str) -> List[StockNewsItem]:
        """Fetch news for HK stock. Uses Yahoo Finance with .HK suffix."""
        yf_symbol = f"{symbol}.HK" if not symbol.endswith(".HK") else symbol
        items = self.fetch_news_us(yf_symbol)
        # Fix market to HK
        for item in items:
            item.market = "HK"
            item.symbol = symbol.replace(".HK", "")
        return items

    def fetch_all(self, pairs: List[Tuple[str, str]]) -> List[StockNewsItem]:
        """Fetch news for all given (symbol, market) pairs.

        Args:
            pairs: List of (symbol, market) tuples.

        Returns:
            Combined list of StockNewsItem from all sources.
        """
        all_news: List[StockNewsItem] = []
        for symbol, market in pairs:
            try:
                if market == "CN":
                    items = self.fetch_news_cn(symbol)
                elif market == "HK":
                    items = self.fetch_news_hk(symbol)
                else:
                    items = self.fetch_news_us(symbol)
                all_news.extend(items)
            except Exception as e:
                logger.warning("News fetch failed for %s.%s: %s", symbol, market, e)
        return all_news
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec api python -m pytest tests/collectors/test_news_collector.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/collectors/structured/news_collector.py tests/collectors/test_news_collector.py
git commit -m "feat: add NewsCollector for multi-source stock news"
```

---

### Task 3: Add EarningsCollector

**Files:**
- Create: `src/collectors/structured/earnings_collector.py`
- Create: `tests/collectors/test_earnings_collector.py`

**Step 1: Write the failing test**

Create `tests/collectors/test_earnings_collector.py`:

```python
"""Tests for EarningsCollector."""
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from src.collectors.structured.earnings_collector import EarningsCollector, EarningsData


def test_collector_name():
    collector = EarningsCollector()
    assert collector.name == "earnings_collector"


def test_fetch_us_earnings():
    """Test that US earnings fetching returns EarningsData list."""
    collector = EarningsCollector()
    with patch("src.collectors.structured.earnings_collector.yfinance.Ticker") as mock_cls:
        import pandas as pd
        mock_ticker = MagicMock()
        mock_ticker.quarterly_income_stmt = pd.DataFrame(
            {"2025-12-31": [35000000000, 18000000000]},
            index=["Total Revenue", "Net Income"],
        )
        mock_ticker.quarterly_earnings = pd.DataFrame(
            {"Reported EPS": [0.89]},
            index=pd.DatetimeIndex(["2025-12-31"]),
        )
        mock_cls.return_value = mock_ticker
        result = collector.fetch_earnings_us("NVDA")
        assert len(result) >= 1
        assert isinstance(result[0], EarningsData)


def test_fetch_all():
    """Test fetch_all with multiple symbols."""
    collector = EarningsCollector()
    with patch.object(collector, "fetch_earnings_us", return_value=[]) as mock_us, \
         patch.object(collector, "fetch_earnings_cn", return_value=[]) as mock_cn:
        pairs = [("NVDA", "US"), ("000001", "CN")]
        result = collector.fetch_all(pairs)
        assert isinstance(result, list)
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec api python -m pytest tests/collectors/test_earnings_collector.py -v`
Expected: FAIL with ImportError

**Step 3: Write the EarningsCollector**

Create `src/collectors/structured/earnings_collector.py`:

```python
"""Earnings collector for quarterly financial data."""
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

import yfinance

logger = logging.getLogger(__name__)

try:
    import akshare as ak
except ImportError:
    ak = None


@dataclass
class EarningsData:
    """Data class for quarterly earnings."""
    symbol: str
    market: str
    period: str  # e.g. "2025Q4"
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    eps: Optional[float] = None
    revenue_yoy: Optional[float] = None
    profit_yoy: Optional[float] = None
    source: str = "unknown"
    reported_at: Optional[datetime] = None


def _date_to_quarter(dt) -> str:
    """Convert a date/datetime to period string like '2025Q4'."""
    if hasattr(dt, 'month'):
        q = (dt.month - 1) // 3 + 1
        return f"{dt.year}Q{q}"
    return str(dt)


class EarningsCollector:
    """Collects quarterly earnings data from yfinance and akshare."""

    @property
    def name(self) -> str:
        return "earnings_collector"

    def fetch_earnings_us(self, symbol: str) -> List[EarningsData]:
        """Fetch quarterly earnings for a US/HK stock via yfinance."""
        try:
            ticker = yfinance.Ticker(symbol)
            income = ticker.quarterly_income_stmt
            if income is None or income.empty:
                return []

            results = []
            for col in income.columns[:4]:  # Last 4 quarters
                period = _date_to_quarter(col)
                revenue = None
                net_income = None

                if "Total Revenue" in income.index:
                    val = income.loc["Total Revenue", col]
                    revenue = float(val) if val is not None else None
                if "Net Income" in income.index:
                    val = income.loc["Net Income", col]
                    net_income = float(val) if val is not None else None

                # EPS from quarterly_earnings
                eps = None
                try:
                    qe = ticker.quarterly_earnings
                    if qe is not None and not qe.empty and "Reported EPS" in qe.columns:
                        # Find matching quarter
                        for idx in qe.index:
                            if _date_to_quarter(idx) == period:
                                eps = float(qe.loc[idx, "Reported EPS"])
                                break
                except Exception:
                    pass

                results.append(EarningsData(
                    symbol=symbol,
                    market="US",
                    period=period,
                    revenue=revenue,
                    net_income=net_income,
                    eps=eps,
                    source="yfinance",
                    reported_at=col if isinstance(col, datetime) else None,
                ))

            # Calculate YoY if we have enough quarters
            self._calculate_yoy(results)
            return results

        except Exception as e:
            logger.warning("Failed to fetch US earnings for %s: %s", symbol, e)
            return []

    def fetch_earnings_cn(self, symbol: str) -> List[EarningsData]:
        """Fetch quarterly earnings for a CN stock via akshare."""
        if ak is None:
            logger.warning("akshare not installed, skipping CN earnings")
            return []
        try:
            # Try financial abstract
            df = ak.stock_financial_abstract_ths(symbol=symbol)
            if df is None or df.empty:
                return []

            results = []
            for _, row in df.head(8).iterrows():
                period_raw = str(row.get("报告期", ""))
                if not period_raw:
                    continue

                # Convert "2025-12-31" to "2025Q4"
                try:
                    dt = datetime.strptime(period_raw[:10], "%Y-%m-%d")
                    period = _date_to_quarter(dt)
                except (ValueError, TypeError):
                    period = period_raw

                revenue = float(row["营业总收入"]) if "营业总收入" in row and row["营业总收入"] else None
                net_income = float(row["净利润"]) if "净利润" in row and row["净利润"] else None
                eps = float(row["基本每股收益"]) if "基本每股收益" in row and row["基本每股收益"] else None

                results.append(EarningsData(
                    symbol=symbol,
                    market="CN",
                    period=period,
                    revenue=revenue,
                    net_income=net_income,
                    eps=eps,
                    source="eastmoney",
                ))

            self._calculate_yoy(results)
            return results

        except Exception as e:
            logger.warning("Failed to fetch CN earnings for %s: %s", symbol, e)
            return []

    def fetch_earnings_hk(self, symbol: str) -> List[EarningsData]:
        """Fetch HK stock earnings via yfinance with .HK suffix."""
        yf_symbol = f"{symbol}.HK" if not symbol.endswith(".HK") else symbol
        items = self.fetch_earnings_us(yf_symbol)
        for item in items:
            item.market = "HK"
            item.symbol = symbol.replace(".HK", "")
        return items

    def fetch_all(self, pairs: List[Tuple[str, str]]) -> List[EarningsData]:
        """Fetch earnings for all given (symbol, market) pairs."""
        all_earnings: List[EarningsData] = []
        for symbol, market in pairs:
            try:
                if market == "CN":
                    items = self.fetch_earnings_cn(symbol)
                elif market == "HK":
                    items = self.fetch_earnings_hk(symbol)
                else:
                    items = self.fetch_earnings_us(symbol)
                all_earnings.extend(items)
            except Exception as e:
                logger.warning("Earnings fetch failed for %s.%s: %s", symbol, market, e)
        return all_earnings

    @staticmethod
    def _calculate_yoy(results: List[EarningsData]) -> None:
        """Calculate YoY growth by matching same quarter across years."""
        by_quarter: dict = {}
        for r in results:
            if not r.period:
                continue
            # e.g. "2025Q4" -> quarter_key = "Q4"
            q_key = r.period[-2:]  # "Q4"
            year = r.period[:4]
            by_quarter.setdefault(q_key, {})[year] = r

        for q_key, year_map in by_quarter.items():
            years = sorted(year_map.keys())
            for i in range(1, len(years)):
                curr = year_map[years[i]]
                prev = year_map[years[i - 1]]
                if curr.revenue and prev.revenue and prev.revenue != 0:
                    curr.revenue_yoy = (curr.revenue - prev.revenue) / abs(prev.revenue)
                if curr.net_income and prev.net_income and prev.net_income != 0:
                    curr.profit_yoy = (curr.net_income - prev.net_income) / abs(prev.net_income)
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec api python -m pytest tests/collectors/test_earnings_collector.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/collectors/structured/earnings_collector.py tests/collectors/test_earnings_collector.py
git commit -m "feat: add EarningsCollector for quarterly financial data"
```

---

### Task 4: Add storage methods and register collectors

**Files:**
- Modify: `src/services/storage.py` (add `store_news` and `store_earnings` methods)
- Modify: `src/collectors/registry.py` (register new collectors)

**Step 1: Write the failing test**

Add to `tests/services/test_storage.py`:

```python
def test_store_news(db_session):
    """Test storing StockNewsItem objects."""
    from src.services.storage import StorageService
    from src.collectors.structured.news_collector import StockNewsItem
    from datetime import datetime

    storage = StorageService(db_session)
    items = [
        StockNewsItem(
            symbol="NVDA", market="US", title="Test News",
            summary="Test summary", source="yahoo",
            url="https://example.com", published_at=datetime(2026, 2, 20),
        )
    ]
    count = storage.store_news(items)
    assert count == 1


def test_store_earnings(db_session):
    """Test storing EarningsData objects."""
    from src.services.storage import StorageService
    from src.collectors.structured.earnings_collector import EarningsData

    storage = StorageService(db_session)
    items = [
        EarningsData(
            symbol="NVDA", market="US", period="2025Q4",
            revenue=35000000000, net_income=18000000000,
            eps=0.89, source="yfinance",
        )
    ]
    count = storage.store_earnings(items)
    assert count == 1
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec api python -m pytest tests/services/test_storage.py::test_store_news tests/services/test_storage.py::test_store_earnings -v`
Expected: FAIL (AttributeError: store_news not found)

**Step 3: Add storage methods**

In `src/services/storage.py`, add after the last `store_*` method:

```python
    def store_news(self, news_items: list) -> int:
        """Store StockNewsItem objects. Deduplicates on (symbol, market, title, published_at)."""
        from src.db.models_market_data import StockNews
        rows = []
        for item in news_items:
            if not item.title:
                continue
            rows.append({
                "symbol": item.symbol,
                "market": item.market,
                "title": item.title[:500],
                "summary": item.summary[:2000] if item.summary else None,
                "source": item.source,
                "url": item.url[:1000] if item.url else None,
                "published_at": item.published_at or datetime.now(),
            })
        return self._mysql_upsert(StockNews, rows, ["symbol", "market", "title", "published_at"])

    def store_earnings(self, earnings_items: list) -> int:
        """Store EarningsData objects. Deduplicates on (symbol, market, period)."""
        from src.db.models_market_data import StockEarnings
        rows = []
        for item in earnings_items:
            if not item.period:
                continue
            rows.append({
                "symbol": item.symbol,
                "market": item.market,
                "period": item.period,
                "revenue": Decimal(str(item.revenue)) if item.revenue else None,
                "net_income": Decimal(str(item.net_income)) if item.net_income else None,
                "eps": Decimal(str(item.eps)) if item.eps else None,
                "revenue_yoy": Decimal(str(item.revenue_yoy)) if item.revenue_yoy else None,
                "profit_yoy": Decimal(str(item.profit_yoy)) if item.profit_yoy else None,
                "source": item.source,
                "reported_at": item.reported_at,
            })
        return self._mysql_upsert(StockEarnings, rows, ["symbol", "market", "period"])
```

Add import at top of storage.py: `from datetime import datetime`

Also register the collectors in `src/collectors/registry.py` `_auto_register_collectors`:

```python
        try:
            from src.collectors.structured.news_collector import NewsCollector
            self.register(
                NewsCollector,
                name="news",
                description="Stock news from EastMoney, Yahoo Finance, and Sina",
            )
        except ImportError as e:
            logger.warning(f"Could not import NewsCollector: {e}")

        try:
            from src.collectors.structured.earnings_collector import EarningsCollector
            self.register(
                EarningsCollector,
                name="earnings",
                description="Quarterly earnings data from yfinance and akshare",
            )
        except ImportError as e:
            logger.warning(f"Could not import EarningsCollector: {e}")
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec api python -m pytest tests/services/test_storage.py::test_store_news tests/services/test_storage.py::test_store_earnings -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/services/storage.py src/collectors/registry.py
git commit -m "feat: add storage methods and register news/earnings collectors"
```

---

### Task 5: Add scheduled news/earnings collection to scheduler

**Files:**
- Modify: `src/scheduler/scheduler.py`

**Step 1: Add the collection functions**

In `src/scheduler/scheduler.py`, add after `_collect_alternative_data`:

```python
def _collect_news_data() -> None:
    """Collect stock news for all holdings and watchlist symbols."""
    logger.info("Running scheduled news collection")
    try:
        from src.collectors.structured.news_collector import NewsCollector
        from src.db.database import SessionLocal
        from src.db.models import Holding, HoldingStatus, Watchlist
        from src.services.storage import StorageService

        db = SessionLocal()
        try:
            # Get all symbols to fetch news for
            holdings = db.query(Holding).filter(
                Holding.status == HoldingStatus.ACTIVE
            ).all()
            pairs = [(h.symbol, h.market.value) for h in holdings if h.symbol != "CASH"]

            watchlist_items = db.query(Watchlist).all()
            pairs.extend([(w.symbol, w.market.value) for w in watchlist_items])
            pairs = list(set(pairs))

            if pairs:
                collector = NewsCollector()
                news_items = collector.fetch_all(pairs)
                storage = StorageService(db)
                n = storage.store_news(news_items)
                logger.info(f"Stored {n} news articles for {len(pairs)} symbols")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"News collection failed: {e}")


def _collect_earnings_data() -> None:
    """Collect quarterly earnings for all holdings and watchlist symbols."""
    logger.info("Running scheduled earnings collection")
    try:
        from src.collectors.structured.earnings_collector import EarningsCollector
        from src.db.database import SessionLocal
        from src.db.models import Holding, HoldingStatus, Watchlist
        from src.services.storage import StorageService

        db = SessionLocal()
        try:
            holdings = db.query(Holding).filter(
                Holding.status == HoldingStatus.ACTIVE
            ).all()
            pairs = [(h.symbol, h.market.value) for h in holdings if h.symbol != "CASH"]

            watchlist_items = db.query(Watchlist).all()
            pairs.extend([(w.symbol, w.market.value) for w in watchlist_items])
            pairs = list(set(pairs))

            if pairs:
                collector = EarningsCollector()
                earnings = collector.fetch_all(pairs)
                storage = StorageService(db)
                n = storage.store_earnings(earnings)
                logger.info(f"Stored {n} earnings records for {len(pairs)} symbols")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Earnings collection failed: {e}")
```

**Step 2: Add to schedules**

Add to `DEFAULT_SCHEDULE`:
```python
    "collect_news":             {"hour": 16, "minute": 30},    # Before market data
```

Add to `WEEKLY_SCHEDULE`:
```python
    "collect_earnings_sat":     {"day_of_week": 5, "hour": 6, "minute": 0},    # Saturday 06:00
```

Add to `_DEFAULT_FUNCS`:
```python
    "collect_news": _collect_news_data,
```

Add to `_WEEKLY_FUNCS`:
```python
    "collect_earnings_sat": _collect_earnings_data,
```

Add to `task_map` in `trigger_task`:
```python
        "collect_news": _collect_news_data,
        "collect_earnings": _collect_earnings_data,
```

**Step 3: Run existing scheduler tests**

Run: `docker compose exec api python -m pytest tests/scheduler/ -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/scheduler/scheduler.py
git commit -m "feat: schedule daily news and weekly earnings collection"
```

---

### Task 6: Add news/earnings context helpers to report_generator

**Files:**
- Modify: `src/services/report_generator.py`

**Step 1: Add helper functions for fetching news and earnings**

Add these helper functions in the "Enhanced Data Fetching Helpers" section (around line 570):

```python
def _get_recent_news_static(
    db: Session, symbol: str, market_value: str, days: int = 7, limit: int = 5
) -> List[Dict[str, Any]]:
    """Get recent news articles for a symbol."""
    from src.db.models_market_data import StockNews
    since = date.today() - timedelta(days=days)
    news = (
        db.query(StockNews)
        .filter(
            StockNews.symbol == symbol,
            StockNews.market == market_value,
            StockNews.published_at >= datetime.combine(since, datetime.min.time()),
        )
        .order_by(StockNews.published_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "title": n.title,
            "summary": n.summary[:200] if n.summary else None,
            "source": n.source,
            "date": n.published_at.strftime("%m-%d") if n.published_at else None,
        }
        for n in news
    ]


def _get_recent_earnings_static(
    db: Session, symbol: str, market_value: str, limit: int = 2
) -> List[Dict[str, Any]]:
    """Get recent quarterly earnings for a symbol."""
    from src.db.models_market_data import StockEarnings
    earnings = (
        db.query(StockEarnings)
        .filter(
            StockEarnings.symbol == symbol,
            StockEarnings.market == market_value,
        )
        .order_by(StockEarnings.period.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "period": e.period,
            "revenue": float(e.revenue) if e.revenue else None,
            "net_income": float(e.net_income) if e.net_income else None,
            "eps": float(e.eps) if e.eps else None,
            "revenue_yoy": float(e.revenue_yoy) if e.revenue_yoy else None,
            "profit_yoy": float(e.profit_yoy) if e.profit_yoy else None,
        }
        for e in earnings
    ]
```

**Step 2: No test needed — these are internal helpers used in the next steps**

**Step 3: Commit**

```bash
git add src/services/report_generator.py
git commit -m "feat: add news/earnings context helpers for report generation"
```

---

### Task 7: Enhance holding AI prompts with news/earnings context

**Files:**
- Modify: `src/services/report_generator.py`

This is the core change. We modify `_get_holding_ai` (daily, line ~1250) and `_get_weekly_holding_ai` (weekly, line ~1834) to include news and earnings context in the LLM prompt.

**Step 1: Enhance the system prompts**

Replace `DAILY_HOLDING_SYSTEM_PROMPT` (line 52):

```python
DAILY_HOLDING_SYSTEM_PROMPT = """你是一位专业投资顾问。请对以下持仓进行深度分析。

重要要求：
1. 必须引用具体的新闻事件、财报数据点或技术指标来支持你的观点
2. 禁止使用"需要关注"、"保持谨慎"等模糊表述，给出明确结论
3. 结合当前宏观环境和行业趋势给出具体建议
4. 如果有最近的新闻或财报数据，必须在分析中体现

要求严格按JSON格式回复，不要包含任何其他文字：
{
  "ai_comment": "2-3句话的结论+简要理由，必须引用至少一个具体数据点或事件",
  "action": "hold/add/reduce/sell 之一",
  "ai_detail": "详细分析报告，markdown格式，包含：\\n## 近期动态\\n引用具体新闻或事件...\\n## 基本面\\n引用具体财报数据...\\n## 技术面\\n引用具体指标...\\n## 操作建议\\n明确的操作建议和理由..."
}"""
```

Replace `WEEKLY_HOLDING_SYSTEM_PROMPT` (line 73):

```python
WEEKLY_HOLDING_SYSTEM_PROMPT = """你是一位专业投资顾问，进行中长期持仓分析。

重要要求：
1. 必须引用具体的新闻事件、财报数据或市场数据来支持你的观点
2. 禁止使用模糊表述，给出有时效性的明确判断
3. 评估持仓逻辑在当前环境下是否仍然成立
4. 结合最新的行业动态和公司事件给出仓位建议

要求严格按JSON格式回复：
{
  "ai_comment": "2-3句话的中长期观点，必须引用具体事件或数据点支持，给出明确仓位建议",
  "action": "hold/add/reduce/sell 之一",
  "ai_detail": "详细分析报告，markdown格式，包含：\\n## 近期重要事件\\n引用具体新闻...\\n## 财报分析\\n引用具体财报数据...\\n## 持仓逻辑回顾\\n当前环境下是否成立...\\n## 中期催化剂\\n...\\n## 风险因素\\n具体风险而非泛泛而谈...\\n## 仓位建议\\n明确加减仓比例建议..."
}"""
```

Replace `OPPORTUNITY_SYSTEM_PROMPT` (line 63):

```python
OPPORTUNITY_SYSTEM_PROMPT = """你是一位专业投资顾问。分析以下标的的投资机会。

重要要求：
1. 必须引用具体的新闻事件、财报数据或技术指标
2. 给出明确的操作建议（买入/观望/回避），不要模棱两可
3. 说明具体的入场条件或价位

要求严格按JSON格式回复：
{
  "reason": "1-2句话说明机会原因，必须引用具体数据",
  "detail": "markdown格式详细分析，包括近期事件、估值分析、操作建议",
  "timeframe": "长期 或 短期",
  "signal_type": "超跌反弹/估值低位/资金流入/技术突破/高成长低估值 之一"
}"""
```

Replace `DAILY_SUMMARY_SYSTEM_PROMPT` (line 61):

```python
DAILY_SUMMARY_SYSTEM_PROMPT = """你是一位专业投资顾问。根据以下持仓数据，生成一句话总结（50字以内），必须提及最值得关注的具体事件或数据变化，不要使用泛泛的描述。只返回总结文字，不要任何其他格式。"""
```

Replace `WEEKLY_SUMMARY_SYSTEM_PROMPT` (line 82):

```python
WEEKLY_SUMMARY_SYSTEM_PROMPT = """你是一位专业投资顾问。根据以下本周市场和持仓数据，生成一段总结（150字以内），必须：
1. 提及本周最重要的市场事件或数据变化
2. 点评表现最好和最差的持仓
3. 给出下周操作的具体方向
不要使用"保持关注"等模糊表述。只返回总结文字，不要任何其他格式。"""
```

**Step 2: Inject news/earnings into `_get_holding_ai` (daily)**

In `DailyReportGenerator._get_holding_ai` method (~line 1250), after the existing data gathering (fundamentals, ETF NAV, northbound, signals) and before the `lines = [...]` prompt building, add:

```python
        # Get recent news and earnings
        news = _get_recent_news_static(self.db, symbol, market_value, days=7, limit=5)
        earnings = _get_recent_earnings_static(self.db, symbol, market_value, limit=2)
```

Then in the prompt building section, after signals but before `user_msg = "\n".join(lines)`, add:

```python
        # Recent news
        if news:
            lines.append("")
            lines.append("== 近期新闻 ==")
            for n in news:
                date_str = f"[{n['date']}] " if n.get('date') else ""
                lines.append(f"  - {date_str}{n['title']}")
                if n.get('summary'):
                    lines.append(f"    摘要: {n['summary']}")

        # Recent earnings
        if earnings:
            lines.append("")
            lines.append("== 近期财报 ==")
            for e in earnings:
                parts = [f"{e['period']}:"]
                if e.get('revenue'):
                    parts.append(f"营收{e['revenue']/1e8:.1f}亿" if e['revenue'] > 1e8 else f"营收{e['revenue']:.0f}")
                if e.get('net_income'):
                    parts.append(f"净利{e['net_income']/1e8:.1f}亿" if e['net_income'] > 1e8 else f"净利{e['net_income']:.0f}")
                if e.get('eps'):
                    parts.append(f"EPS {e['eps']:.2f}")
                if e.get('revenue_yoy') is not None:
                    parts.append(f"营收同比{e['revenue_yoy']*100:+.1f}%")
                if e.get('profit_yoy') is not None:
                    parts.append(f"利润同比{e['profit_yoy']*100:+.1f}%")
                lines.append("  " + " | ".join(parts))
```

**Step 3: Inject news/earnings into `_get_weekly_holding_ai`**

Same pattern in `WeeklyReportGenerator._get_weekly_holding_ai` (~line 1834). After the existing data gathering, add:

```python
        # Get recent news and earnings
        news = _get_recent_news_static(self.db, symbol, market_value, days=14, limit=5)
        earnings = _get_recent_earnings_static(self.db, symbol, market_value, limit=2)
```

Then in the prompt building, after signals section and before `user_msg = "\n".join(lines)`, add the same news/earnings block as Step 2.

**Step 4: Inject news/earnings into `_get_opportunity_ai_static`**

In the `_get_opportunity_ai_static` function (~line 446), after the existing data gathering and before `user_msg = "\n".join(lines)`, fetch and inject news/earnings.

After line `lines.append(f"机会信号: {', '.join(opp_signals)}")` add:

```python
    # Recent news
    news = _get_recent_news_static(
        db if 'db' not in dir() else None,
        opp_entry["symbol"], opp_entry["market"], days=7, limit=3
    )
```

Wait — `_get_opportunity_ai_static` doesn't have a `db` parameter. We need to pass it. Since `_scan_opportunities_static` already has `db`, we need to pass `db` to `_get_opportunity_ai_static`.

Modify `_get_opportunity_ai_static` signature to add `db: Session` as the second parameter:

```python
def _get_opportunity_ai_static(
    llm: LLMClient,
    db: Session,  # ADD THIS
    opp_entry: Dict[str, Any],
    ...
```

Update the call site in `_scan_opportunities_static` (~line 429):

```python
        ai_result = _get_opportunity_ai_static(
            llm, db, opp_entry, item, fundamental, pe, revenue_growth, change_30d, opp_signals,
            enhanced_data
        )
```

Then add news/earnings injection in `_get_opportunity_ai_static`, after `lines.append(f"机会信号: {', '.join(opp_signals)}")`:

```python
    # Recent news and earnings
    news = _get_recent_news_static(db, opp_entry["symbol"], opp_entry["market"], days=7, limit=3)
    earnings = _get_recent_earnings_static(db, opp_entry["symbol"], opp_entry["market"], limit=2)

    if news:
        lines.append("")
        lines.append("== 近期新闻 ==")
        for n in news:
            date_str = f"[{n['date']}] " if n.get('date') else ""
            lines.append(f"  - {date_str}{n['title']}")

    if earnings:
        lines.append("")
        lines.append("== 近期财报 ==")
        for e in earnings:
            parts = [f"{e['period']}:"]
            if e.get('revenue'):
                parts.append(f"营收{e['revenue']/1e8:.1f}亿" if e['revenue'] > 1e8 else f"营收{e['revenue']:.0f}")
            if e.get('revenue_yoy') is not None:
                parts.append(f"营收同比{e['revenue_yoy']*100:+.1f}%")
            if e.get('profit_yoy') is not None:
                parts.append(f"利润同比{e['profit_yoy']*100:+.1f}%")
            lines.append("  " + " | ".join(parts))
```

**Step 5: Run existing tests**

Run: `docker compose exec api python -m pytest tests/services/test_weekly_report.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/services/report_generator.py
git commit -m "feat: enhance LLM prompts with news/earnings context and require specific analysis"
```

---

### Task 8: Analyze ALL watchlist stocks in weekly report (not just triggered ones)

**Files:**
- Modify: `src/services/report_generator.py`

Currently `_scan_opportunities_static` only analyzes watchlist stocks that trigger opportunity signals (pullback, low PE, etc.). We need to also produce analysis for every watchlist stock.

**Step 1: Add `_analyze_all_watchlist_static` function**

Add after `_scan_opportunities_static`:

```python
def _analyze_all_watchlist_static(
    db: Session, llm: LLMClient, user_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Analyze EVERY watchlist stock with deep context, regardless of signal triggers.

    This replaces the opportunity-only scan for weekly reports.
    Returns a list of dicts with full analysis for each watchlist item.
    """
    query = db.query(Watchlist)
    if user_id is not None:
        query = query.filter(Watchlist.user_id == user_id)
    watchlist_items = query.all()
    if not watchlist_items:
        return []

    analyses: List[Dict[str, Any]] = []

    for item in watchlist_items:
        market_value = item.market.value if isinstance(item.market, Market) else item.market
        fundamental = _get_latest_fundamental_static(db, item.symbol, market_value)

        # Get 60-day quotes
        quotes_60d = _get_quotes_for_period(db, item.symbol, item.market, 60)

        # Current price
        price = None
        if quotes_60d and quotes_60d[-1].close is not None:
            price = float(quotes_60d[-1].close)

        # Fundamentals
        pe = float(fundamental.pe_ratio) if fundamental and fundamental.pe_ratio else None
        pb = float(fundamental.pb_ratio) if fundamental and fundamental.pb_ratio else None
        revenue_growth = float(fundamental.revenue_growth) if fundamental and fundamental.revenue_growth else None
        target_price = float(fundamental.target_price) if fundamental and fundamental.target_price else None
        analyst_rating = fundamental.analyst_rating if fundamental else None
        name = fundamental.name if fundamental and fundamental.name else item.symbol

        # Technical indicators
        change_5d = _calc_price_change(quotes_60d, 5)
        change_20d = _calc_price_change(quotes_60d, 20)
        change_60d = _calc_price_change(quotes_60d, 60)
        ma20 = _calc_moving_average(quotes_60d, 20)
        ma60 = _calc_moving_average(quotes_60d, 60)
        volume_change = _calc_volume_change(quotes_60d)
        high_60d, low_60d = _get_high_low_60d(quotes_60d)

        # PE percentile
        pe_percentile = None
        if pe and pe > 0:
            pe_percentile = _get_pe_percentile(db, item.symbol, market_value, pe)

        # Sector data
        sector_name = item.theme
        sector_perf = _get_sector_performance_static(db, sector_name) if sector_name else None
        sector_flow = _get_sector_flow_static(db, sector_name, days=14) if sector_name else None

        # Northbound holding (for A-shares)
        nb_holding = None
        if item.market == Market.CN:
            nb_holding = _get_northbound_holding_static(db, item.symbol, days=28)

        # News and earnings
        news = _get_recent_news_static(db, item.symbol, market_value, days=14, limit=5)
        earnings = _get_recent_earnings_static(db, item.symbol, market_value, limit=2)

        # Detect opportunity signals (keep for backward compat)
        change_30d = None
        if len(quotes_60d) >= 20:
            oldest_idx = max(0, len(quotes_60d) - 30)
            oldest = quotes_60d[oldest_idx].close
            newest = quotes_60d[-1].close
            if oldest and newest and oldest != 0:
                change_30d = float((newest - oldest) / oldest)

        upside = None
        if price and price > 0 and target_price:
            upside = (target_price - price) / price

        opp_signals = _detect_opportunity(pe, revenue_growth, change_30d, upside)

        # Build LLM prompt
        lines = [
            f"标的: {name} ({item.symbol}.{market_value})",
            f"市场: {market_value} | 主题: {item.theme}",
            f"跟踪理由: {item.reason}",
        ]

        if price:
            lines.append(f"当前价: {price:.2f}")

        # Technical
        lines.append("")
        lines.append("== 技术面 ==")
        trend_parts = []
        if change_5d is not None:
            trend_parts.append(f"5日:{change_5d:+.1f}%")
        if change_20d is not None:
            trend_parts.append(f"20日:{change_20d:+.1f}%")
        if change_60d is not None:
            trend_parts.append(f"60日:{change_60d:+.1f}%")
        if trend_parts:
            lines.append("价格走势: " + ", ".join(trend_parts))

        if ma20 is not None and ma60 is not None and price:
            ma_status = "多头排列" if price > ma20 > ma60 else ("空头排列" if price < ma20 < ma60 else "震荡")
            lines.append(f"均线: MA20={ma20:.2f}, MA60={ma60:.2f} ({ma_status})")

        if volume_change is not None:
            vol_desc = "放量" if volume_change > 30 else ("缩量" if volume_change < -30 else "平稳")
            lines.append(f"成交量: 近5日vs前20日 {volume_change:+.0f}% ({vol_desc})")

        if high_60d is not None and low_60d is not None and price:
            position = (price - low_60d) / (high_60d - low_60d) * 100 if high_60d != low_60d else 50
            lines.append(f"60日区间: {low_60d:.2f}-{high_60d:.2f} (当前{position:.0f}%位置)")

        # Fundamentals
        lines.append("")
        lines.append("== 基本面 ==")
        if pe is not None:
            pe_str = f"PE: {pe:.1f}"
            if pe_percentile is not None:
                pe_str += f" (历史{pe_percentile}%分位)"
            lines.append(pe_str)
        if pb is not None:
            lines.append(f"PB: {pb:.2f}")
        if revenue_growth is not None:
            lines.append(f"营收增长: {revenue_growth * 100:.1f}%")
        if target_price and price:
            up = (target_price - price) / price * 100
            lines.append(f"目标价: {target_price:.2f} (空间{up:+.1f}%)")
        if analyst_rating:
            lines.append(f"分析师评级: {analyst_rating}")

        # Sector
        if sector_perf or sector_flow:
            lines.append("")
            lines.append("== 所属板块 ==")
            if sector_perf:
                lines.append(f"板块涨跌: {sector_perf.get('change_pct', 0):.1f}%")
            if sector_flow:
                flow = sector_flow.get("net_inflow", 0)
                direction = sector_flow.get("direction", "")
                consecutive = sector_flow.get("consecutive_weeks", 0)
                lines.append(f"板块资金: {'流入' if flow > 0 else '流出'}{abs(flow):.1f}亿, 连续{consecutive}周{direction}")

        # Northbound
        if nb_holding:
            lines.append("")
            lines.append("== 北向资金 ==")
            if nb_holding.get("change_pct") is not None:
                cp = nb_holding["change_pct"]
                lines.append(f"28日变化: {'增持' if cp > 0 else '减持'}{abs(cp):.1f}%")

        # News
        if news:
            lines.append("")
            lines.append("== 近期新闻 ==")
            for n in news:
                date_str = f"[{n['date']}] " if n.get('date') else ""
                lines.append(f"  - {date_str}{n['title']}")
                if n.get('summary'):
                    lines.append(f"    摘要: {n['summary']}")

        # Earnings
        if earnings:
            lines.append("")
            lines.append("== 近期财报 ==")
            for e in earnings:
                parts = [f"{e['period']}:"]
                if e.get('revenue'):
                    parts.append(f"营收{e['revenue']/1e8:.1f}亿" if e['revenue'] > 1e8 else f"营收{e['revenue']:.0f}")
                if e.get('net_income'):
                    parts.append(f"净利{e['net_income']/1e8:.1f}亿" if e['net_income'] > 1e8 else f"净利{e['net_income']:.0f}")
                if e.get('revenue_yoy') is not None:
                    parts.append(f"营收同比{e['revenue_yoy']*100:+.1f}%")
                if e.get('profit_yoy') is not None:
                    parts.append(f"利润同比{e['profit_yoy']*100:+.1f}%")
                lines.append("  " + " | ".join(parts))

        if opp_signals:
            lines.append(f"\n机会信号: {', '.join(opp_signals)}")

        user_msg = "\n".join(lines)

        # Call LLM
        WATCHLIST_ANALYSIS_PROMPT = """你是一位专业投资顾问。对以下跟踪标的进行深度分析。

重要要求：
1. 必须引用具体的新闻事件、财报数据或技术指标
2. 给出明确的操作建议（买入/观望/回避）和具体理由
3. 如果建议买入，给出建议的入场价位区间
4. 禁止使用"需关注"、"保持谨慎"等模糊表述

要求严格按JSON格式回复：
{
  "verdict": "买入/观望/回避 之一",
  "ai_comment": "2-3句话的明确结论，必须引用具体数据或事件",
  "ai_detail": "markdown格式详细分析，包含：\\n## 近期动态\\n...\\n## 估值分析\\n...\\n## 技术面\\n...\\n## 投资建议\\n明确的操作建议..."
}"""

        ai_result = None
        try:
            raw = asyncio.run(
                llm.chat_with_system(
                    WATCHLIST_ANALYSIS_PROMPT, user_msg, model=ModelChoice.QUALITY,
                    max_tokens=4000,
                )
            )
            ai_result = _parse_llm_json(raw)
        except (LLMError, json.JSONDecodeError, ValueError, RuntimeError, SyntaxError) as e:
            logger.warning("Failed to get watchlist AI for %s: %s", item.symbol, e)

        entry: Dict[str, Any] = {
            "symbol": item.symbol,
            "name": name,
            "market": market_value,
            "theme": item.theme,
            "reason": item.reason,
            "current_price": price,
            "target_price": target_price,
            "signal_type": ", ".join(opp_signals) if opp_signals else "",
            "verdict": ai_result.get("verdict", "观望") if ai_result else "观望",
            "ai_comment": ai_result.get("ai_comment", "") if ai_result else "",
            "ai_detail": ai_result.get("ai_detail", "") if ai_result else "",
            "news_count": len(news),
            "has_earnings": len(earnings) > 0,
        }
        analyses.append(entry)

    return analyses
```

**Step 2: Use this in `WeeklyReportGenerator.generate`**

Replace line ~1455:
```python
        # 4. Opportunities (reuse shared helper)
        opportunities = _scan_opportunities_static(self.db, self._llm, user_id=self.user_id)
```
With:
```python
        # 4. Tracked stocks deep analysis (replaces simple opportunity scan)
        watchlist_analysis = _analyze_all_watchlist_static(self.db, self._llm, user_id=self.user_id)
```

And in the content dict (~line 1470), replace `"opportunities": opportunities,` with:
```python
            "watchlist_analysis": watchlist_analysis,
```

Keep daily report using `_scan_opportunities_static` (daily only needs opportunity alerts, not full analysis).

**Step 3: Run existing tests**

Run: `docker compose exec api python -m pytest tests/services/test_weekly_report.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/services/report_generator.py
git commit -m "feat: analyze all watchlist stocks in weekly report with deep context"
```

---

### Task 9: Add news/earnings API endpoints for watchlist page

**Files:**
- Modify: `src/api/watchlist.py`

**Step 1: Add endpoints for news and earnings data**

Add to `src/api/watchlist.py`:

```python
@router.get("/news/{symbol}")
def get_stock_news(
    symbol: str,
    market: str = "US",
    days: int = 7,
    db: Session = Depends(get_db),
):
    """Get recent news for a specific stock."""
    from src.db.models_market_data import StockNews
    since = date.today() - timedelta(days=days)
    news = (
        db.query(StockNews)
        .filter(
            StockNews.symbol == symbol,
            StockNews.market == market,
            StockNews.published_at >= datetime.combine(since, datetime.min.time()),
        )
        .order_by(StockNews.published_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": n.id,
            "title": n.title,
            "summary": n.summary,
            "source": n.source,
            "url": n.url,
            "published_at": n.published_at.isoformat() if n.published_at else None,
        }
        for n in news
    ]


@router.get("/earnings/{symbol}")
def get_stock_earnings(
    symbol: str,
    market: str = "US",
    db: Session = Depends(get_db),
):
    """Get quarterly earnings for a specific stock."""
    from src.db.models_market_data import StockEarnings
    earnings = (
        db.query(StockEarnings)
        .filter(
            StockEarnings.symbol == symbol,
            StockEarnings.market == market,
        )
        .order_by(StockEarnings.period.desc())
        .limit(8)
        .all()
    )
    return [
        {
            "id": e.id,
            "period": e.period,
            "revenue": float(e.revenue) if e.revenue else None,
            "net_income": float(e.net_income) if e.net_income else None,
            "eps": float(e.eps) if e.eps else None,
            "revenue_yoy": float(e.revenue_yoy) if e.revenue_yoy else None,
            "profit_yoy": float(e.profit_yoy) if e.profit_yoy else None,
            "source": e.source,
        }
        for e in earnings
    ]
```

Add necessary imports at top: `from datetime import date, datetime, timedelta`

**Step 2: Commit**

```bash
git add src/api/watchlist.py
git commit -m "feat: add news and earnings API endpoints for watchlist"
```

---

### Task 10: Update frontend API client

**Files:**
- Modify: `web/src/api/index.js`

**Step 1: Add API functions**

Add to the API client:

```javascript
// News & Earnings
export const getStockNews = (symbol, market = 'US', days = 7) =>
  api.get(`/watchlist/news/${symbol}`, { params: { market, days } }).then(r => r.data)
export const getStockEarnings = (symbol, market = 'US') =>
  api.get(`/watchlist/earnings/${symbol}`, { params: { market } }).then(r => r.data)
```

**Step 2: Commit**

```bash
git add web/src/api/index.js
git commit -m "feat: add news and earnings API functions to frontend client"
```

---

### Task 11: Enhance Watchlist.vue with news/earnings display

**Files:**
- Modify: `web/src/views/Watchlist.vue`

**Step 1: Add news/earnings preview to watchlist table**

Changes to `Watchlist.vue`:

1. Import the new API functions
2. Add a "detail drawer" that shows news and earnings when clicking a watchlist item
3. Rename page title from "Watchlist" to "Tracked Stocks"

In `<script setup>`:
```javascript
import { getStockNews, getStockEarnings } from '../api'

// Detail panel
const selectedItem = ref(null)
const stockNews = ref([])
const stockEarnings = ref([])
const loadingDetail = ref(false)

async function openDetail(item) {
  selectedItem.value = item
  loadingDetail.value = true
  try {
    const [news, earnings] = await Promise.all([
      getStockNews(item.symbol, item.market, 14),
      getStockEarnings(item.symbol, item.market),
    ])
    stockNews.value = news
    stockEarnings.value = earnings
  } catch (e) {
    console.error('Failed to load detail:', e)
    stockNews.value = []
    stockEarnings.value = []
  } finally {
    loadingDetail.value = false
  }
}

function closeDetail() {
  selectedItem.value = null
}

function formatNumber(val) {
  if (val == null) return '-'
  if (Math.abs(val) >= 1e8) return (val / 1e8).toFixed(1) + '亿'
  if (Math.abs(val) >= 1e4) return (val / 1e4).toFixed(1) + '万'
  return val.toFixed(2)
}

function formatPct(val) {
  if (val == null) return '-'
  return (val > 0 ? '+' : '') + (val * 100).toFixed(1) + '%'
}
```

In `<template>`, update the page header:
```html
    <div class="page-header">
      <h1>Tracked Stocks</h1>
      <p>Deep analysis of tracked stocks with news, earnings, and AI insights</p>
    </div>
```

Add click handler to table rows:
```html
<tr v-for="item in group" :key="item.id" @click="openDetail(item)" style="cursor:pointer">
```

Add detail panel after the table (before modals):
```html
    <!-- Detail Panel -->
    <div v-if="selectedItem" class="detail-panel card" style="margin-top: 16px">
      <div class="detail-header">
        <h3>{{ selectedItem.symbol }} <span class="market-tag">{{ marketLabel(selectedItem.market) }}</span></h3>
        <button class="btn-cancel" @click="closeDetail">Close</button>
      </div>
      <p class="detail-reason">{{ selectedItem.reason }}</p>

      <div v-if="loadingDetail" class="loading">Loading...</div>
      <template v-else>
        <div class="detail-grid">
          <!-- News -->
          <div class="detail-section">
            <h4>Recent News ({{ stockNews.length }})</h4>
            <div v-if="stockNews.length === 0" class="empty-hint">No recent news</div>
            <ul v-else class="news-list">
              <li v-for="n in stockNews.slice(0, 8)" :key="n.id">
                <a v-if="n.url" :href="n.url" target="_blank" class="news-title">{{ n.title }}</a>
                <span v-else class="news-title">{{ n.title }}</span>
                <span class="news-meta">{{ n.source }} · {{ formatDate(n.published_at) }}</span>
              </li>
            </ul>
          </div>
          <!-- Earnings -->
          <div class="detail-section">
            <h4>Quarterly Earnings</h4>
            <div v-if="stockEarnings.length === 0" class="empty-hint">No earnings data</div>
            <table v-else class="data-table earnings-table">
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Revenue</th>
                  <th>Net Income</th>
                  <th>EPS</th>
                  <th>Rev YoY</th>
                  <th>Profit YoY</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="e in stockEarnings.slice(0, 4)" :key="e.id">
                  <td>{{ e.period }}</td>
                  <td>{{ formatNumber(e.revenue) }}</td>
                  <td>{{ formatNumber(e.net_income) }}</td>
                  <td>{{ e.eps != null ? e.eps.toFixed(2) : '-' }}</td>
                  <td :class="{ positive: e.revenue_yoy > 0, negative: e.revenue_yoy < 0 }">{{ formatPct(e.revenue_yoy) }}</td>
                  <td :class="{ positive: e.profit_yoy > 0, negative: e.profit_yoy < 0 }">{{ formatPct(e.profit_yoy) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </div>
```

Add CSS for detail panel:
```css
.detail-panel { padding: 20px; }
.detail-header { display: flex; justify-content: space-between; align-items: center; }
.detail-header h3 { margin: 0; color: #fff; }
.detail-reason { color: #aaa; font-size: 13px; margin: 8px 0 16px; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.detail-section h4 { color: #ccc; font-size: 14px; margin: 0 0 12px; }
.news-list { list-style: none; padding: 0; margin: 0; }
.news-list li { margin-bottom: 10px; }
.news-title { color: #4fc3f7; font-size: 13px; text-decoration: none; display: block; }
.news-title:hover { text-decoration: underline; }
.news-meta { color: #666; font-size: 11px; }
.earnings-table { font-size: 13px; }
.positive { color: #4caf50; }
.negative { color: #f44336; }
@media (max-width: 768px) { .detail-grid { grid-template-columns: 1fr; } }
```

**Step 2: Commit**

```bash
git add web/src/views/Watchlist.vue
git commit -m "feat: enhance watchlist page with news/earnings detail panel"
```

---

### Task 12: Update Reports.vue to render watchlist analysis section

**Files:**
- Modify: `web/src/views/Reports.vue`

**Step 1: Add watchlist analysis rendering**

In the weekly report detail view, after the opportunities section (or replacing it), add a "Tracked Stocks Analysis" section that renders `report.content.watchlist_analysis`:

```html
<!-- Tracked Stocks Analysis (Weekly) -->
<div v-if="detail.content.watchlist_analysis && detail.content.watchlist_analysis.length > 0" class="report-section">
  <h3>Tracked Stocks Analysis</h3>
  <div v-for="stock in detail.content.watchlist_analysis" :key="stock.symbol" class="stock-analysis-card">
    <div class="stock-header">
      <span class="stock-name">{{ stock.name }} ({{ stock.symbol }})</span>
      <span class="market-tag">{{ stock.market }}</span>
      <span class="verdict-tag" :class="verdictClass(stock.verdict)">{{ stock.verdict }}</span>
    </div>
    <div v-if="stock.current_price" class="stock-price">Price: {{ stock.current_price.toFixed(2) }}</div>
    <p v-if="stock.ai_comment" class="ai-comment">{{ stock.ai_comment }}</p>
    <div v-if="stock.ai_detail" class="ai-detail" v-html="renderMarkdown(stock.ai_detail)"></div>
  </div>
</div>
```

Add helper methods:
```javascript
function verdictClass(verdict) {
  if (verdict === '买入') return 'verdict-buy'
  if (verdict === '回避') return 'verdict-avoid'
  return 'verdict-wait'
}
```

Add CSS:
```css
.stock-analysis-card { border: 1px solid #333; border-radius: 8px; padding: 16px; margin-bottom: 12px; }
.stock-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.stock-name { color: #fff; font-weight: 600; font-size: 15px; }
.verdict-tag { padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.verdict-buy { background: #1b5e20; color: #4caf50; }
.verdict-avoid { background: #b71c1c33; color: #f44336; }
.verdict-wait { background: #333; color: #ff9800; }
.stock-price { color: #888; font-size: 13px; margin-bottom: 8px; }
.ai-comment { color: #ccc; font-size: 14px; line-height: 1.6; }
.ai-detail { color: #aaa; font-size: 13px; line-height: 1.5; margin-top: 12px; }
```

**Step 2: Build and test frontend**

Run: `docker compose up -d --build web`

**Step 3: Commit**

```bash
git add web/src/views/Reports.vue
git commit -m "feat: render tracked stocks deep analysis in weekly report view"
```

---

### Task 13: Update router sidebar label

**Files:**
- Modify: `web/src/router/index.js` (or wherever sidebar labels are defined)

**Step 1: Rename "Watchlist" to "Tracked Stocks" in navigation**

Find the route definition for `/watchlist` and update the name/label.

**Step 2: Commit**

```bash
git add web/src/router/index.js
git commit -m "refactor: rename Watchlist to Tracked Stocks in navigation"
```

---

### Task 14: Full integration test

**Step 1: Rebuild and test**

```bash
docker compose up -d --build
```

**Step 2: Trigger news collection manually**

```bash
curl -X POST http://localhost:8000/api/scheduler/trigger/collect_news
```

**Step 3: Trigger earnings collection manually**

```bash
curl -X POST http://localhost:8000/api/scheduler/trigger/collect_earnings
```

**Step 4: Generate a weekly report**

```bash
curl -X POST http://localhost:8000/api/reports/weekly/generate
```

**Step 5: Verify the report contains watchlist analysis**

```bash
curl http://localhost:8000/api/reports/weekly/list | python -m json.tool
```

Check that the latest report's content has `watchlist_analysis` with AI analysis for each tracked stock.

**Step 6: Verify the frontend**

- Visit `/watchlist` page — verify title says "Tracked Stocks"
- Click a stock — verify news and earnings detail panel opens
- Visit `/reports` — view latest weekly report — verify "Tracked Stocks Analysis" section appears

**Step 7: Run all tests**

```bash
docker compose exec api python -m pytest tests/ -v
```

**Step 8: Final commit**

```bash
git add -A
git commit -m "test: verify full integration of tracked stocks deep analysis"
```
