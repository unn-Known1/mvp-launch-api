"""
FastAPI router for audit log query interface.

Provides read-only access to audit logs for compliance and security monitoring.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from auth import get_current_user, require_permissions
from database import get_db
from models import AuditLog, User

router = APIRouter(prefix="/api/v1/audit-logs", tags=["Audit Logs"])


class AuditLogResponse(BaseModel):
    id: str
    user_id: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: Optional[dict]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class AuditLogSummary(BaseModel):
    total_events: int
    events_by_action: dict[str, int]
    events_by_resource_type: dict[str, int]
    recent_activity_count: int


@router.get("/", response_model=AuditLogListResponse)
async def list_audit_logs(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    from_date: Optional[datetime] = Query(None, description="Filter from date (ISO format)"),
    to_date: Optional[datetime] = Query(None, description="Filter to date (ISO format)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    List audit logs with optional filters and pagination.

    Requires 'audit:read' permission.
    """
    # Check permission
    require_permissions("audit:read")(current_user)

    query = db.query(AuditLog)

    # Apply filters
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if from_date:
        query = query.filter(AuditLog.created_at >= from_date)
    if to_date:
        query = query.filter(AuditLog.created_at <= to_date)

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size).all()

    return AuditLogListResponse(
        logs=[
            AuditLogResponse(
                id=str(log.id),
                user_id=str(log.user_id) if log.user_id else None,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=str(log.resource_id) if log.resource_id else None,
                details=log.details,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                created_at=log.created_at.isoformat() if log.created_at else "",
            )
            for log in logs
        ],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(logs)) < total,
    )


@router.get("/summary", response_model=AuditLogSummary)
async def get_audit_summary(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get audit log summary statistics.

    Requires 'audit:read' permission.
    """
    require_permissions("audit:read")(current_user)

    from datetime import timedelta

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Query logs within the period
    logs = db.query(AuditLog).filter(AuditLog.created_at >= cutoff_date).all()

    # Calculate statistics
    events_by_action: dict[str, int] = {}
    events_by_resource_type: dict[str, int] = {}

    for log in logs:
        events_by_action[log.action] = events_by_action.get(log.action, 0) + 1
        events_by_resource_type[log.resource_type] = events_by_resource_type.get(
            log.resource_type, 0
        ) + 1

    return AuditLogSummary(
        total_events=len(logs),
        events_by_action=events_by_action,
        events_by_resource_type=events_by_resource_type,
        recent_activity_count=len(logs),
    )


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get a specific audit log entry by ID.

    Requires 'audit:read' permission.
    """
    require_permissions("audit:read")(current_user)

    from uuid import UUID

    try:
        UUID(log_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid audit log ID format")

    log = db.query(AuditLog).filter(AuditLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")

    return AuditLogResponse(
        id=str(log.id),
        user_id=str(log.user_id) if log.user_id else None,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=str(log.resource_id) if log.resource_id else None,
        details=log.details,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        created_at=log.created_at.isoformat() if log.created_at else "",
    )


@router.get("/user/{user_id}", response_model=AuditLogListResponse)
async def get_user_audit_logs(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get audit logs for a specific user.

    Requires 'audit:read' permission.
    """
    require_permissions("audit:read")(current_user)

    query = db.query(AuditLog).filter(AuditLog.user_id == user_id)
    total = query.count()

    offset = (page - 1) * page_size
    logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size).all()

    return AuditLogListResponse(
        logs=[
            AuditLogResponse(
                id=str(log.id),
                user_id=str(log.user_id) if log.user_id else None,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=str(log.resource_id) if log.resource_id else None,
                details=log.details,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                created_at=log.created_at.isoformat() if log.created_at else "",
            )
            for log in logs
        ],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(logs)) < total,
    )


@router.get("/actions/list")
async def list_available_actions(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get list of distinct action types in audit logs.

    Requires 'audit:read' permission.
    """
    require_permissions("audit:read")(current_user)

    actions = db.query(AuditLog.action).distinct().all()
    return {"actions": [a[0] for a in actions if a[0]]}


@router.get("/resource-types/list")
async def list_available_resource_types(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get list of distinct resource types in audit logs.

    Requires 'audit:read' permission.
    """
    require_permissions("audit:read")(current_user)

    resource_types = db.query(AuditLog.resource_type).distinct().all()
    return {"resource_types": [r[0] for r in resource_types if r[0]]}