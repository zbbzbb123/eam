"""Portfolio API endpoints."""
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.db.database import get_db
from src.db.models import Holding, Tier, HoldingStatus
from src.api.schemas import PortfolioOverview, TierAllocation, TierEnum

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
