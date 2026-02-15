"""Holdings API endpoints."""
import logging
from datetime import datetime, date, timedelta
from threading import Thread
from typing import List, Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.db.database import get_db, SessionLocal
from src.db.models import Holding, Transaction, Market, Tier, HoldingStatus, TransactionAction, DailyQuote
from src.db.models_auth import User
from src.services.auth import get_current_user
from src.api.schemas import (
    HoldingCreate, HoldingUpdate, HoldingResponse,
    TransactionCreate, TransactionResponse,
    TransactionPreviewRequest, TransactionPreviewResponse,
    PositionUpdateRequest,
    TierEnum, MarketEnum, HoldingStatusEnum
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/holdings", tags=["holdings"])


def _map_market(market: MarketEnum) -> Market:
    """Map API enum to DB enum."""
    return Market[market.value]


def _map_tier(tier: TierEnum) -> Tier:
    """Map API enum to DB enum."""
    return Tier[tier.value.upper()]


def _fetch_initial_quotes(symbol: str, market: Market, days: int = 90):
    """Fetch historical quotes in a background thread (uses its own DB session)."""
    db = SessionLocal()
    try:
        today = date.today()
        start = today - timedelta(days=days)

        if market in (Market.CN, Market.HK):
            from src.collectors.structured.akshare_collector import AkShareCollector
            quotes = AkShareCollector().fetch_quotes(symbol, start, today, market.value)
        else:
            from src.collectors.structured.yfinance_collector import YFinanceCollector
            quotes = YFinanceCollector().fetch_quotes(symbol, start, today)

        upserted = 0
        for q in quotes:
            existing = db.query(DailyQuote).filter(
                DailyQuote.symbol == symbol,
                DailyQuote.market == market,
                DailyQuote.trade_date == q.trade_date,
            ).first()
            if existing:
                existing.open = q.open
                existing.high = q.high
                existing.low = q.low
                existing.close = q.close
                existing.volume = q.volume
            else:
                db.add(DailyQuote(
                    symbol=symbol, market=market, trade_date=q.trade_date,
                    open=q.open, high=q.high, low=q.low, close=q.close, volume=q.volume,
                ))
            upserted += 1
        db.commit()
        logger.info(f"Initial quotes: upserted {upserted} rows for {symbol} ({market.value})")
    except Exception as e:
        logger.warning(f"Failed to fetch initial quotes for {symbol}: {e}")
        db.rollback()
    finally:
        db.close()


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
    db.flush()  # get db_holding.id for the initial transaction

    # Auto-generate initial BUY transaction
    initial_tx = Transaction(
        holding_id=db_holding.id,
        action=TransactionAction.BUY,
        quantity=holding.quantity,
        price=holding.avg_cost,
        total_amount=holding.quantity * holding.avg_cost,
        reason=holding.buy_reason or '首次买入',
        transaction_date=datetime.combine(holding.first_buy_date, datetime.min.time()),
    )
    db.add(initial_tx)

    db.commit()
    db.refresh(db_holding)

    # Fetch 90-day historical quotes in background
    Thread(
        target=_fetch_initial_quotes,
        args=(db_holding.symbol, db_holding.market),
        daemon=True,
    ).start()

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

    # Map tier enum if present
    if "tier" in update_data and update_data["tier"]:
        update_data["tier"] = Tier[update_data["tier"].value.upper()]

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


# ===== Position Update Endpoints =====

def _infer_transaction(old_qty: Decimal, old_avg: Decimal, new_qty: Decimal, new_avg: Decimal):
    """Infer transaction details from position changes.

    Returns (action, abs_delta_qty, inferred_price) or raises HTTPException.
    """
    delta_qty = new_qty - old_qty
    if delta_qty == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="数量未变化，无法推导交易"
        )

    action = "buy" if delta_qty > 0 else "sell"
    inferred_price = (new_qty * new_avg - old_qty * old_avg) / delta_qty

    if inferred_price <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"推导价格异常 ({inferred_price:.4f})，请检查输入"
        )

    return action, abs(delta_qty), round(inferred_price, 4)


def _suggest_date(symbol: str, market: Market, inferred_price: Decimal, db: Session) -> Optional[str]:
    """Find the trading day with closest price to inferred_price in the last 60 days."""
    cutoff = datetime.now().date() - timedelta(days=60)
    quotes = db.execute(
        select(DailyQuote).where(
            DailyQuote.symbol == symbol,
            DailyQuote.market == market,
            DailyQuote.trade_date >= cutoff,
        ).order_by(DailyQuote.trade_date.desc())
    ).scalars().all()

    if not quotes:
        return None

    best = min(quotes, key=lambda q: (abs(q.close - inferred_price), -q.trade_date.toordinal()) if q.close else (Decimal("999999"), 0))
    if best and best.close:
        return best.trade_date.isoformat()
    return None


@router.post("/{holding_id}/preview-transaction", response_model=TransactionPreviewResponse)
def preview_transaction(
    holding_id: int,
    req: TransactionPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview an inferred transaction from position changes without saving."""
    holding = db.get(Holding, holding_id)
    if not holding or holding.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holding {holding_id} not found"
        )

    action, qty, price = _infer_transaction(
        holding.quantity, holding.avg_cost, req.new_quantity, req.new_avg_cost
    )

    suggested_date = None
    if req.transaction_date:
        suggested_date = req.transaction_date.strftime("%Y-%m-%d")
    else:
        suggested_date = _suggest_date(holding.symbol, holding.market, price, db)

    return TransactionPreviewResponse(
        action=action,
        quantity=qty,
        inferred_price=price,
        suggested_date=suggested_date,
        old_quantity=holding.quantity,
        old_avg_cost=holding.avg_cost,
    )


@router.post("/{holding_id}/update-position", response_model=HoldingResponse)
def update_position(
    holding_id: int,
    req: PositionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update position and create an inferred transaction record."""
    holding = db.get(Holding, holding_id)
    if not holding or holding.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holding {holding_id} not found"
        )

    action, qty, price = _infer_transaction(
        holding.quantity, holding.avg_cost, req.new_quantity, req.new_avg_cost
    )

    tx_date = req.transaction_date or datetime.now()
    reason = req.reason or ("加仓" if action == "buy" else "减仓")

    # Create transaction record
    db_tx = Transaction(
        holding_id=holding_id,
        action=TransactionAction.BUY if action == "buy" else TransactionAction.SELL,
        quantity=qty,
        price=price,
        total_amount=qty * price,
        reason=reason,
        transaction_date=tx_date,
    )
    db.add(db_tx)

    # Update holding directly
    holding.quantity = req.new_quantity
    holding.avg_cost = req.new_avg_cost

    if req.new_quantity == 0:
        holding.status = HoldingStatus.CLOSED

    db.commit()
    db.refresh(holding)
    return holding
