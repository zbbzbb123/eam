# 日报+周报重新设计 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace current real-time report generation with pre-generated, portfolio-centric daily/weekly reports stored in DB, with per-holding AI commentary and opportunity radar.

**Architecture:** New `GeneratedReport` DB table stores pre-generated reports as JSON. ReportService redesigned to produce holding-centric daily reports (P&L + per-stock AI commentary + opportunity radar) and strategic weekly reports (week summary + macro + capital flow + holdings review + opportunities). Scheduler triggers generation at fixed times. Frontend reads from cache — instant load.

**Tech Stack:** Python/FastAPI/SQLAlchemy (backend), Vue 3/Composition API (frontend), LLMClient for AI commentary (FAST model for daily per-holding, QUALITY model for weekly strategy).

---

## Report Content JSON Structures

### Daily Report Content

```json
{
  "portfolio_summary": {
    "total_value_cny": 1234567.89,
    "today_pnl": -1234.56,
    "today_pnl_pct": -0.8,
    "total_pnl": 12345.67,
    "total_pnl_pct": 5.2,
    "holdings_count": 8,
    "cash_pct": 12.5,
    "ai_summary": "今日持仓整体小幅回调-0.8%..."
  },
  "holdings": [
    {
      "symbol": "01810.HK",
      "name": "小米集团",
      "market": "HK",
      "tier": "medium",
      "weight_pct": 15.2,
      "quantity": 1000,
      "avg_cost": 35.0,
      "current_price": 42.5,
      "today_change_pct": -3.2,
      "total_pnl": 7500.0,
      "total_pnl_pct": 21.4,
      "action": "hold",
      "ai_comment": "建议持有。当前PE 18倍处于历史中位...",
      "ai_detail": "## 基本面\n...\n## 技术面\n...",
      "stop_loss_price": 30.0,
      "take_profit_price": 55.0,
      "near_stop_loss": false,
      "near_take_profit": false
    }
  ],
  "opportunities": [
    {
      "symbol": "NVDA",
      "name": "NVIDIA",
      "market": "US",
      "signal_type": "估值低位",
      "timeframe": "长期",
      "reason": "PE回落至25倍，数据中心业务增长强劲...",
      "detail": "## 详细分析\n...",
      "target_price": 150.0,
      "current_price": 120.0
    }
  ]
}
```

### Weekly Report Content

```json
{
  "week_summary": {
    "week_start": "2026-01-27",
    "week_end": "2026-02-02",
    "week_pnl": 5678.90,
    "week_pnl_pct": 1.2,
    "best_holding": {"symbol": "NVDA", "pnl_pct": 8.5},
    "worst_holding": {"symbol": "01810.HK", "pnl_pct": -3.2},
    "ai_summary": "本周市场受美联储鹰派讲话影响..."
  },
  "macro_capital": {
    "us_score": 45,
    "cn_score": 25,
    "us_summary": "美国宏观环境偏中性...",
    "cn_summary": "中国宏观数据偏弱...",
    "northbound_weekly_flow": -85.3,
    "northbound_trend": "外资观望",
    "sector_inflow_top5": [{"name": "半导体", "flow": 12.5}],
    "sector_outflow_top5": [{"name": "房地产", "flow": -8.3}],
    "key_events": ["美联储议息会议维持利率不变", "中国PMI低于预期"]
  },
  "holdings": [
    {
      "symbol": "01810.HK",
      "name": "小米集团",
      "market": "HK",
      "tier": "medium",
      "weight_pct": 15.2,
      "week_change_pct": -3.2,
      "total_pnl_pct": 21.4,
      "action": "hold",
      "ai_comment": "中期逻辑不变，汽车业务Q2放量...",
      "ai_detail": "## 持仓逻辑回顾\n..."
    }
  ],
  "opportunities": [
    {
      "symbol": "NVDA",
      "name": "NVIDIA",
      "market": "US",
      "source": "watchlist",
      "signal_type": "超跌反弹",
      "timeframe": "短期",
      "reason": "...",
      "detail": "...",
      "target_price": 150.0,
      "current_price": 120.0
    }
  ],
  "risk_alerts": [
    {"level": "high", "message": "半导体板块仓位集中度过高(35%)"}
  ],
  "next_week_events": [
    {"date": "2026-02-05", "event": "美国非农就业数据公布"}
  ]
}
```

