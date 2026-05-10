"""
FastAPI main application for MVP Launch platform.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sentry_sdk
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

# Initialize Sentry error tracking before app setup
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.1)

from anomaly_router import router as anomaly_router
from auth import seed_default_roles
from auth_router import router as auth_router
from connectors.router import router as connectors_router
from csv_upload_router import router as csv_upload_router
from database import SessionLocal, engine
from forecast_router import router as forecast_router
from nl_query_router import router as nl_query_router
from report_router import router as report_router
from role_router import router as role_router

# API versioning configuration
API_VERSIONS = {
    "v1": {
        "prefix": "/api/v1",
        "status": "stable",
        "deprecation_date": None,
        "sunset_date": None,
    },
    "v2": {
        "prefix": "/api/v2",
        "status": "beta",
        "deprecation_date": None,
        "sunset_date": None,
    },
}

# v2 router placeholders
v2_router_v1_alias = APIRouter(prefix="/api/v2")

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/app_db"
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    print(
        f"Starting MVP Launch API - Database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}"
    )
    db = SessionLocal()
    try:
        seed_default_roles(db)
    finally:
        db.close()
    yield
    print("Shutting down MVP Launch API")
    engine.dispose()


app = FastAPI(
    title="MVP Launch API",
    description="API for MVP Launch platform - data ingestion, forecasting, NLP, and anomaly detection.",
    version="1.1.0",
    lifespan=lifespan,
)

# API versioning middleware - inject version headers and deprecation warnings
@app.middleware("http")
async def versioning_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path

    # Determine API version from path prefix
    if path.startswith("/api/v1/"):
        response.headers["X-API-Version"] = "1"
        response.headers["X-API-Status"] = "stable"
    elif path.startswith("/api/v2/"):
        response.headers["X-API-Version"] = "2"
        response.headers["X-API-Status"] = "beta"
        response.headers["X-API-Deprecated"] = "true"
        response.headers["Sunset"] = "Fri, 31 Dec 2027 23:59:59 GMT"

    # Add versioning policy link
    response.headers["X-API-Versioning-Policy"] = "/api/versioning-policy"

    return response


@app.get("/api/versioning-policy")
async def versioning_policy():
    return {
        "versions": {
            "v1": {
                "prefix": "/api/v1",
                "status": "stable",
                "deprecation_date": None,
                "sunset_date": "2027-12-31",
                "migration_guide": "/docs#migration-v1-to-v2",
            },
            "v2": {
                "prefix": "/api/v2",
                "status": "beta",
                "deprecation_date": "2026-06-30",
                "sunset_date": "2027-12-31",
                "changelog": "/docs#v2-changelog",
            },
        },
        "recommendation": "Use the latest stable version (/api/v1) for production workloads. "
        "Evaluate /api/v2 for new integrations.",
    }


# Redirect v2 requests that don't have explicit handlers to v1 as fallback
@app.middleware("http")
async def v2_fallback_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/v2/") and not any(
        path.startswith(p) for p in ["/api/v2/docs", "/api/v2/openapi.json"]
    ):
        response = await call_next(request)
        if response.status_code == 404:
            v1_path = path.replace("/api/v2/", "/api/v1/", 1)
            if request.url.query:
                v1_path += "?" + request.url.query
            return RedirectResponse(url=v1_path, status_code=307)
        return response
    return await call_next(request)


# CORS configuration - use environment variable for allowed origins
# CWE-942: Never use "*" with allow_credentials=True in production
_allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins = (
    [origin.strip() for origin in _allowed_origins_str.split(",") if origin.strip()]
    if _allowed_origins_str
    else [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(role_router)
app.include_router(connectors_router)
app.include_router(nl_query_router)
app.include_router(anomaly_router)
app.include_router(csv_upload_router)
app.include_router(report_router)
app.include_router(forecast_router)

# Backward compatibility redirects for route standardisation
# Old /auth/* -> /api/v1/auth/*, old /nl-query/* -> /api/v1/nl-query/*

@app.middleware("http")
async def redirect_old_routes(request, call_next):
    old_prefixes = {
        "/auth/": "/api/v1/auth/",
        "/nl-query/": "/api/v1/nl-query/",
    }
    path = request.url.path
    for old_prefix, new_prefix in old_prefixes.items():
        if path.startswith(old_prefix):
            new_path = path.replace(old_prefix, new_prefix, 1)
            if request.url.query:
                new_path += "?" + request.url.query
            return RedirectResponse(url=new_path, status_code=308)
    return await call_next(request)


@app.get("/")
async def root():
    return {"service": "MVP Launch API", "version": "1.1.0", "status": "running"}


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
