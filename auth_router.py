"""
Authentication router - login, logout, refresh, register endpoints.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import (
    blacklist_token,
    create_access_token,
    create_refresh_token,
    get_db,
    get_current_user,
    hash_password,
    require_permissions,
    seed_default_roles,
    verify_password,
    decode_token,
)
from models import User, Role

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int


class UserCreateRequest(BaseModel):
    email: str
    password: str
    name: str
    role_name: Optional[str] = "viewer"


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/login", response_model=TokenResponse)
def login(creds: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == creds.email).first()
    if user is None or not verify_password(creds.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
        )

    user.last_login_at = datetime.utcnow()
    db.commit()

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=15 * 60,
    )


@router.post("/logout")
def logout(current_user=Depends(get_current_user)):
    return {"message": "Logout successful"}


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token type")

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=15 * 60,
    )


@router.post("/users", response_model=UserResponse, status_code=201)
def register_user(body: UserCreateRequest, db: Session = Depends(get_db)):
    seed_default_roles(db)

    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    role = db.query(Role).filter(Role.name == body.role_name).first()
    if role is None:
        role = db.query(Role).filter(Role.name == "viewer").first()

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        name=body.name,
        role_id=role.id if role else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=role.name if role else None,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get("/users", response_model=list[UserResponse])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _=Depends(require_permissions("users:read")),
):
    users = db.query(User).offset(skip).limit(limit).all()
    result = []
    for u in users:
        result.append(
            UserResponse(
                id=str(u.id),
                email=u.email,
                name=u.name,
                role=u.role.name if u.role else None,
                is_active=u.is_active,
                created_at=u.created_at,
            )
        )
    return result
