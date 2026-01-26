# Phase 3: Data Collectors Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build comprehensive data collection layer covering structured APIs, web crawlers, and alternative data sources.

**Architecture:** Each collector is a standalone module with unified interface. All collectors inherit from BaseCollector and implement fetch/parse/store pattern.

**Tech Stack:** Python 3.11+, httpx (async HTTP), BeautifulSoup4, APScheduler (future), existing SQLAlchemy models

---

## Collector Interface

```python
class BaseCollector(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def source(self) -> str: ...

    @abstractmethod
    def collect(self) -> List[Any]: ...

    def validate(self) -> bool: ...
```

---

## Task 1: FRED API Collector

**Purpose:** Fetch US macro data - TIPS yields, CPI, GDP, unemployment rate, Fed Funds rate

**Files:**
- Create: `src/collectors/structured/fred_collector.py`
- Create: `src/db/models_market_data.py` (macro data models)
- Create: `tests/collectors/test_fred_collector.py`

**Data Points:**
- DFII10 - 10-Year TIPS Yield
- CPIAUCSL - CPI
- GDP - Gross Domestic Product
- UNRATE - Unemployment Rate
- FEDFUNDS - Federal Funds Rate

**API:** https://api.stlouisfed.org/fred/series/observations

**Verification:**
```bash
pytest tests/collectors/test_fred_collector.py -v
# Manual: python -c "from src.collectors.structured.fred_collector import FREDCollector; c = FREDCollector(); print(c.collect())"
```

---

## Task 2: AkShare Northbound Flow Collector

**Purpose:** Fetch A-share northbound capital flow (北向资金)

**Files:**
- Create: `src/collectors/structured/northbound_collector.py`
- Create: `tests/collectors/test_northbound_collector.py`

**Data Points:**
- Daily northbound net flow
- Top 10 stocks by northbound holding change
- Sector flow breakdown

**API:** `akshare.stock_hsgt_north_net_flow_in_em()`, `akshare.stock_hsgt_hold_stock_em()`

**Verification:**
```bash
pytest tests/collectors/test_northbound_collector.py -v
```

---

## Task 3: OpenInsider Crawler

**Purpose:** Scrape US insider trading data

**Files:**
- Create: `src/collectors/crawlers/openinsider_crawler.py`
- Create: `src/db/models_insider.py` (insider trade model)
- Create: `tests/collectors/test_openinsider_crawler.py`

**Target URL:** http://openinsider.com/screener

**Data Points:**
- Filing date, trade date
- Ticker, company name
- Insider name, title
- Trade type (Buy/Sell)
- Price, quantity, value
- Shares owned after

**Verification:**
```bash
pytest tests/collectors/test_openinsider_crawler.py -v
```

---

## Task 4: SEC EDGAR 13F Collector

**Purpose:** Fetch institutional holdings from 13F filings

**Files:**
- Create: `src/collectors/structured/sec13f_collector.py`
- Create: `src/db/models_institutional.py` (institutional holding model)
- Create: `tests/collectors/test_sec13f_collector.py`

**Target:** SEC EDGAR API for 13F-HR filings

**Data Points:**
- Institution name, CIK
- Report date
- Holdings: stock, shares, value
- Quarter-over-quarter changes

**Key Institutions to Track:**
- Berkshire Hathaway
- ARK Invest
- Bridgewater
- Renaissance Technologies

**Verification:**
```bash
pytest tests/collectors/test_sec13f_collector.py -v
```

---

## Task 5: 集思录 ETF Premium Crawler

**Purpose:** Scrape ETF premium/discount data from jisilu.cn

**Files:**
- Create: `src/collectors/crawlers/jisilu_crawler.py`
- Create: `tests/collectors/test_jisilu_crawler.py`

**Target URL:** https://www.jisilu.cn/data/etf/#index

**Data Points:**
- ETF code, name
- Net value, price
- Premium/discount rate
- Volume, turnover

**Verification:**
```bash
pytest tests/collectors/test_jisilu_crawler.py -v
```

---

## Task 6: Commodity Price Crawler (生意社/SMM)

**Purpose:** Scrape commodity prices - lithium carbonate, polysilicon

