"""Portfolio API endpoints."""
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.db.database import get_db
from src.db.models import Holding, Tier, HoldingStatus, DailyQuote
from src.api.schemas import (
    PortfolioOverview, TierAllocation, TierEnum,
    PortfolioSummaryResponse, TierSummaryResponse,
    HoldingSummaryResponse,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# Target allocations (from boss's framework)
TARGET_ALLOCATIONS = {
    Tier.STABLE: Decimal("40"),
    Tier.MEDIUM: Decimal("30"),
    Tier.GAMBLE: Decimal("30"),
}


@router.get("/overview", response_model=PortfolioOverview)
def get_portfolio_overview(db: Session = Depends(get_db)):
    """
    Get portfolio overview with tier allocations.
    Uses avg_cost as price estimate for MVP (real implementation would fetch current prices).
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
        # For MVP, use avg_cost as price estimate
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
    Only suggests rebalancing when drift exceeds 5%.
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
def get_portfolio_summary(db: Session = Depends(get_db)):
    """Get portfolio summary with tier allocation details."""
    holdings = db.execute(
        select(Holding).where(Holding.status == HoldingStatus.ACTIVE)
    ).scalars().all()

    if not holdings:
        tiers = []
        for tier in [Tier.STABLE, Tier.MEDIUM, Tier.GAMBLE]:
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
    for tier in [Tier.STABLE, Tier.MEDIUM, Tier.GAMBLE]:
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


@router.get("/holdings-summary", response_model=List[HoldingSummaryResponse])
def get_holdings_summary(db: Session = Depends(get_db)):
    """Get all active holdings with P&L information."""
    holdings = db.execute(
        select(Holding).where(Holding.status == HoldingStatus.ACTIVE)
        .order_by(Holding.tier, Holding.symbol)
    ).scalars().all()

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
