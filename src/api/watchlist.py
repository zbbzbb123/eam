"""Watchlist API endpoints."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.db.database import get_db
from src.db.models import Watchlist, Market
from src.db.models_auth import User
from src.services.auth import get_current_user

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


# ===== Schemas =====

class WatchlistCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    market: str = Field(..., pattern="^(US|HK|CN)$")
    theme: str = Field("", max_length=100)
    reason: str = Field("")


class WatchlistUpdate(BaseModel):
    theme: Optional[str] = None
    reason: Optional[str] = None


class WatchlistResponse(BaseModel):
    id: int
    symbol: str
    market: str
    theme: str
    reason: str
    created_at: str

    model_config = {"from_attributes": True}


# ===== Endpoints =====

@router.get("", response_model=List[WatchlistResponse])
def list_watchlist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all watchlist items for current user."""
    items = db.execute(
        select(Watchlist)
        .where(Watchlist.user_id == current_user.id)
        .order_by(Watchlist.created_at.desc())
    ).scalars().all()

    return [
        WatchlistResponse(
            id=w.id,
            symbol=w.symbol,
            market=w.market.value,
            theme=w.theme,
            reason=w.reason,
            created_at=w.created_at.isoformat() if w.created_at else "",
        )
        for w in items
    ]


@router.post("", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
def add_watchlist(
    req: WatchlistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a symbol to watchlist."""
    # Check duplicate
    existing = db.execute(
        select(Watchlist).where(
            Watchlist.user_id == current_user.id,
            Watchlist.symbol == req.symbol.upper(),
            Watchlist.market == Market[req.market],
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{req.symbol} 已在关注列表中",
        )

    item = Watchlist(
        user_id=current_user.id,
        symbol=req.symbol.upper(),
        market=Market[req.market],
        theme=req.theme or "默认",
        reason=req.reason or "",
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return WatchlistResponse(
        id=item.id,
        symbol=item.symbol,
        market=item.market.value,
        theme=item.theme,
        reason=item.reason,
        created_at=item.created_at.isoformat() if item.created_at else "",
    )


@router.patch("/{item_id}", response_model=WatchlistResponse)
def update_watchlist(
    item_id: int,
    req: WatchlistUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a watchlist item."""
    item = db.get(Watchlist, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    if req.theme is not None:
        item.theme = req.theme
    if req.reason is not None:
        item.reason = req.reason

    db.commit()
    db.refresh(item)

    return WatchlistResponse(
        id=item.id,
        symbol=item.symbol,
        market=item.market.value,
        theme=item.theme,
        reason=item.reason,
        created_at=item.created_at.isoformat() if item.created_at else "",
    )


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a symbol from watchlist."""
    item = db.get(Watchlist, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    db.delete(item)
    db.commit()