**Files:**
- Create: `src/collectors/crawlers/commodity_crawler.py`
- Create: `tests/collectors/test_commodity_crawler.py`

**Target URLs:**
- 生意社: http://www.100ppi.com/
- SMM: https://www.smm.cn/

**Data Points:**
- Lithium carbonate price (碳酸锂)
- Polysilicon price (多晶硅)
- Price change %, 30-day trend

**Verification:**
```bash
pytest tests/collectors/test_commodity_crawler.py -v
```

---

## Task 7: GitHub API Collector

**Purpose:** Track open source project popularity for tech companies

**Files:**
- Create: `src/collectors/structured/github_collector.py`
- Create: `tests/collectors/test_github_collector.py`

**API:** GitHub REST API v3

**Data Points:**
- Repository stars, forks, watchers
- Recent commit activity
- Issue/PR velocity
- Contributor growth

**Target Repos (examples):**
- openai/openai-python
- huggingface/transformers
- pytorch/pytorch
- tensorflow/tensorflow

**Verification:**
```bash
pytest tests/collectors/test_github_collector.py -v
```

---

## Task 8: HuggingFace Collector

**Purpose:** Track AI model download trends

**Files:**
- Create: `src/collectors/structured/huggingface_collector.py`
- Create: `tests/collectors/test_huggingface_collector.py`

**API:** HuggingFace Hub API

**Data Points:**
- Model downloads (all-time, last month)
- Model likes
- Trending models by category

**Target Models (examples):**
- meta-llama/Llama-2-*
- mistralai/Mistral-*
- stabilityai/stable-diffusion-*

**Verification:**
```bash
pytest tests/collectors/test_huggingface_collector.py -v
```

---

## Task 9: TuShare Pro Collector Enhancement

**Purpose:** Fetch A-share financial metrics and valuation percentiles

**Files:**
- Modify: `src/collectors/structured/tushare_collector.py` (if exists, else create)
- Create: `tests/collectors/test_tushare_collector.py`

**Data Points:**
- PE, PB, PS ratios
- PE/PB historical percentile
- ROE, ROA
- Revenue/profit growth
- Free cash flow

**Verification:**
```bash
pytest tests/collectors/test_tushare_collector.py -v
```

---

## Task 10: Collector Registry and CLI

**Purpose:** Unified interface to run any collector

**Files:**
- Create: `src/collectors/registry.py`
- Create: `src/cli/collect.py`
- Create: `tests/collectors/test_registry.py`

**Features:**
- Register all collectors
- Run single collector: `python -m src.cli.collect --collector fred`
- Run all collectors: `python -m src.cli.collect --all`
- Status check: `python -m src.cli.collect --status`

**Verification:**
```bash
pytest tests/collectors/test_registry.py -v
python -m src.cli.collect --status
```

---

## Database Models Summary

New models to create:
1. `MacroData` - FRED macro indicators
2. `NorthboundFlow` - 北向资金流向
3. `InsiderTrade` - Insider transactions
4. `InstitutionalHolding` - 13F holdings
5. `ETFPremium` - ETF premium/discount
6. `CommodityPrice` - Commodity prices
7. `GitHubMetrics` - GitHub project metrics
8. `HuggingFaceMetrics` - AI model metrics

---

## Dependencies to Add

```toml
# pyproject.toml additions
httpx = "^0.27"
beautifulsoup4 = "^4.12"
lxml = "^5.1"
fredapi = "^0.5"
```

---

## Execution Order

1. Task 1: FRED API (foundation for macro analysis)
2. Task 2: Northbound Flow (A-share smart money)
3. Task 3: OpenInsider (US insider trading)
4. Task 4: SEC 13F (institutional holdings)
5. Task 5: 集思录 ETF (ETF arbitrage)
6. Task 6: Commodity Prices (sector indicators)
7. Task 7: GitHub API (tech sentiment)
8. Task 8: HuggingFace (AI trend)
9. Task 9: TuShare Enhancement (A-share fundamentals)
10. Task 10: Registry & CLI (unified interface)

Each task includes tests and manual verification before proceeding to next.
