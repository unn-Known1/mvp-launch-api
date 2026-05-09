"""
FastAPI router for CSV file upload and auto-detection pipeline.
"""

import io
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from auth import get_current_user
from database import SessionLocal
from models import DataRecord, Dataset, ImportBatch

router = APIRouter(prefix="/api/v1/csv", tags=["CSV Upload"])


# --- Response Models ---


class ColumnTypeInfo(BaseModel):
    name: str
    inferred_type: str
    sample_values: list


class CSVDetectionResponse(BaseModel):
    filename: str
    row_count: int
    column_count: int
    columns: list[ColumnTypeInfo]
    preview: list[dict]


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    row_count: int
    size_bytes: int
    status: str
    dataset_schema: Optional[dict] = Field(None, alias="schema")
    created_at: Optional[datetime] = None


class ImportBatchResponse(BaseModel):
    id: str
    dataset_id: str
    source_type: str
    status: str
    total_rows: int
    processed_rows: int
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class CSVUploadResponse(BaseModel):
    dataset: DatasetResponse
    import_batch: ImportBatchResponse
    detection: CSVDetectionResponse


# --- Dependency ---


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Type Detection Helpers ---


def detect_column_type(series: pd.Series) -> str:
    """Auto-detect column type based on pandas dtype and value analysis."""
    dtype_str = str(series.dtype)

    if dtype_str.startswith("int") or dtype_str.startswith("float"):
        return "number"
    elif dtype_str.startswith("bool"):
        return "boolean"
    elif dtype_str.startswith("datetime"):
        return "date"
    else:
        try:
            pd.to_datetime(series.dropna().head(100), errors="raise")
            return "date"
        except (ValueError, TypeError):
            pass

        try:
            pd.to_numeric(series.dropna().head(100), errors="raise")
            return "number"
        except (ValueError, TypeError):
            pass

        unique_vals = series.dropna().unique()
        if len(unique_vals) <= 2 and all(
            str(v).lower() in ("true", "false", "1", "0", "yes", "no")
            for v in unique_vals
        ):
            return "boolean"

    return "string"


def analyze_csv_types(df: pd.DataFrame) -> list[ColumnTypeInfo]:
    """Detect types for all columns in a DataFrame."""
    columns = []
    for col in df.columns:
        series = df[col]
        inferred_type = detect_column_type(series)
        sample_values = series.dropna().head(5).tolist()
        columns.append(
            ColumnTypeInfo(
                name=str(col),
                inferred_type=inferred_type,
                sample_values=sample_values,
            )
        )
    return columns


# --- Endpoints ---


@router.post("/detect", response_model=CSVDetectionResponse)
async def detect_csv_types(
    file: UploadFile = File(...), current_user=Depends(get_current_user)
):
    """Upload a CSV file and auto-detect column types without storing."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    contents = await file.read()
    if len(contents) > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 100MB limit")

    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

    columns = analyze_csv_types(df)
    preview = df.head(10).to_dict(orient="records")

    return CSVDetectionResponse(
        filename=file.filename,
        row_count=len(df),
        column_count=len(df.columns),
        columns=columns,
        preview=preview,
    )


@router.post("/upload", response_model=CSVUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    dataset_name: Optional[str] = None,
    description: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Upload a CSV file, auto-detect types, and store in database."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    contents = await file.read()
    file_size = len(contents)
    if file_size > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 100MB limit")

    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

    name = dataset_name or file.filename
    columns = analyze_csv_types(df)
    schema = {"columns": [{"name": c.name, "type": c.inferred_type} for c in columns]}

    dataset = Dataset(
        name=name,
        description=description or f"Uploaded from {file.filename}",
        user_id=str(current_user.id),
        schema=schema,
        row_count=len(df),
        size_bytes=file_size,
        status="processing",
    )
    db.add(dataset)
    db.flush()

    import_batch = ImportBatch(
        dataset_id=dataset.id,
        source_type="csv",
        source_path=file.filename,
        status="processing",
        total_rows=len(df),
    )
    db.add(import_batch)
    db.flush()

    try:
        records = []
        for _, row in df.iterrows():
            record = DataRecord(
                dataset_id=dataset.id,
                import_batch_id=import_batch.id,
                data=row.to_dict(),
            )
            records.append(record)
        db.bulk_save_objects(records)

        import_batch.status = "completed"
        import_batch.processed_rows = len(df)
        import_batch.completed_at = datetime.now(timezone.utc)
        dataset.status = "ready"

        db.commit()
    except Exception as e:
        db.rollback()
        import_batch.status = "failed"
        import_batch.error_message = str(e)
        dataset.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to store data: {str(e)}")

    detection = CSVDetectionResponse(
        filename=file.filename,
        row_count=len(df),
        column_count=len(df.columns),
        columns=columns,
        preview=df.head(10).to_dict(orient="records"),
    )

    return CSVUploadResponse(
        dataset=DatasetResponse(
            id=str(dataset.id),
            name=dataset.name,
            description=dataset.description,
            row_count=dataset.row_count,
            size_bytes=dataset.size_bytes,
            status=dataset.status,
            dataset_schema=dataset.schema,
            created_at=dataset.created_at,
        ),
        import_batch=ImportBatchResponse(
            id=str(import_batch.id),
            dataset_id=str(import_batch.dataset_id),
            source_type=import_batch.source_type,
            status=import_batch.status,
            total_rows=import_batch.total_rows,
            processed_rows=import_batch.processed_rows,
            created_at=import_batch.created_at,
            completed_at=import_batch.completed_at,
        ),
        detection=detection,
    )


@router.get("/datasets", response_model=list[DatasetResponse])
def list_csv_datasets(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    """List all CSV-imported datasets for the current user."""
    datasets = (
        db.query(Dataset)
        .filter(Dataset.schema.isnot(None), Dataset.user_id == current_user.id)
        .all()
    )
    return [
        DatasetResponse(
            id=str(d.id),
            name=d.name,
            description=d.description,
            row_count=d.row_count,
            size_bytes=d.size_bytes,
            status=d.status,
            dataset_schema=d.schema,
            created_at=d.created_at,
        )
        for d in datasets
    ]