---

## Task 1: Database — GeneratedReport Model

**Files:**
- Modify: `src/db/models_market_data.py` — add GeneratedReport model
- Modify: `src/db/database.py` — ensure table created on init

**Step 1: Add GeneratedReport model**

Add to `src/db/models_market_data.py` after existing models:

```python
class GeneratedReport(Base):
    """Pre-generated report storage."""
    __tablename__ = "generated_report"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_type = Column(String(20), nullable=False, index=True)  # "daily" or "weekly"
    report_date = Column(Date, nullable=False, index=True)
    generated_at = Column(DateTime, nullable=False)
    summary = Column(Text, nullable=True)  # One-line summary for list view
    content = Column(JSON, nullable=False)  # Full report JSON

    __table_args__ = (
        Index("ix_generated_report_type_date", "report_type", "generated_at"),
    )
```

**Step 2: Verify table auto-creates**

Check `src/db/database.py` — it should call `Base.metadata.create_all()` on init. The new model inherits from same `Base`, so table will be created automatically.

**Step 3: Commit**

```bash
git add src/db/models_market_data.py
git commit -m "feat: add GeneratedReport model for pre-generated report storage"
```

---

## Task 2: Backend — Daily Report Generator

**Files:**
- Create: `src/services/report_generator.py` — new service for generating and storing reports
- Reference: `src/services/ai_advisor.py` (per-holding AI analysis pattern)
- Reference: `src/analyzers/portfolio_health.py` (P&L calculation pattern)
- Reference: `src/analyzers/watchlist_analyzer.py` (opportunity detection pattern)

**Step 1: Create report_generator.py**

This is the largest new file. The `DailyReportGenerator` class:

1. Calculates P&L for all active holdings (reuse logic from `PortfolioHealthAnalyzer._get_latest_price()`)
2. Fetches today's change from `DailyQuote` (latest vs previous)
3. Calls LLM (FAST model) for each holding to generate `ai_comment` + `ai_detail` + `action`
4. Scans watchlist + related sectors for opportunities
5. Generates portfolio-level AI summary
6. Packages everything as JSON and saves to `GeneratedReport`

Key implementation details:

```python
class DailyReportGenerator:
    """Generates and stores daily reports."""

    def __init__(self, db: Session):
        self.db = db

    def generate(self) -> int:
        """Generate daily report and save to DB. Returns report ID."""
        now = datetime.now()

        # 1. Build portfolio summary + per-holding data
        holdings_data = self._build_holdings_data()

        # 2. AI commentary for each holding (batch)
        holdings_data = self._enrich_with_ai(holdings_data)

        # 3. Scan opportunities
        opportunities = self._scan_opportunities()

        # 4. Portfolio-level AI summary
        ai_summary = self._generate_portfolio_summary(holdings_data)

        # 5. Package and save
        content = {
            "portfolio_summary": { ... },
            "holdings": holdings_data,
            "opportunities": opportunities,
        }
        report = GeneratedReport(
            report_type="daily",
            report_date=now.date(),
            generated_at=now,
            summary=ai_summary,
            content=content,
        )
        self.db.add(report)
        self.db.commit()
        return report.id
```

For per-holding AI, reuse the prompt pattern from `ai_advisor.py` but with a simplified prompt focused on:
- Short comment (2-3 sentences, conclusion + reasoning)
- Action label (hold/add/reduce/sell)
- Detailed analysis (basic + technical + catalysts + risks, markdown format)

For opportunity scanning, reuse `WatchlistAnalyzer` logic plus add sector scanning:
- Pull all watchlist items + run opportunity detection
- Scan sectors related to holdings (from `HOLDING_KEYWORDS` and holding `custom_keywords`)
- For each opportunity, call LLM for a brief reason + detail

**Important:** Use `asyncio.run()` wrapper for LLM calls since scheduler runs in sync context. Batch LLM calls with `asyncio.gather()` for speed.

**Step 2: Add helper for "today's change"**

