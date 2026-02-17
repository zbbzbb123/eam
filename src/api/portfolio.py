"""Portfolio API endpoints."""
import logging
import time
from datetime import date, timedelta
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
    DashboardResponse, DashboardTier, DashboardHoldingItem,
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


def _get_ref_price(holding: Holding, db: Session, days: int) -> Decimal:
    """Get reference price N days ago for P&L calculation.

    If holding was bought within the last N days, use avg_cost.
    Otherwise, use the closest DailyQuote close on or before (today - days).
    Falls back to avg_cost if no quote found.
    """
    today = date.today()
    ref_date = today - timedelta(days=days)

    if holding.first_buy_date > ref_date:
        return holding.avg_cost

    quote = (
        db.query(DailyQuote)
        .filter(
            DailyQuote.symbol == holding.symbol,
            DailyQuote.market == holding.market,
            DailyQuote.trade_date <= ref_date,
        )
        .order_by(DailyQuote.trade_date.desc())
        .first()
    )
    if quote and quote.close:
        return quote.close
    return holding.avg_cost


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full dashboard data: tiers with holdings and 7d/30d P&L."""
    holdings = db.execute(
        select(Holding).where(
            Holding.status == HoldingStatus.ACTIVE,
            Holding.user_id == current_user.id,
        )
        .order_by(Holding.tier, Holding.symbol)
    ).scalars().all()

    if not holdings:
        empty_tiers = []
        for tier_val in ["core", "growth", "gamble"]:
            empty_tiers.append(DashboardTier(
                tier=tier_val, market_value=Decimal("0"), weight_pct=Decimal("0"),
                pnl_7d=Decimal("0"), pnl_7d_pct=Decimal("0"),
                pnl_30d=Decimal("0"), pnl_30d_pct=Decimal("0"),
                holdings=[],
            ))
        return DashboardResponse(
            total_value=Decimal("0"),
            pnl_7d=Decimal("0"), pnl_7d_pct=Decimal("0"),
            pnl_30d=Decimal("0"), pnl_30d_pct=Decimal("0"),
            tiers=empty_tiers,
        )

    names = _get_stock_names(holdings)

    # Pre-compute per-holding data
    holding_data = []
    for h in holdings:
        current_price = _get_current_price(h, db)
        market_value = h.quantity * current_price

        ref_7d = _get_ref_price(h, db, 7)
        pnl_7d = (current_price - ref_7d) * h.quantity
        pnl_7d_pct = ((current_price - ref_7d) / ref_7d * 100) if ref_7d else Decimal("0")

        ref_30d = _get_ref_price(h, db, 30)
        pnl_30d = (current_price - ref_30d) * h.quantity
        pnl_30d_pct = ((current_price - ref_30d) / ref_30d * 100) if ref_30d else Decimal("0")

        holding_data.append({
            "holding": h,
            "current_price": current_price,
            "market_value": market_value,
            "ref_7d_value": ref_7d * h.quantity,
            "pnl_7d": pnl_7d,
            "pnl_7d_pct": pnl_7d_pct,
            "ref_30d_value": ref_30d * h.quantity,
            "pnl_30d": pnl_30d,
            "pnl_30d_pct": pnl_30d_pct,
        })

    total_value = sum(d["market_value"] for d in holding_data)

    # Group by tier
    tier_order = [Tier.CORE, Tier.GROWTH, Tier.GAMBLE]
    tiers = []
    total_pnl_7d = Decimal("0")
    total_ref_7d = Decimal("0")
    total_pnl_30d = Decimal("0")
    total_ref_30d = Decimal("0")

    for tier in tier_order:
        tier_holdings = [d for d in holding_data if d["holding"].tier == tier]
        tier_mv = sum(d["market_value"] for d in tier_holdings)
        tier_pnl_7d = sum(d["pnl_7d"] for d in tier_holdings)
        tier_ref_7d = sum(d["ref_7d_value"] for d in tier_holdings)
        tier_pnl_30d = sum(d["pnl_30d"] for d in tier_holdings)
        tier_ref_30d = sum(d["ref_30d_value"] for d in tier_holdings)

        total_pnl_7d += tier_pnl_7d
        total_ref_7d += tier_ref_7d
        total_pnl_30d += tier_pnl_30d
        total_ref_30d += tier_ref_30d

        items = []
        for d in tier_holdings:
            h = d["holding"]
            items.append(DashboardHoldingItem(
                id=h.id,
                symbol=h.symbol,
                name=names.get(h.symbol, ""),
                market=h.market.value,
                current_price=round(d["current_price"], 4),
                market_value=round(d["market_value"], 2),
                weight_in_tier=round(d["market_value"] / tier_mv * 100, 2) if tier_mv else Decimal("0"),
                pnl_7d=round(d["pnl_7d"], 2),
                pnl_7d_pct=round(d["pnl_7d_pct"], 2),
                pnl_30d=round(d["pnl_30d"], 2),
                pnl_30d_pct=round(d["pnl_30d_pct"], 2),
            ))

        tiers.append(DashboardTier(
            tier=tier.value,
            market_value=round(tier_mv, 2),
            weight_pct=round(tier_mv / total_value * 100, 2) if total_value else Decimal("0"),
            pnl_7d=round(tier_pnl_7d, 2),
            pnl_7d_pct=round(tier_pnl_7d / tier_ref_7d * 100, 2) if tier_ref_7d else Decimal("0"),
            pnl_30d=round(tier_pnl_30d, 2),
            pnl_30d_pct=round(tier_pnl_30d / tier_ref_30d * 100, 2) if tier_ref_30d else Decimal("0"),
            holdings=items,
        ))

    return DashboardResponse(
        total_value=round(total_value, 2),
        pnl_7d=round(total_pnl_7d, 2),
        pnl_7d_pct=round(total_pnl_7d / total_ref_7d * 100, 2) if total_ref_7d else Decimal("0"),
        pnl_30d=round(total_pnl_30d, 2),
        pnl_30d_pct=round(total_pnl_30d / total_ref_30d * 100, 2) if total_ref_30d else Decimal("0"),
        tiers=tiers,
    )
