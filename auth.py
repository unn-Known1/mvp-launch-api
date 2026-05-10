"""
Authentication module - JWT handling, password hashing, FastAPI dependencies.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import SessionLocal
from models import DEFAULT_ROLES, Role, TokenBlacklist, User, ApiKey
import hashlib
import hmac

# SECURITY: Validate that JWT_SECRET_KEY is set in production
SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not SECRET_KEY:
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        raise ValueError(
            "JWT_SECRET_KEY environment variable is required in production. "
            "Please set a secure secret key before starting the application."
        )
    # In development, provide a clear error instead of silent fallback
    raise ValueError(
        "JWT_SECRET_KEY environment variable is not set. "
        "Please set it in your .env file or environment."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "type": "access", "jti": uuid4().hex, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "type": "refresh", "jti": uuid4().hex, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials)
        user_id = payload.get("sub")
        token_type = payload.get("type")
        if token_type != "access" or not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    token_jti = payload.get("jti")
    if token_jti:
        blacklisted = (
            db.query(TokenBlacklist)
            .filter(
                TokenBlacklist.token_jti == token_jti,
                TokenBlacklist.expires_at > datetime.now(timezone.utc),
            )
            .first()
        )
        if blacklisted:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
            )

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


def require_permissions(*required_permissions: str):
    async def permission_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not current_user.role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no role assigned",
            )

        user_permissions = set(current_user.role.permissions or [])
        if not all(perm in user_permissions for perm in required_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        return current_user

    return permission_checker


def seed_default_roles(db: Session) -> None:
    for role_name, config in DEFAULT_ROLES.items():
        existing = db.query(Role).filter(Role.name == role_name).first()
        if existing is None:
            role = Role(
                name=role_name,
                description=config["description"],
                permissions=config["permissions"],
            )
            db.add(role)
    db.commit()


def blacklist_token(
    token_jti: str, token_sub: str, expires_at: datetime, db: Session
) -> None:
    existing = (
        db.query(TokenBlacklist).filter(TokenBlacklist.token_jti == token_jti).first()
    )
    if not existing:
        entry = TokenBlacklist(
            token_jti=token_jti,
            token_sub=token_sub,
            expires_at=expires_at,
        )
        db.add(entry)
        db.commit()


def cleanup_expired_blacklist(db: Session) -> None:
    # NEW-014 FIX: Ensure timezone-aware datetime comparison
    # Convert naive datetime from DB to timezone-aware for comparison
    now_aware = datetime.now(timezone.utc)
    db.query(TokenBlacklist).filter(
        TokenBlacklist.expires_at <= now_aware
    ).delete()
    db.commit()


# B-006: API Key Authentication Support
def verify_api_key(api_key: str, db: Session) -> Optional[User]:
    """Verify an API key and return the associated user.

    B-006 FIX: Added API key authentication support.
    API keys are stored as SHA-256 hashes for security.
    """
    if not api_key or not api_key.startswith("mk_"):
        return None

    # Hash the provided API key to compare with stored hash
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # Find active API key with matching hash
    api_key_record = (
        db.query(ApiKey)
        .filter(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active.is_(True),
        )
        .first()
    )

    if not api_key_record:
        return None

    # Check expiration
    if api_key_record.expires_at and api_key_record.expires_at <= datetime.now(timezone.utc):
        return None

    # Update last used timestamp
    api_key_record.last_used_at = datetime.now(timezone.utc)
    db.commit()

    # Return the user
    return db.query(User).filter(User.id == api_key_record.user_id, User.is_active.is_(True)).first()


def create_api_key(user_id: str, name: str, db: Session, expires_at: Optional[datetime] = None) -> tuple[str, str]:
    """Create a new API key for a user. Returns (key_id, full_key).
    
    The full_key should be shown to the user once - it cannot be recovered.
    """
    import secrets
    
    # Generate a secure random key
    full_key = f"mk_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    
    api_key = ApiKey(
        user_id=user_id,
        key_hash=key_hash,
        name=name,
        expires_at=expires_at,
    )
    db.add(api_key)
    db.commit()
    
    # Return the full key (only time it's visible) and key ID
    return str(api_key.id), full_key
