"""
Anomaly detection service using statistical methods (z-score, IQR).
"""

import statistics
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from models import Anomaly, AnomalyThreshold, Dataset, DataRecord


def calculate_z_score(value: float, mean: float, std_dev: float) -> float:
    if std_dev == 0:
        return 0.0
    return abs((value - mean) / std_dev)


def calculate_iqr_bounds(
    values: list[float], multiplier: float = 3.0
) -> tuple[float, float]:
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    q1 = sorted_vals[n // 4]
    q3 = sorted_vals[(3 * n) // 4]
    iqr = q3 - q1
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr
    return lower, upper


def get_threshold_for_metric(
    db: Session, dataset_id: str, metric_name: str
) -> tuple[int, int, bool]:
    threshold = (
        db.query(AnomalyThreshold)
        .filter(
            AnomalyThreshold.dataset_id == dataset_id,
            AnomalyThreshold.metric_name == metric_name,
        )
        .first()
    )
    if threshold:
        return threshold.z_score_threshold, threshold.iqr_multiplier, threshold.enabled
    return 3, 3, True


def get_time_series_for_metric(
    db: Session, dataset_id: str, metric_name: str
) -> list[tuple[datetime, float]]:
    records = (
        db.query(DataRecord)
        .filter(DataRecord.dataset_id == dataset_id)
        .order_by(DataRecord.created_at)
        .all()
    )
    result = []
    for record in records:
        data = record.data
        if isinstance(data, dict) and metric_name in data:
            try:
                value = float(data[metric_name])
                result.append((record.created_at, value))
            except (ValueError, TypeError):
                continue
    return result


def detect_anomalies_for_metric(
    db: Session, dataset_id: str, metric_name: str, user_id: Optional[str] = None
) -> list[Anomaly]:
    z_threshold, iqr_multiplier, enabled = get_threshold_for_metric(
        db, dataset_id, metric_name
    )
    if not enabled:
        return []

    series = get_time_series_for_metric(db, dataset_id, metric_name)
    if len(series) < 3:
        return []

    values = [v for _, v in series]
    mean = statistics.mean(values)
    std_dev = statistics.stdev(values) if len(values) > 1 else 0
    iqr_lower, iqr_upper = calculate_iqr_bounds(values, iqr_multiplier)

    anomalies = []
    for timestamp, value in series:
        is_anomaly = False
        detection_method = []
        z_score_val = None
        severity = "low"

        z = calculate_z_score(value, mean, std_dev)
        if z > z_threshold:
            is_anomaly = True
            detection_method.append("z_score")
            z_score_val = f"{z:.2f}"
            if z > z_threshold * 2:
                severity = "high"
            elif z > z_threshold * 1.5:
                severity = "medium"

        if value < iqr_lower or value > iqr_upper:
            is_anomaly = True
            detection_method.append("iqr")
            if severity == "low":
                if value < iqr_lower * 0.5 or value > iqr_upper * 1.5:
                    severity = "high"
                else:
                    severity = "medium"

        if is_anomaly:
            existing = (
                db.query(Anomaly)
                .filter(
                    Anomaly.dataset_id == dataset_id,
                    Anomaly.metric_name == metric_name,
                    Anomaly.timestamp == timestamp,
                )
                .first()
            )
            if not existing:
                anomaly = Anomaly(
                    dataset_id=dataset_id,
                    metric_name=metric_name,
                    timestamp=timestamp,
                    expected_value=f"{mean:.2f}",
                    actual_value=f"{value:.2f}",
                    severity=severity,
                    detection_method=",".join(detection_method),
                    z_score=z_score_val,
                    iqr_lower=f"{iqr_lower:.2f}",
                    iqr_upper=f"{iqr_upper:.2f}",
                    status="flagged",
                )
                db.add(anomaly)
                anomalies.append(anomaly)

    db.commit()
    return anomalies


def scan_all_datasets(db: Session, user_id: Optional[str] = None) -> dict[str, int]:
    datasets = db.query(Dataset).filter(Dataset.status == "ready").all()
    results = {}
    for dataset in datasets:
        metric_names = extract_numeric_metrics(db, dataset.id)
        count = 0
        for metric in metric_names:
            anomalies = detect_anomalies_for_metric(
                db, dataset.id, metric, user_id
            )
            count += len(anomalies)
            if anomalies and user_id:
                create_notifications(db, user_id, anomalies)
        if count > 0:
            results[dataset.id] = count
    return results


def extract_numeric_metrics(db: Session, dataset_id: str) -> list[str]:
    sample = (
        db.query(DataRecord)
        .filter(DataRecord.dataset_id == dataset_id)
        .limit(10)
        .all()
    )
    metrics = set()
    for record in sample:
        if isinstance(record.data, dict):
            for key, val in record.data.items():
                try:
                    float(val)
                    metrics.add(key)
                except (ValueError, TypeError):
                    continue
    return list(metrics)


def create_notifications(
    db: Session, user_id: str, anomalies: list[Anomaly]
) -> None:
    from models import AnomalyNotification

    for anomaly in anomalies:
        notification = AnomalyNotification(
            user_id=user_id, anomaly_id=anomaly.id
        )
        db.add(notification)
    db.commit()


def update_anomaly_status(
    db: Session,
    anomaly_id: str,
    status: str,
    user_id: str,
    notes: Optional[str] = None,
) -> Optional[Anomaly]:
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        return None
    anomaly.status = status
    anomaly.investigated_by = user_id
    anomaly.investigated_at = datetime.utcnow()
    if notes:
        anomaly.notes = notes
    db.commit()
    return anomaly


def get_anomalies_for_user(
    db: Session, user_id: str, status: Optional[str] = None
) -> list[Anomaly]:
    query = (
        db.query(Anomaly)
        .join(Dataset, Anomaly.dataset_id == Dataset.id)
        .filter(Dataset.user_id == user_id)
    )
    if status:
        query = query.filter(Anomaly.status == status)
    return query.order_by(desc(Anomaly.timestamp)).all()


def set_metric_threshold(
    db: Session,
    dataset_id: str,
    metric_name: str,
    z_score_threshold: int = 3,
    iqr_multiplier: int = 3,
    enabled: bool = True,
) -> AnomalyThreshold:
    existing = (
        db.query(AnomalyThreshold)
        .filter(
            AnomalyThreshold.dataset_id == dataset_id,
            AnomalyThreshold.metric_name == metric_name,
        )
        .first()
    )
    if existing:
        existing.z_score_threshold = z_score_threshold
        existing.iqr_multiplier = iqr_multiplier
        existing.enabled = enabled
    else:
        existing = AnomalyThreshold(
            dataset_id=dataset_id,
            metric_name=metric_name,
            z_score_threshold=z_score_threshold,
            iqr_multiplier=iqr_multiplier,
            enabled=enabled,
        )
        db.add(existing)
    db.commit()
    return existing
