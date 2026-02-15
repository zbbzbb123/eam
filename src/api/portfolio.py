"""Portfolio API endpoints."""
import logging
import time
from datetime import date
from decimal import Decimal
from typing import List, Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.db.database import get_db
from src.db.models import Holding, Tier, HoldingStatus, DailyQuote, Market
from src.db.models_auth import User
from src.services.auth import get_current_user
from src.api.schemas import (
    PortfolioOverview, TierAllocation, TierEnum,
    PortfolioSummaryResponse, TierSummaryResponse,
    HoldingSummaryResponse,
)

logger = logging.getLogger(__name__)

# Simple TTL cache: {key: (value, expire_timestamp)}
_cache: Dict[str, Any] = {}
CACHE_TTL = 3600  # 1 hour


def _cache_get(key: str):
    """Get value from cache if not expired."""
    if key in _cache:
        value, expire_at = _cache[key]
        if time.time() < expire_at:
            return value
        del _cache[key]
    return None


def _cache_set(key: str, value):
    """Set value in cache with TTL."""
    _cache[key] = (value, time.time() + CACHE_TTL)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# Target allocations (from boss's framework)
TARGET_ALLOCATIONS = {
    Tier.CORE: Decimal("40"),
    Tier.GROWTH: Decimal("30"),
    Tier.GAMBLE: Decimal("30"),
}


@router.get("/overview", response_model=PortfolioOverview)
def get_portfolio_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get portfolio overview with tier allocations.
    Uses avg_cost as price estimate for MVP (real implementation would fetch current prices).
    """
    # Get all active holdings
    holdings = db.execute(
        select(Holding).where(
            Holding.status == HoldingStatus.ACTIVE,
            Holding.user_id == current_user.id,
        )
    ).scalars().all()

    if not holdings:
        return PortfolioOverview(
            total_value=Decimal("0"),
            allocations=[
                TierAllocation(
                    tier=TierEnum.CORE,
                    target_pct=TARGET_ALLOCATIONS[Tier.CORE],
                    actual_pct=Decimal("0"),
                    drift_pct=Decimal("-40"),
                    market_value=Decimal("0"),
                ),
                TierAllocation(
                    tier=TierEnum.GROWTH,
                    target_pct=TARGET_ALLOCATIONS[Tier.GROWTH],
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
        # For MVP, use avg_cost as price estimate
        market_value = holding.quantity * holding.avg_cost
        tier_values[holding.tier] += market_value

    total_value = sum(tier_values.values())

    # Calculate allocations
    allocations = []
    for tier in [Tier.CORE, Tier.GROWTH, Tier.GAMBLE]:
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
def get_rebalance_suggestions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get suggestions for rebalancing the portfolio.
    Only suggests rebalancing when drift exceeds 5%.
    """
    overview = get_portfolio_overview(db=db, current_user=current_user)

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


def _get_current_price(holding: Holding, db: Session) -> Decimal:
    """Get current price for a holding from latest quote, falling back to avg_cost."""
    quote = (
        db.query(DailyQuote)
        .filter(
            DailyQuote.symbol == holding.symbol,
            DailyQuote.market == holding.market,
        )
        .order_by(DailyQuote.trade_date.desc())
        .first()
    )
    if quote and quote.close:
        return quote.close
    return holding.avg_cost


