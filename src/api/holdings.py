"""Holdings API endpoints."""
from typing import List, Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.db.database import get_db
from src.db.models import Holding, Transaction, Market, Tier, HoldingStatus, TransactionAction
from src.db.models_auth import User
from src.services.auth import get_current_user
from src.api.schemas import (
    HoldingCreate, HoldingUpdate, HoldingResponse,
    TransactionCreate, TransactionResponse,
    TierEnum, MarketEnum, HoldingStatusEnum
)

router = APIRouter(prefix="/holdings", tags=["holdings"])


def _map_market(market: MarketEnum) -> Market:
    """Map API enum to DB enum."""
    return Market[market.value]


def _map_tier(tier: TierEnum) -> Tier:
    """Map API enum to DB enum."""
    return Tier[tier.value.upper()]


@router.post("", response_model=HoldingResponse, status_code=status.HTTP_201_CREATED)
def create_holding(
    holding: HoldingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new holding."""
    db_holding = Holding(
        symbol=holding.symbol.upper(),
        market=_map_market(holding.market),
        tier=_map_tier(holding.tier),
        quantity=holding.quantity,
        avg_cost=holding.avg_cost,
        first_buy_date=holding.first_buy_date,
        buy_reason=holding.buy_reason,
        stop_loss_price=holding.stop_loss_price,
        take_profit_price=holding.take_profit_price,
        custom_keywords=holding.custom_keywords,
        notes=holding.notes,
        user_id=current_user.id,
    )
    db.add(db_holding)
    db.commit()
    db.refresh(db_holding)
    return db_holding


@router.get("", response_model=List[HoldingResponse])
def list_holdings(
    tier: Optional[TierEnum] = None,
    status: Optional[HoldingStatusEnum] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all holdings with optional filters."""
    query = select(Holding).where(Holding.user_id == current_user.id)

    if tier:
        query = query.where(Holding.tier == _map_tier(tier))
    if status:
        query = query.where(Holding.status == HoldingStatus[status.value.upper()])

    query = query.order_by(Holding.tier, Holding.symbol)

    result = db.execute(query)
    return result.scalars().all()


@router.get("/{holding_id}", response_model=HoldingResponse)
def get_holding(
    holding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific holding by ID."""
    holding = db.get(Holding, holding_id)
    if not holding or holding.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holding {holding_id} not found"
        )
    return holding


@router.patch("/{holding_id}", response_model=HoldingResponse)
def update_holding(
    holding_id: int,
    update: HoldingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a holding."""
    holding = db.get(Holding, holding_id)
    if not holding or holding.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holding {holding_id} not found"
        )

    update_data = update.model_dump(exclude_unset=True)

    # Map status enum if present
    if "status" in update_data and update_data["status"]:
        update_data["status"] = HoldingStatus[update_data["status"].value.upper()]

    for field, value in update_data.items():
        setattr(holding, field, value)

    db.commit()
    db.refresh(holding)
    return holding


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(
    holding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a holding."""
    holding = db.get(Holding, holding_id)
    if not holding or holding.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holding {holding_id} not found"
        )

    db.delete(holding)
    db.commit()


# ===== Transaction Endpoints =====

@router.post("/{holding_id}/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    holding_id: int,
    transaction: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new transaction for a holding."""
    holding = db.get(Holding, holding_id)
    if not holding or holding.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holding {holding_id} not found"
        )

    # Validate sell quantity
    if transaction.action.value == "sell" and transaction.quantity > holding.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot sell {transaction.quantity} shares, only {holding.quantity} available"
        )

    total_amount = transaction.quantity * transaction.price

    db_transaction = Transaction(
        holding_id=holding_id,
        action=TransactionAction[transaction.action.value.upper()],
        quantity=transaction.quantity,
        price=transaction.price,
        total_amount=total_amount,
        reason=transaction.reason,
        transaction_date=transaction.transaction_date,
    )

    db.add(db_transaction)

    # Update holding quantity and avg_cost
    if transaction.action.value == "buy":
        new_total_cost = (holding.quantity * holding.avg_cost) + total_amount
        holding.quantity += transaction.quantity
        holding.avg_cost = new_total_cost / holding.quantity
    else:  # sell
        holding.quantity -= transaction.quantity
        if holding.quantity <= 0:
            holding.status = HoldingStatus.CLOSED
            holding.quantity = Decimal("0")

    db.commit()
    db.refresh(db_transaction)
    return db_transaction


@router.get("/{holding_id}/transactions", response_model=List[TransactionResponse])
def list_transactions(
    holding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all transactions for a holding."""
    holding = db.get(Holding, holding_id)
    if not holding or holding.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holding {holding_id} not found"
        )

    query = select(Transaction).where(
        Transaction.holding_id == holding_id
    ).order_by(Transaction.transaction_date.desc())

    result = db.execute(query)
    return result.scalars().all()