Need to compute today's change % per holding:
- Get latest 2 `DailyQuote` rows for each symbol
- `today_change_pct = (latest.close - previous.close) / previous.close * 100`
- If only 1 row or no rows, fallback to 0

**Step 3: Commit**

```bash
git add src/services/report_generator.py
git commit -m "feat: add DailyReportGenerator for per-holding AI daily reports"
```

---

## Task 3: Backend — Weekly Report Generator

**Files:**
- Modify: `src/services/report_generator.py` — add `WeeklyReportGenerator` class

**Step 1: Add WeeklyReportGenerator to same file**

```python
class WeeklyReportGenerator:
    """Generates and stores weekly reports."""

    def __init__(self, db: Session):
        self.db = db

    def generate(self) -> int:
        """Generate weekly report and save to DB. Returns report ID."""
        now = datetime.now()
        # Calculate current natural week boundaries
        week_end = now.date()
        week_start = week_end - timedelta(days=week_end.weekday())  # Monday

        # 1. Week P&L summary (aggregate from holdings)
        week_summary = self._build_week_summary(week_start, week_end)

        # 2. Macro + capital flow (reuse existing analyzers)
        macro_capital = self._build_macro_capital(week_start, week_end)

        # 3. Per-holding medium/long-term review (AI with strategic prompt)
        holdings = self._build_holdings_review()

        # 4. Opportunities (same as daily but broader)
        opportunities = self._scan_opportunities()

        # 5. Risk alerts
        risk_alerts = self._build_risk_alerts()

        # 6. Next week events
        next_week_events = self._build_next_week_events()

        content = { ... }
        # Save to DB
```

Key differences from daily:
- **Week P&L**: Compare holdings value at week_start vs now. Best/worst holding of the week.
- **Macro + capital**: Run `MarketEnvironmentAnalyzer` + `CapitalFlowAnalyzer`, extract key data, summarize weekly northbound flow, compile key events from signals.
- **AI prompts**: Use QUALITY model (Claude), strategic/medium-term perspective, reference macro context in per-holding prompts.
- **Opportunities**: Same sources as daily but LLM prompt emphasizes medium-term thesis.
- **Risk alerts**: Reuse from `PortfolioHealthAnalyzer` (concentration, tier deviation, etc.)
- **Next week events**: Placeholder structure — can be populated from signals or manual input later.

**Step 2: Commit**

```bash
git add src/services/report_generator.py
git commit -m "feat: add WeeklyReportGenerator with macro context and strategic analysis"
```

---

## Task 4: Backend — API Endpoints

**Files:**
- Modify: `src/api/reports.py` — add list + detail endpoints
- Modify: `src/api/schemas.py` — add new response schemas

**Step 1: Add schemas**

```python
class GeneratedReportListItem(BaseModel):
    """List item for generated reports."""
    id: int
    report_type: str
    report_date: date
    generated_at: datetime
    summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class GeneratedReportDetail(BaseModel):
    """Full generated report."""
    id: int
    report_type: str
    report_date: date
    generated_at: datetime
    summary: Optional[str] = None
    content: dict

    model_config = ConfigDict(from_attributes=True)
```

**Step 2: Add API endpoints**

```python
@router.get("/reports/daily/list")
def list_daily_reports(limit: int = 10, offset: int = 0, db=Depends(get_db)):
    """List generated daily reports, newest first."""
    reports = db.query(GeneratedReport).filter(
        GeneratedReport.report_type == "daily"
    ).order_by(desc(GeneratedReport.generated_at)).offset(offset).limit(limit).all()
    return [GeneratedReportListItem.model_validate(r) for r in reports]

@router.get("/reports/daily/{report_id}")
def get_daily_report_detail(report_id: int, db=Depends(get_db)):
    """Get a single daily report by ID."""
    report = db.query(GeneratedReport).filter(
        GeneratedReport.id == report_id,
        GeneratedReport.report_type == "daily"
    ).first()
    if not report:
        raise HTTPException(404, "Report not found")
    return GeneratedReportDetail.model_validate(report)

# Same pattern for weekly: /reports/weekly/list and /reports/weekly/{report_id}
```

