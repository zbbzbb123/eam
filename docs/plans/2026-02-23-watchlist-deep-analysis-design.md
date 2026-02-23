# Watchlist Deep Analysis Redesign

**Date**: 2026-02-23
**Status**: Approved

## Goal

Transform the existing Watchlist into a "Tracked Stocks" module with deep analysis capabilities. Add news and earnings data collection to provide LLM with rich, timely context for generating specific, actionable investment analysis in weekly/daily reports.

## Problem

Current report analysis is vague and generic — statements like "需要关注" or "保持谨慎" that could apply at any time. The LLM lacks:
1. Recent news/events for each stock
2. Quarterly earnings data with YoY trends
3. Strong prompt guidance requiring specific, data-backed recommendations

## Design

### Module 1: New Data Models

#### `StockNews` table (stock_news)
- `id`, `symbol`, `market`, `title`, `summary`, `source` (eastmoney/sina/yahoo), `url`, `published_at`, `fetched_at`
- Indexed on (symbol, market, published_at)
- Serves both Watchlist and Holdings

#### `StockEarnings` table (stock_earnings)
- `id`, `symbol`, `market`, `period` (e.g. "2025Q4"), `revenue`, `net_income`, `eps`, `revenue_yoy`, `profit_yoy`, `source`, `reported_at`, `fetched_at`
- Indexed on (symbol, market, period)
- Stores last few quarters of earnings summary

### Module 2: New Collectors

#### `NewsCollector`
- A-share/HK: EastMoney individual stock news (akshare `stock_news_em` or direct crawl)
- US: Yahoo Finance news (yfinance `.news` property)
- Sina Finance as supplement
- Scope: all Watchlist symbols + all active Holding symbols
- Schedule: daily, fetch last 7 days of news per symbol, dedup on insert

#### `EarningsCollector`
- A-share: EastMoney financial abstract (akshare `stock_financial_abstract_em`)
- HK/US: yfinance `.quarterly_financials`
- Schedule: weekly (earnings update infrequently)

### Module 3: Enhanced Report Generation

#### Watchlist Analysis Changes
- **Before**: Only analyze watchlist stocks that trigger opportunity signals (pullback, low PE, etc.)
- **After**: Analyze EVERY watchlist stock in weekly report, regardless of signal triggers

#### Enhanced LLM Context per Stock
1. Recent news (top 5 headlines + summaries from last 7 days)
2. Recent earnings (last 2 quarters: revenue, profit, YoY changes)
3. Price trends (5d/20d/60d changes, MA positions, volume) — existing
4. Fundamentals (PE/PB/analyst rating) — existing
5. Sector fund flows — existing

#### Improved LLM Prompts
- Require citing specific news events and data points
- Require clear action recommendation (buy/hold/avoid) with reasoning
- Require incorporating macro environment context
- Prohibit vague statements ("需关注", "保持谨慎" etc.)

#### Holdings Analysis Enhancement
- Holdings in daily/weekly reports also receive news + earnings context

### Module 4: Frontend Changes

#### Watchlist Page
- Rename to "跟踪股票" / "Tracked Stocks"
- Add latest news preview column
- Add recent earnings summary column

#### Reports Page
- Weekly report includes "跟踪股票深度分析" section
- Each stock shows: news events, earnings changes, price trends, investment recommendation

## Data Flow

```
Schedulers (daily/weekly)
    ↓
NewsCollector + EarningsCollector
    ↓
stock_news + stock_earnings tables
    ↓
Report Generator (reads news + earnings per stock)
    ↓
Enhanced LLM prompt with rich context
    ↓
Specific, actionable analysis in reports
```