@router.get("/summary", response_model=PortfolioSummaryResponse)
def get_portfolio_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get portfolio summary with tier allocation details."""
    holdings = db.execute(
        select(Holding).where(
            Holding.status == HoldingStatus.ACTIVE,
            Holding.user_id == current_user.id,
        )
    ).scalars().all()

    if not holdings:
        tiers = []
        for tier in [Tier.CORE, Tier.GROWTH, Tier.GAMBLE]:
            target = TARGET_ALLOCATIONS[tier]
            tiers.append(TierSummaryResponse(
                tier=tier.value,
                target_pct=target,
                actual_pct=Decimal("0"),
                deviation=Decimal("0") - target,
                market_value=Decimal("0"),
                holdings_count=0,
            ))
        return PortfolioSummaryResponse(total_value=Decimal("0"), tiers=tiers)

    # Calculate values using current prices
    holding_values = {}
    for h in holdings:
        price = _get_current_price(h, db)
        holding_values[h.id] = h.quantity * price

    total_value = sum(holding_values.values())

    tiers = []
    for tier in [Tier.CORE, Tier.GROWTH, Tier.GAMBLE]:
        tier_holdings = [h for h in holdings if h.tier == tier]
        tier_value = sum(holding_values.get(h.id, Decimal("0")) for h in tier_holdings)
        target = TARGET_ALLOCATIONS[tier]
        actual = (tier_value / total_value * 100) if total_value else Decimal("0")
        deviation = actual - target

        tiers.append(TierSummaryResponse(
            tier=tier.value,
            target_pct=target,
            actual_pct=round(actual, 2),
            deviation=round(deviation, 2),
            market_value=round(tier_value, 2),
            holdings_count=len(tier_holdings),
        ))

    return PortfolioSummaryResponse(
        total_value=round(total_value, 2),
        tiers=tiers,
    )


def _get_stock_names(holdings) -> dict:
    """Batch fetch stock names with cache. Returns {symbol: name}."""
    from src.collectors.sina_quote import fetch_sina_quote

    names = {}
    for h in holdings:
        cache_key = f"name:{h.symbol}:{h.market.value}"
        cached = _cache_get(cache_key)
        if cached is not None:
            names[h.symbol] = cached
            continue

        name = ""
        if h.market in (Market.CN, Market.HK):
            try:
                sq = fetch_sina_quote(h.symbol, h.market.value)
                if sq and sq.name:
                    name = sq.name
            except Exception:
                pass
        elif h.market == Market.US:
            try:
                import yfinance as yf
                info = yf.Ticker(h.symbol).info
                name = info.get("shortName") or info.get("longName") or ""
            except Exception:
                pass

        _cache_set(cache_key, name)
        names[h.symbol] = name
    return names


@router.get("/holdings-summary", response_model=List[HoldingSummaryResponse])
def get_holdings_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all active holdings with P&L information."""
    holdings = db.execute(
        select(Holding).where(
            Holding.status == HoldingStatus.ACTIVE,
            Holding.user_id == current_user.id,
        )
        .order_by(Holding.tier, Holding.symbol)
    ).scalars().all()

    # Batch fetch names
    names = _get_stock_names(holdings)

    result = []
    for h in holdings:
        current_price = _get_current_price(h, db)
        market_value = h.quantity * current_price
        cost_basis = h.quantity * h.avg_cost
        pnl = market_value - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis else Decimal("0")

        result.append(HoldingSummaryResponse(
            id=h.id,
            symbol=h.symbol,
            name=names.get(h.symbol, ""),
            market=h.market.value,
            tier=h.tier.value,
            quantity=h.quantity,
            avg_cost=h.avg_cost,
            current_price=current_price,
            market_value=round(market_value, 2),
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 2),
        ))

    return result


def _fetch_and_cache_price(symbol: str, market: Market):
    """Fetch price from external API with 1-hour cache. Returns (close, open, high, low, volume, trade_date) or None."""
    cache_key = f"price:{symbol}:{market.value}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    from src.collectors.structured.yfinance_collector import YFinanceCollector
    from src.collectors.sina_quote import fetch_sina_quote

    result = None
    try:
        if market == Market.US:
            yf = YFinanceCollector()
            quote = yf.fetch_latest_quote(symbol)
            if quote and quote.close:
                result = {
                    "close": Decimal(str(quote.close)),
                    "open": Decimal(str(quote.open)) if quote.open else None,
                    "high": Decimal(str(quote.high)) if quote.high else None,
                    "low": Decimal(str(quote.low)) if quote.low else None,
                    "volume": quote.volume,
                    "trade_date": quote.trade_date,
                }
        else:
            sq = fetch_sina_quote(symbol, market.value)
            if sq and sq.close:
                result = {
                    "close": sq.close,
                    "open": sq.open,
                    "high": sq.high,
                    "low": sq.low,
                    "volume": sq.volume,
                    "trade_date": sq.trade_date,
                }
    except Exception as e:
        logger.warning("Failed to fetch price for %s: %s", symbol, e)

    _cache_set(cache_key, result)
    return result


@router.post("/sync-prices")
def sync_prices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch latest prices for all active holdings and store in daily_quotes. Uses 1-hour cache."""
    holdings = db.execute(
        select(Holding).where(
            Holding.status == HoldingStatus.ACTIVE,
            Holding.user_id == current_user.id,
        )
    ).scalars().all()

    if not holdings:
        return {"synced": 0, "errors": []}

    synced = 0
    errors = []

    # Deduplicate symbols per market
    seen = set()
    unique_holdings = []
    for h in holdings:
        key = (h.symbol, h.market)
        if key not in seen:
            seen.add(key)
            unique_holdings.append(h)

    for h in unique_holdings:
        try:
            data = _fetch_and_cache_price(h.symbol, h.market)

            if not data:
                errors.append(f"{h.symbol}: no quote data")
                continue

            # Upsert into daily_quotes
            existing = db.execute(
                select(DailyQuote).where(
                    DailyQuote.symbol == h.symbol,
                    DailyQuote.market == h.market,
                    DailyQuote.trade_date == data["trade_date"],
                )
            ).scalar_one_or_none()

            if existing:
                existing.close = data["close"]
                existing.open = data["open"]
                existing.high = data["high"]
                existing.low = data["low"]
                existing.volume = data["volume"]
            else:
                db.add(DailyQuote(
                    symbol=h.symbol,
                    market=h.market,
                    trade_date=data["trade_date"],
                    open=data["open"], high=data["high"], low=data["low"],
                    close=data["close"], volume=data["volume"],
                ))
            db.flush()
            synced += 1
        except Exception as e:
            db.rollback()
            logger.warning("Failed to sync price for %s: %s", h.symbol, e)
            errors.append(f"{h.symbol}: {str(e)}")

    db.commit()
    return {"synced": synced, "errors": errors}