**Step 3: Add manual trigger endpoint**

```python
@router.post("/reports/daily/generate")
def trigger_daily_report(db=Depends(get_db)):
    """Manually trigger daily report generation."""
    from src.services.report_generator import DailyReportGenerator
    gen = DailyReportGenerator(db)
    report_id = gen.generate()
    return {"status": "ok", "report_id": report_id}

# Same for weekly
```

**Step 4: Commit**

```bash
git add src/api/reports.py src/api/schemas.py
git commit -m "feat: add API endpoints for pre-generated report list and detail"
```

---

## Task 5: Backend — Update Scheduler

**Files:**
- Modify: `src/scheduler/scheduler.py` — update schedule times, add new jobs

**Step 1: Update DEFAULT_SCHEDULE**

```python
DEFAULT_SCHEDULE = {
    "collect_market_data":      {"hour": 17, "minute": 0},   # A-share close
    "collect_macro_data":       {"hour": 17, "minute": 10},
    "generate_daily_report_pm": {"hour": 17, "minute": 30},  # Daily #1
    "collect_market_data_am":   {"hour": 6, "minute": 30},   # US overnight
    "generate_daily_report_am": {"hour": 7, "minute": 0},    # Daily #2
}

WEEKLY_SCHEDULE = {
    "generate_weekly_report_sat": {"day_of_week": 5, "hour": 7, "minute": 0},   # Saturday 07:00
    "generate_weekly_report_sun": {"day_of_week": 6, "hour": 22, "minute": 0},  # Sunday 22:00
}
```

**Step 2: Add new job functions**

```python
def _generate_daily_report_new() -> None:
    """Generate pre-stored daily report."""
    from src.services.report_generator import DailyReportGenerator
    from src.db.database import SessionLocal
    db = SessionLocal()
    try:
        gen = DailyReportGenerator(db)
        report_id = gen.generate()
        logger.info(f"Daily report generated, id={report_id}")
    except Exception as e:
        logger.error(f"Daily report generation failed: {e}")
    finally:
        db.close()

def _generate_weekly_report_new() -> None:
    """Generate pre-stored weekly report."""
    from src.services.report_generator import WeeklyReportGenerator
    from src.db.database import SessionLocal
    db = SessionLocal()
    try:
        gen = WeeklyReportGenerator(db)
        report_id = gen.generate()
        logger.info(f"Weekly report generated, id={report_id}")
    except Exception as e:
        logger.error(f"Weekly report generation failed: {e}")
    finally:
        db.close()
```

**Step 3: Update _DEFAULT_FUNCS and _WEEKLY_FUNCS mappings**

**Step 4: Commit**

```bash
git add src/scheduler/scheduler.py
git commit -m "feat: update scheduler for 2x daily + 2x weekly report generation"
```

---

## Task 6: Frontend — API Layer + Reports.vue Rewrite

**Files:**
- Modify: `web/src/api/index.js` — replace report API functions
- Rewrite: `web/src/views/Reports.vue` — tab + history list structure

**Step 1: Update API functions**

Replace existing report functions with:

```javascript
export function getDailyReportList(limit = 10) {
  return safe(api.get('/reports/daily/list', { params: { limit } }), [])
}
export function getDailyReportDetail(id) {
  return safe(api.get(`/reports/daily/${id}`), null)
}
export function getWeeklyReportList(limit = 10) {
  return safe(api.get('/reports/weekly/list', { params: { limit } }), [])
}
export function getWeeklyReportDetail(id) {
  return safe(api.get(`/reports/weekly/${id}`), null)
}
export function triggerDailyReport() {
  return safe(aiApi.post('/reports/daily/generate'), null)
}
export function triggerWeeklyReport() {
  return safe(aiApi.post('/reports/weekly/generate'), null)
}
```

**Step 2: Rewrite Reports.vue**

Core structure:
- Tab bar: 日报 | 周报
- Each tab loads its report list on mount
- Latest report auto-expanded with full content
- Historical reports collapsed showing `generated_at` + `summary`, click to expand (lazy-load detail)
- Manual "生成报告" button for triggering

