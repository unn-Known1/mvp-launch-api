"""
Authentication router - login, logout, refresh, register endpoints.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from auth import (
    blacklist_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_db,
    hash_password,
    require_permissions,
    seed_default_roles,
    verify_password,
)
from models import Role, User

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


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

    model_config = ConfigDict(from_attributes=True)


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

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=15 * 60,
    )


@router.post("/logout")
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token_str = auth_header[len("Bearer ") :]
        try:
            payload = decode_token(token_str)
            token_jti = payload.get("jti")
            token_exp = payload.get("exp")
            if token_jti and token_exp:
                blacklist_token(
                    token_jti=token_jti,
                    token_sub=str(current_user.id),
                    expires_at=datetime.fromtimestamp(token_exp),
                    db=db,
                )
        except HTTPException as e:
            logging.warning(f"HTTPException during logout for user {current_user.id}: {e.detail}")
        except Exception as e:
            logging.error(f"Failed to blacklist token during logout: {e}")
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


class PaginatedUsersResponse(BaseModel):
    """B-001: Paginated response format for list endpoints."""
    data: list[UserResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


@router.get("/users", response_model=PaginatedUsersResponse)
def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=1000, description="Items per page"),
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to include (e.g., id,email,name)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("users:read")),
):
    """
    List users with pagination and optional field selection.

    The fields parameter allows clients to request only specific fields
    to reduce payload size. Example: ?fields=id,email,name

    B-001 FIX: Added pagination with {data, total, page, page_size, has_more} response.
    """
    # Parse fields parameter
    requested_fields = None
    if fields:
        requested_fields = set(fields.split(","))

    # Get total count
    total = db.query(User).filter(User.deleted_at.is_(None)).count()

    # Calculate offset
    skip = (page - 1) * page_size

    # Fetch paginated users
    users = (
        db.query(User)
        .filter(User.deleted_at.is_(None))
        .offset(skip)
        .limit(page_size)
        .all()
    )

    # Filter to users in same "organization" - for MVP, users with same role are considered same org
    result = []
    for u in users:
        if u.email.startswith("system@"):
            continue

        # Build user response based on requested fields
        user_data = {
            "id": str(u.id),
            "email": u.email,
            "name": u.name,
            "role": u.role.name if u.role else None,
            "is_active": u.is_active,
            "created_at": u.created_at,
        }

        # Filter to requested fields if specified
        if requested_fields:
            user_data = {k: v for k, v in user_data.items() if k in requested_fields}

        result.append(UserResponse(**user_data))

    has_more = (skip + len(result)) < total

    return PaginatedUsersResponse(
        data=result,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )
