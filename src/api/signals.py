"""Signals API endpoints."""
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.db.database import get_db
from src.db.models import Signal, SignalType, SignalSeverity, SignalStatus
from src.db.models_auth import User
from src.services.auth import get_current_user
from src.api.schemas import (
    SignalCreate, SignalResponse, SignalUpdate,
    SignalTypeEnum, SignalSeverityEnum, SignalStatusEnum
)

router = APIRouter(prefix="/signals", tags=["signals"])

# Severity ordering for filtering
SEVERITY_ORDER = {
    SignalSeverity.INFO: 0,
    SignalSeverity.LOW: 1,
    SignalSeverity.MEDIUM: 2,
    SignalSeverity.HIGH: 3,
    SignalSeverity.CRITICAL: 4,
}


@router.post("", response_model=SignalResponse, status_code=status.HTTP_201_CREATED)
def create_signal(
    signal: SignalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new signal."""
    db_signal = Signal(
        signal_type=SignalType[signal.signal_type.value.upper()],
        sector=signal.sector,
        title=signal.title,
        description=signal.description,
        severity=SignalSeverity[signal.severity.value.upper()],
        source=signal.source,
        data=signal.data,
        related_symbols=signal.related_symbols,
        holding_id=signal.holding_id,
        expires_at=signal.expires_at,
        user_id=current_user.id,
    )
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.get("", response_model=List[SignalResponse])
def list_signals(
    signal_type: Optional[SignalTypeEnum] = None,
    sector: Optional[str] = None,
    min_severity: Optional[SignalSeverityEnum] = None,
    status: Optional[SignalStatusEnum] = Query(None, alias="status"),
    since: Optional[datetime] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List signals with optional filters."""
    query = select(Signal).where(Signal.user_id == current_user.id)

    if signal_type:
        query = query.where(Signal.signal_type == SignalType[signal_type.value.upper()])
    if sector:
        query = query.where(Signal.sector == sector)
    if status:
        query = query.where(Signal.status == SignalStatus[status.value.upper()])
    if min_severity:
        min_level = SEVERITY_ORDER[SignalSeverity[min_severity.value.upper()]]
        valid_severities = [s for s, level in SEVERITY_ORDER.items() if level >= min_level]
        query = query.where(Signal.severity.in_(valid_severities))
    if since:
        query = query.where(Signal.created_at >= since)

    query = query.order_by(Signal.created_at.desc()).limit(limit)

    result = db.execute(query)
    return result.scalars().all()


@router.get("/{signal_id}", response_model=SignalResponse)
def get_signal(
    signal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific signal by ID."""
    signal = db.get(Signal, signal_id)
    if not signal or signal.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal {signal_id} not found"
        )
    return signal


@router.patch("/{signal_id}", response_model=SignalResponse)
def update_signal(
    signal_id: int,
    update: SignalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a signal (mainly for status changes)."""
    signal = db.get(Signal, signal_id)
    if not signal or signal.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal {signal_id} not found"
        )

    if update.status:
        signal.status = SignalStatus[update.status.value.upper()]

    db.commit()
    db.refresh(signal)
    return signal


@router.post("/{signal_id}/mark-read", response_model=SignalResponse)
def mark_signal_read(
    signal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a signal as read."""
    signal = db.get(Signal, signal_id)
    if not signal or signal.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal {signal_id} not found"
        )

    signal.status = SignalStatus.READ
    db.commit()
    db.refresh(signal)
    return signal


@router.delete("/{signal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_signal(
    signal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a signal."""
    signal = db.get(Signal, signal_id)
    if not signal or signal.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal {signal_id} not found"
        )

    db.delete(signal)
    db.commit()