```vue
<template>
  <div>
    <div class="page-header">
      <h1>报告分析</h1>
    </div>

    <!-- Tab Bar -->
    <div class="tab-bar">
      <button :class="['tab-btn', {active: tab==='daily'}]" @click="switchTab('daily')">日报</button>
      <button :class="['tab-btn', {active: tab==='weekly'}]" @click="switchTab('weekly')">周报</button>
    </div>

    <!-- Report List -->
    <div v-if="loading" class="loading">加载中</div>
    <div v-else-if="!reports.length" class="empty">暂无报告</div>
    <div v-else>
      <div v-for="(r, i) in reports" :key="r.id" class="report-item">
        <!-- Header (always visible) -->
        <div class="report-item-header" @click="toggleReport(r)">
          <span class="report-date">{{ formatDate(r.generated_at) }}</span>
          <span class="report-summary">{{ r.summary || '加载中...' }}</span>
          <span class="expand-icon">{{ expandedId === r.id ? '▼' : '▶' }}</span>
        </div>
        <!-- Content (expanded) -->
        <div v-if="expandedId === r.id && expandedContent" class="report-content">
          <DailyReportView v-if="tab==='daily'" :content="expandedContent" />
          <WeeklyReportView v-else :content="expandedContent" />
        </div>
      </div>
    </div>
  </div>
</template>
```

**Step 3: Commit**

```bash
git add web/src/api/index.js web/src/views/Reports.vue
git commit -m "feat: rewrite Reports.vue with report history list and lazy loading"
```

---

## Task 7: Frontend — Daily Report Components

**Files:**
- Create: `web/src/components/report/DailyReportView.vue` — daily report container
- Create: `web/src/components/report/PortfolioSummaryCard.vue` — top summary card
- Create: `web/src/components/report/HoldingReviewCard.vue` — per-holding card
- Create: `web/src/components/report/OpportunityCard.vue` — opportunity radar card

**Step 1: DailyReportView.vue**

Container that renders the 3 sections:
```vue
<template>
  <div class="daily-report">
    <PortfolioSummaryCard :summary="content.portfolio_summary" />
    <h2 class="section-title">持仓点评</h2>
    <HoldingReviewCard v-for="h in content.holdings" :key="h.symbol" :holding="h" />
    <template v-if="content.opportunities?.length">
      <h2 class="section-title">机会雷达</h2>
      <OpportunityCard v-for="o in content.opportunities" :key="o.symbol" :opportunity="o" />
    </template>
  </div>
</template>
```

**Step 2: PortfolioSummaryCard.vue**

Props: `summary` object. Shows:
- Total value (large number)
- Today P&L with color (green/red) + percentage
- Total P&L with color + percentage
- Holdings count, cash %
- AI summary text

No charts — pure text + numbers, fast render.

**Step 3: HoldingReviewCard.vue**

Props: `holding` object. Shows:
- Header row: symbol + name + market badge + tier badge + weight %
- Data row: current price, today change %, total P&L, P&L %
- Action badge: 持有(blue) / 关注(orange) / 减仓(red) / 加仓(green)
- AI comment text (default visible)
- Stop loss / take profit warning if near
- Expandable detail section (click to toggle `ai_detail`, rendered with `white-space: pre-wrap`)

**Step 4: OpportunityCard.vue**

Props: `opportunity` object. Shows:
- Symbol + name + market badge
- Signal type badge + timeframe badge (长期/短期)
- Reason text
- Current price + target price (if available)
- Expandable detail

**Step 5: Commit**

```bash
git add web/src/components/report/DailyReportView.vue \
        web/src/components/report/PortfolioSummaryCard.vue \
        web/src/components/report/HoldingReviewCard.vue \
        web/src/components/report/OpportunityCard.vue
git commit -m "feat: add daily report frontend components"
```

---

## Task 8: Frontend — Weekly Report Components

**Files:**
- Create: `web/src/components/report/WeeklyReportView.vue` — weekly report container
- Create: `web/src/components/report/WeekSummaryCard.vue` — week overview card
- Create: `web/src/components/report/MacroCapitalSection.vue` — macro + capital flow section

Reuse from Task 7: `HoldingReviewCard.vue`, `OpportunityCard.vue`

**Step 1: WeeklyReportView.vue**

Container rendering 5 sections:
```vue
<template>
  <div class="weekly-report">
    <WeekSummaryCard :summary="content.week_summary" />
    <MacroCapitalSection :data="content.macro_capital" />
    <h2 class="section-title">持仓中长期点评</h2>
    <HoldingReviewCard v-for="h in content.holdings" :key="h.symbol" :holding="h" />
    <template v-if="content.opportunities?.length">
      <h2 class="section-title">新机会发掘</h2>
      <OpportunityCard v-for="o in content.opportunities" :key="o.symbol" :opportunity="o" />
    </template>
    <template v-if="content.risk_alerts?.length">
      <h2 class="section-title">风险提醒</h2>
      <div v-for="a in content.risk_alerts" :key="a.message" class="risk-alert-item">
        <span class="risk-badge" :class="a.level">{{ a.level }}</span>
        <span>{{ a.message }}</span>
      </div>
    </template>
    <template v-if="content.next_week_events?.length">
      <h2 class="section-title">下周关注</h2>
      <div v-for="e in content.next_week_events" :key="e.event" class="event-item">
        <span class="event-date">{{ e.date }}</span>
        <span>{{ e.event }}</span>
      </div>
    </template>
  </div>
</template>
```

**Step 2: WeekSummaryCard.vue**

Props: `summary` object. Shows:
- Week date range
- Week P&L (amount + %)
- Best / worst holding of the week
- AI summary paragraph

**Step 3: MacroCapitalSection.vue**

Props: `data` object. Shows:
- US/CN macro scores with ScoreGauge (small, reuse existing component)
- US/CN summary text
- Northbound weekly flow number + trend badge
- Sector inflow/outflow top 5 (simple list, no chart — keep it fast)
- Key events list

This is the only section with optional gauges. If score data unavailable, skip gauges.

**Step 4: Commit**

```bash
git add web/src/components/report/WeeklyReportView.vue \
        web/src/components/report/WeekSummaryCard.vue \
        web/src/components/report/MacroCapitalSection.vue
git commit -m "feat: add weekly report frontend components"
```

---

## Task 9: Cleanup + Integration

**Files:**
- Delete unused old components: `MacroSection.vue`, `CapitalFlowSection.vue`, `CommoditySection.vue`, `PortfolioHealthSection.vue`, `WatchlistSection.vue`, `SectionHeader.vue` (no longer needed)
- Keep: `RatingBadge.vue`, `ScoreGauge.vue`, `AIAdviceCard.vue` (reused)
- Modify: `src/scheduler/scheduler.py` — remove old report generation jobs

**Step 1: Remove old components**

```bash
rm web/src/components/report/MacroSection.vue
rm web/src/components/report/CapitalFlowSection.vue
rm web/src/components/report/CommoditySection.vue
rm web/src/components/report/PortfolioHealthSection.vue
rm web/src/components/report/WatchlistSection.vue
rm web/src/components/report/SectionHeader.vue
```

**Step 2: Commit cleanup**

```bash
git add -A
git commit -m "chore: remove old report section components replaced by new design"
```

---

## Task 10: Docker Build + Verification

**Step 1: Build and restart**

```bash
docker compose up -d --build
```

**Step 2: Trigger a daily report manually**

```bash
curl -X POST http://localhost:8000/api/reports/daily/generate
```

**Step 3: Verify list endpoint**

```bash
curl http://localhost:8000/api/reports/daily/list
```

Should return array with 1 report including summary.

**Step 4: Verify detail endpoint**

```bash
curl http://localhost:8000/api/reports/daily/{id}
```

Should return full content JSON with portfolio_summary, holdings[], opportunities[].

**Step 5: Verify frontend**

Open `http://localhost:3000/reports` — should show daily tab with the generated report expanded.

**Step 6: Trigger weekly report and verify**

```bash
curl -X POST http://localhost:8000/api/reports/weekly/generate
```

Switch to weekly tab — should show the generated weekly report.

**Step 7: Final commit**

```bash
git add -A
git commit -m "feat: complete report redesign — pre-generated daily/weekly with AI commentary"
```
