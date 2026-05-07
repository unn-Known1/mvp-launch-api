"""
FastAPI router for anomaly detection endpoints.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from anomaly import (
    detect_anomalies_for_metric,
    set_metric_threshold,
    update_anomaly_status,
)
from auth import get_current_user
from database import get_db
from models import Anomaly, AnomalyNotification, AnomalyThreshold, Dataset

router = APIRouter(prefix="/api/v1/anomalies", tags=["Anomaly Detection"])


class ThresholdRequest(BaseModel):
    metric_name: str = Field(..., min_length=1)
    z_score_threshold: int = Field(default=3, ge=1, le=10)
    iqr_multiplier: int = Field(default=3, ge=1, le=10)
    enabled: bool = True


class ThresholdResponse(BaseModel):
    id: str
    dataset_id: str
    metric_name: str
    z_score_threshold: int
    iqr_multiplier: int
    enabled: bool


class AnomalyResponse(BaseModel):
    id: str
    dataset_id: str
    metric_name: str
    timestamp: str
    expected_value: Optional[str]
    actual_value: str
    severity: str
    detection_method: str
    status: str
    investigated_at: Optional[str]
    notes: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class UpdateAnomalyRequest(BaseModel):
    status: str = Field(..., pattern="^(investigated|dismissed)$")
    notes: Optional[str] = None


class NotificationResponse(BaseModel):
    id: str
    anomaly_id: str
    read: bool
    created_at: str
    anomaly: AnomalyResponse

    class Config:
        from_attributes = True


class ScanResponse(BaseModel):
    scanned_datasets: int
    total_anomalies_found: int
    anomalies_by_dataset: dict[str, int]


@router.post("/scan", response_model=ScanResponse)
def scan_for_anomalies(
    dataset_id: Optional[str] = Query(None),
    metric_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Run anomaly detection scan on all datasets or a specific dataset/metric."""
    total = 0
    results = {}
    query = db.query(Dataset).filter(
        Dataset.status == "ready", Dataset.user_id == current_user.id
    )
    datasets = query.all()
    if dataset_id:
        datasets = [d for d in datasets if str(d.id) == dataset_id]
    for ds in datasets:
        count = 0
        if metric_name:
            anomalies = detect_anomalies_for_metric(db, str(ds.id), metric_name)
            count = len(anomalies)
        else:
            from anomaly import extract_numeric_metrics

            metrics = extract_numeric_metrics(db, str(ds.id))
            for m in metrics:
                anomalies = detect_anomalies_for_metric(db, str(ds.id), m)
                count += len(anomalies)
        if count > 0:
            results[str(ds.id)] = count
        total += count
    return ScanResponse(
        scanned_datasets=len(datasets),
        total_anomalies_found=total,
        anomalies_by_dataset=results,
    )


