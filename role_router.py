"""
Role management router - CRUD for roles and user role assignment.
Admin-only endpoints for managing roles and permissions.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user, get_db, require_permissions, seed_default_roles
from models import Role, User

router = APIRouter(prefix="/api/v1/roles", tags=["Role Management"])


class RoleCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: list[str] = []


class RoleUpdateRequest(BaseModel):
    description: Optional[str] = None
    permissions: Optional[list[str]] = None


class RoleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    permissions: list[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserRoleUpdateRequest(BaseModel):
    role_name: str


class UserPermissionResponse(BaseModel):
    id: str
    email: str
    name: str
    role: Optional[str]
    permissions: list[str]
    is_active: bool

    class Config:
        from_attributes = True


@router.post("", response_model=RoleResponse, status_code=201)
def create_role(
    req: RoleCreateRequest,
    db: Session = Depends(get_db),
    _=Depends(require_permissions("users:write")),
):
    """Create a new role. Requires users:write permission."""
    existing = db.query(Role).filter(Role.name == req.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Role '{req.name}' already exists")

    role = Role(
        name=req.name,
        description=req.description or "",
        permissions=req.permissions,
    )
    db.add(role)
    db.commit()
    db.refresh(role)

    return RoleResponse(
        id=str(role.id),
        name=role.name,
        description=role.description,
        permissions=role.permissions or [],
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.get("", response_model=list[RoleResponse])
def list_roles(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """List all roles. Any authenticated user can view roles."""
    seed_default_roles(db)
    roles = db.query(Role).order_by(Role.name).all()
    return [
        RoleResponse(
            id=str(r.id),
            name=r.name,
            description=r.description,
            permissions=r.permissions or [],
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in roles
    ]


@router.get("/{role_id}", response_model=RoleResponse)
def get_role(
    role_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Get a specific role by ID."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    return RoleResponse(
        id=str(role.id),
        name=role.name,
        description=role.description,
        permissions=role.permissions or [],
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.put("/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: str,
    req: RoleUpdateRequest,
    db: Session = Depends(get_db),
    _=Depends(require_permissions("users:write")),
):
    """Update a role's description or permissions. Requires users:write permission."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if req.description is not None:
        role.description = req.description
    if req.permissions is not None:
        role.permissions = req.permissions

    db.commit()
    db.refresh(role)

    return RoleResponse(
        id=str(role.id),
        name=role.name,
        description=role.description,
        permissions=role.permissions or [],
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_permissions("users:delete")),
):
    """Delete a role. Requires users:delete permission. Cannot delete roles with active users."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    users_with_role = (
        db.query(User).filter(User.role_id == role_id, User.is_active.is_(True)).count()
    )
    if users_with_role > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete role: {users_with_role} active user(s) have this role",
        )

    db.delete(role)
    db.commit()


@router.patch("/users/{user_id}/role", response_model=UserPermissionResponse)
def update_user_role(
    user_id: str,
    req: UserRoleUpdateRequest,
    db: Session = Depends(get_db),
    _=Depends(require_permissions("users:write")),
):
    """Change a user's role. Requires users:write permission."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role = db.query(Role).filter(Role.name == req.role_name).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role '{req.role_name}' not found")

    user.role_id = role.id
    db.commit()
    db.refresh(user)

    return UserPermissionResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=role.name,
        permissions=role.permissions or [],
        is_active=user.is_active,
    )


@router.get("/users/{user_id}/permissions", response_model=UserPermissionResponse)
def get_user_permissions(
    user_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a user's role and permissions. Admins can view any user; users can view themselves."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if str(current_user.id) != user_id:
        admin_checker = require_permissions("users:read")
        admin_checker(current_user)

    role_name = user.role.name if user.role else None
    permissions = user.role.permissions if user.role else []

    return UserPermissionResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=role_name,
        permissions=permissions or [],
        is_active=user.is_active,
    )
