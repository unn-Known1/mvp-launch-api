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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
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