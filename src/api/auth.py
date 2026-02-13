"""Authentication API endpoints."""
import secrets
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models_auth import User, InvitationCode
from src.services.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_admin_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ===== Schemas =====

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user_id: int
    username: str
    is_admin: bool


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    invitation_code: str


class UserResponse(BaseModel):
    id: int
    username: str
    is_admin: bool
    created_at: datetime


class InvitationCodeCreate(BaseModel):
    count: int = Field(1, ge=1, le=50)
    note: Optional[str] = None


class InvitationCodeResponse(BaseModel):
    id: int
    code: str
    created_at: datetime
    used_by_username: Optional[str] = None
    used_at: Optional[datetime] = None
    note: Optional[str] = None


# ===== Endpoints =====

@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    token = create_access_token(user.id, user.username, user.is_admin)
    return LoginResponse(token=token, user_id=user.id, username=user.username, is_admin=user.is_admin)


@router.post("/register", response_model=LoginResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    # Validate invitation code
    invite = db.query(InvitationCode).filter(InvitationCode.code == req.invitation_code).first()
    if not invite:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invitation code")
    if invite.used_by is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation code already used")

    # Check username uniqueness
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    # Create user
    user = User(username=req.username, password_hash=hash_password(req.password), is_admin=False)
    db.add(user)
    db.flush()

    # Mark invitation code as used
    invite.used_by = user.id
    invite.used_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.username, user.is_admin)
    return LoginResponse(token=token, user_id=user.id, username=user.username, is_admin=user.is_admin)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id, username=current_user.username,
        is_admin=current_user.is_admin, created_at=current_user.created_at,
    )


# ===== Admin: Invitation Code Management =====

@router.post("/invitation-codes", response_model=List[InvitationCodeResponse])
def create_invitation_codes(
    req: InvitationCodeCreate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    codes = []
    for _ in range(req.count):
        code = secrets.token_urlsafe(8)
        ic = InvitationCode(code=code, created_by=admin.id, note=req.note)
        db.add(ic)
        codes.append(ic)
    db.commit()
    for c in codes:
        db.refresh(c)
    return [
        InvitationCodeResponse(id=c.id, code=c.code, created_at=c.created_at, note=c.note)
        for c in codes
    ]


@router.get("/invitation-codes", response_model=List[InvitationCodeResponse])
def list_invitation_codes(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    codes = db.query(InvitationCode).order_by(InvitationCode.created_at.desc()).all()
    result = []
    for c in codes:
        used_username = None
        if c.used_by:
            u = db.get(User, c.used_by)
            used_username = u.username if u else None
        result.append(InvitationCodeResponse(
            id=c.id, code=c.code, created_at=c.created_at,
            used_by_username=used_username, used_at=c.used_at, note=c.note,
        ))
    return result
