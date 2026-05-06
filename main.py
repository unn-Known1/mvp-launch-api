"""
FastAPI main application for MVP Launch platform.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import SessionLocal, engine
from models import Base
from connectors.router import router as connectors_router
from anomaly_router import router as anomaly_router
from nl_query_router import router as nl_query_router
from csv_upload_router import router as csv_upload_router


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/app_db"
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    print(f"Starting MVP Launch API - Database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
    yield
    print("Shutting down MVP Launch API")
    engine.dispose()


app = FastAPI(
    title="MVP Launch API",
    description="API for MVP Launch platform - data ingestion, forecasting, NLP, and anomaly detection.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration - use environment variable for allowed origins
# CWE-942: Never use "*" with allow_credentials=True in production
_allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins = (
    [origin.strip() for origin in _allowed_origins_str.split(",") if origin.strip()]
    if _allowed_origins_str
    else ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(connectors_router)
app.include_router(nl_query_router)
app.include_router(anomaly_router)
app.include_router(csv_upload_router)


@app.get("/")
async def root():
    return {"service": "MVP Launch API", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health_check():
    db = SessionLocal()
    try:
        db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "healthy", "database": "disconnected", "error": str(e)}
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)