@router.get("/", response_model=list[AnomalyResponse])
def list_anomalies(
    dataset_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None, pattern="^(flagged|investigated|dismissed)$"),
    severity: Optional[str] = Query(None, pattern="^(low|medium|high)$"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List anomalies with optional filters."""
    query = db.query(Anomaly).join(Dataset).filter(Dataset.user_id == current_user.id)
    if dataset_id:
        query = query.filter(Anomaly.dataset_id == dataset_id)
    if status:
        query = query.filter(Anomaly.status == status)
    if severity:
        query = query.filter(Anomaly.severity == severity)
    anomalies = query.order_by(Anomaly.timestamp.desc()).limit(100).all()
    return [
        AnomalyResponse(
            id=str(a.id),
            dataset_id=str(a.dataset_id),
            metric_name=a.metric_name,
            timestamp=a.timestamp.isoformat() if a.timestamp else "",
            expected_value=a.expected_value,
            actual_value=a.actual_value,
            severity=a.severity,
            detection_method=a.detection_method,
            status=a.status,
            investigated_at=(
                a.investigated_at.isoformat() if a.investigated_at else None
            ),
            notes=a.notes,
            created_at=a.created_at.isoformat() if a.created_at else "",
        )
        for a in anomalies
    ]


@router.patch("/{anomaly_id}", response_model=AnomalyResponse)
def update_anomaly(
    anomaly_id: str,
    req: UpdateAnomalyRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Mark an anomaly as investigated or dismissed."""
    anomaly = update_anomaly_status(
        db, anomaly_id, req.status, str(current_user.id), req.notes
    )
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return AnomalyResponse(
        id=str(anomaly.id),
        dataset_id=str(anomaly.dataset_id),
        metric_name=anomaly.metric_name,
        timestamp=anomaly.timestamp.isoformat() if anomaly.timestamp else "",
        expected_value=anomaly.expected_value,
        actual_value=anomaly.actual_value,
        severity=anomaly.severity,
        detection_method=anomaly.detection_method,
        status=anomaly.status,
        investigated_at=(
            anomaly.investigated_at.isoformat() if anomaly.investigated_at else None
        ),
        notes=anomaly.notes,
        created_at=anomaly.created_at.isoformat() if anomaly.created_at else "",
    )


@router.get("/notifications", response_model=list[NotificationResponse])
def get_notifications(
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get anomaly notifications for the current user."""
    query = db.query(AnomalyNotification).filter(
        AnomalyNotification.user_id == current_user.id
    )
    if unread_only:
        query = query.filter(AnomalyNotification.read.is_(False))
    notifications = (
        query.order_by(AnomalyNotification.created_at.desc()).limit(50).all()
    )
    return [
        NotificationResponse(
            id=str(n.id),
            anomaly_id=str(n.anomaly_id),
            read=n.read,
            created_at=n.created_at.isoformat() if n.created_at else "",
            anomaly=AnomalyResponse(
                id=str(n.anomaly.id),
                dataset_id=str(n.anomaly.dataset_id),
                metric_name=n.anomaly.metric_name,
                timestamp=(
                    n.anomaly.timestamp.isoformat() if n.anomaly.timestamp else ""
                ),
                expected_value=n.anomaly.expected_value,
                actual_value=n.anomaly.actual_value,
                severity=n.anomaly.severity,
                detection_method=n.anomaly.detection_method,
                status=n.anomaly.status,
                investigated_at=(
                    n.anomaly.investigated_at.isoformat()
                    if n.anomaly.investigated_at
                    else None
                ),
                notes=n.anomaly.notes,
                created_at=(
                    n.anomaly.created_at.isoformat() if n.anomaly.created_at else ""
                ),
            ),
        )
        for n in notifications
        if n.anomaly
    ]


@router.post("/notifications/{notification_id}/read", status_code=204)
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Mark a notification as read."""
    notification = (
        db.query(AnomalyNotification)
        .filter(
            AnomalyNotification.id == notification_id,
            AnomalyNotification.user_id == current_user.id,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.read = True
    db.commit()


@router.post("/thresholds", response_model=ThresholdResponse, status_code=201)
def create_or_update_threshold(
    req: ThresholdRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Set anomaly detection sensitivity threshold for a metric."""
    dataset_id = None
    threshold = set_metric_threshold(
        db,
        dataset_id or "",
        req.metric_name,
        req.z_score_threshold,
        req.iqr_multiplier,
        req.enabled,
    )
    return ThresholdResponse(
        id=str(threshold.id),
        dataset_id=str(threshold.dataset_id),
        metric_name=threshold.metric_name,
        z_score_threshold=threshold.z_score_threshold,
        iqr_multiplier=threshold.iqr_multiplier,
        enabled=threshold.enabled,
    )


@router.get("/thresholds", response_model=list[ThresholdResponse])
def list_thresholds(
    dataset_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List anomaly detection thresholds for current user's datasets."""
    query = (
        db.query(AnomalyThreshold)
        .join(Dataset)
        .filter(Dataset.user_id == current_user.id)
    )
    if dataset_id:
        query = query.filter(AnomalyThreshold.dataset_id == dataset_id)
    thresholds = query.all()
    return [
        ThresholdResponse(
            id=str(t.id),
            dataset_id=str(t.dataset_id),
            metric_name=t.metric_name,
            z_score_threshold=t.z_score_threshold,
            iqr_multiplier=t.iqr_multiplier,
            enabled=t.enabled,
        )
        for t in thresholds
    ]
