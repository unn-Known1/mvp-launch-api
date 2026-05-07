"""
Anomaly detection service using statistical methods (z-score, IQR).
Supports model versioning, evaluation metrics, and configurable detection.
"""

import hashlib
import json
import statistics
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from models import Anomaly, AnomalyThreshold, Dataset, DataRecord


def calculate_z_score(value: float, mean: float, std_dev: float) -> float:
    if std_dev == 0:
        return 0.0
    return abs((value - mean) / std_dev)


def calculate_iqr_bounds(
    values: list[float], multiplier: float = 3.0
) -> tuple[float, float]:
    """Calculate IQR bounds using proper percentile interpolation."""
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 0:
        return 0.0, 0.0
    if n == 1:
        return sorted_vals[0], sorted_vals[0]
    if n == 2:
        q1 = sorted_vals[0]
        q3 = sorted_vals[1]
        iqr = q3 - q1
        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr
        return lower, upper

    def percentile(data: list[float], p: float) -> float:
        k = (len(data) - 1) * (p / 100.0)
        f = int(k)
        c = f + 1
        if c >= len(data):
            return data[f]
        d0 = data[f] * (c - k)
        d1 = data[c] * (k - f)
        return d0 + d1

    q1 = percentile(sorted_vals, 25.0)
    q3 = percentile(sorted_vals, 75.0)
    iqr = q3 - q1
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr
    return lower, upper


def compute_anomaly_scores(
    values: list[float],
    z_threshold: float = 3.0,
    iqr_multiplier: float = 3.0,
) -> dict[str, Any]:
    """Compute comprehensive anomaly evaluation scores for a dataset."""
    if len(values) < 3:
        return {
            "num_points": len(values),
            "anomaly_count": 0,
            "anomaly_rate": 0.0,
            "mean": 0.0,
            "std_dev": 0.0,
            "skewness": 0.0,
            "kurtosis": 0.0,
            "max_z_score": 0.0,
            "detection_summary": {"z_score": 0, "iqr": 0, "both": 0},
        }

    mean = statistics.mean(values)
    std_dev = statistics.stdev(values) if len(values) > 1 else 0.0
    iqr_lower, iqr_upper = calculate_iqr_bounds(values, iqr_multiplier)

    z_score_count = 0
    iqr_count = 0
    both_count = 0
    max_z = 0.0

    for v in values:
        z = calculate_z_score(v, mean, std_dev)
        max_z = max(max_z, z)
        is_z = z > z_threshold
        is_iqr = v < iqr_lower or v > iqr_upper
        if is_z and is_iqr:
            both_count += 1
        elif is_z:
            z_score_count += 1
        elif is_iqr:
            iqr_count += 1

    total_anomalies = z_score_count + iqr_count + both_count
    anomaly_rate = total_anomalies / len(values) if values else 0.0

    skewness = 0.0
    kurtosis = 0.0
    if std_dev > 0 and len(values) >= 3:
        skewness = sum(((v - mean) / std_dev) ** 3 for v in values) / len(values)
        kurtosis = sum(((v - mean) / std_dev) ** 4 for v in values) / len(values) - 3.0

    return {
        "num_points": len(values),
        "anomaly_count": total_anomalies,
        "anomaly_rate": round(anomaly_rate, 4),
        "mean": round(mean, 4),
        "std_dev": round(std_dev, 4),
        "skewness": round(skewness, 4),
        "kurtosis": round(kurtosis, 4),
        "max_z_score": round(max_z, 4),
        "iqr_lower": round(iqr_lower, 4),
        "iqr_upper": round(iqr_upper, 4),
        "detection_summary": {
            "z_score": z_score_count,
            "iqr": iqr_count,
            "both": both_count,
        },
    }


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

    model_version = compute_model_version(
        z_threshold=z_threshold,
        iqr_multiplier=iqr_multiplier,
        data_hash=hashlib.md5(json.dumps(sorted(values), default=str).encode()).hexdigest()[:8],
    )

    anomalies = []
    for timestamp, value in series:
        is_anomaly = False
        detection_method = []
        z_score_val = None
        severity = "low"
        confidence = 0.0

        z = calculate_z_score(value, mean, std_dev)
        if z > z_threshold:
            is_anomaly = True
            detection_method.append("z_score")
            z_score_val = f"{z:.2f}"
            if z > z_threshold * 2:
                severity = "high"
                confidence = min(0.95, 0.7 + (z / (z_threshold * 4)))
            elif z > z_threshold * 1.5:
                severity = "medium"
                confidence = min(0.85, 0.5 + (z / (z_threshold * 4)))
            else:
                confidence = 0.4 + (z / (z_threshold * 4))

        if value < iqr_lower or value > iqr_upper:
            is_anomaly = True
            detection_method.append("iqr")
            iqr_range = iqr_upper - iqr_lower if iqr_upper != iqr_lower else 1.0
            _ = abs(value - (iqr_lower + iqr_range / 2)) / iqr_range
            if severity == "low":
                if value < iqr_lower * 0.5 or value > iqr_upper * 1.5:
                    severity = "high"
                    confidence = max(confidence, 0.85)
                else:
                    severity = "medium"
                    confidence = max(confidence, 0.6)
            else:
                confidence = max(confidence, min(0.95, confidence + 0.1))

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
                    model_version=model_version,
                    confidence=round(confidence, 4),
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
    from uuid import UUID

    try:
        user_uuid = UUID(user_id)
    except (ValueError, AttributeError):
        return

    for anomaly in anomalies:
        notification = AnomalyNotification(
            user_id=user_uuid, anomaly_id=anomaly.id
        )
        db.add(notification)
    db.commit()


def compute_model_version(
    z_threshold: float, iqr_multiplier: float, data_hash: str
) -> str:
    """Compute a deterministic model version string from hyperparameters and data."""
    version_input = f"z={z_threshold}:iqr={iqr_multiplier}:data={data_hash}"
    return hashlib.sha256(version_input.encode()).hexdigest()[:12]


def update_anomaly_status(
    db: Session,
    anomaly_id: str,
    status: str,
    user_id: str,
    notes: Optional[str] = None,
) -> Optional[Anomaly]:
    from uuid import UUID
    try:
        anomaly_uuid = UUID(anomaly_id)
    except (ValueError, AttributeError):
        return None
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_uuid).first()
    if not anomaly:
        return None
    anomaly.status = status
    try:
        anomaly.investigated_by = UUID(user_id)
    except (ValueError, AttributeError):
        pass
    anomaly.investigated_at = datetime.now(timezone.utc)
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
