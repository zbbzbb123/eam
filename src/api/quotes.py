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
    end_date: date = Query(default_factory=lambda: date.today()),
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
    end_date: date = Query(default_factory=lambda: date.today()),
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

    # Fetch all existing dates for this symbol/market in one query (avoid N+1)
    existing_dates_result = db.execute(
        select(DailyQuote.trade_date).where(
            DailyQuote.symbol == symbol,
            DailyQuote.market == Market[market.value],
        )
    ).scalars().all()
    existing_dates = set(existing_dates_result)

    count = 0
    for q in quotes:
        # Check if quote already exists using the pre-fetched set
        if q.trade_date not in existing_dates:
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
