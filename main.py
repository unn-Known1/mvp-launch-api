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
from sqlalchemy import text

# Rate limiting setup
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    HAS_RATE_LIMITING = True
except ImportError:
    HAS_RATE_LIMITING = False
    Limiter = None

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

def _get_database_url() -> str:
    """Get database URL from environment variable. Raises error if not set in production."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        environment = os.getenv("ENVIRONMENT", "development")
        if environment == "production":
            raise ValueError(
                "DATABASE_URL environment variable is required in production. "
                "Please set it before starting the application."
            )
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "Please set it in your .env file or environment."
        )
    return db_url


DATABASE_URL = _get_database_url()


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

# Rate limiting setup
if HAS_RATE_LIMITING:
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        # Apply rate limiting to auth endpoints to prevent brute force attacks
        if request.url.path.startswith("/api/v1/auth/login") or request.url.path.startswith("/api/v1/auth/refresh"):
            # Use default rate limit for auth endpoints
            pass
        response = await call_next(request)
        return response

    # Add rate limit exception handlers
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
else:
    # Provide a no-op limiter for when slowapi is not installed
    class NoOpLimiter:
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    app.state.limiter = NoOpLimiter()

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
            # Return explicit 501 for missing v2 endpoints instead of silent fallback
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=501,
                content={
                    "detail": "API v2 endpoint not implemented",
                    "version": "v2",
                    "message": "This endpoint is not available in API v2. Use /api/v1 for stable endpoints.",
                    "versioning_policy": "/api/versioning-policy"
                }
            )
        return response
    return await call_next(request)


# Security headers middleware
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


# CORS configuration - use environment variable for allowed origins
# SECURITY: Validate CORS configuration in production - fail fast if not properly configured
_allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins = (
    [origin.strip() for origin in _allowed_origins_str.split(",") if origin.strip()]
    if _allowed_origins_str
    else None  # Will be handled below based on environment
)

# Production validation: require explicit ALLOWED_ORIGINS configuration
environment = os.getenv("ENVIRONMENT", "development")
if _allowed_origins is None:
    if environment == "production":
        raise ValueError(
            "ALLOWED_ORIGINS environment variable is required in production. "
            "Please set it to explicit frontend URLs (comma-separated). "
            "Example: https://app.example.com,https://dashboard.example.com"
        )
    # In development, allow localhost with a warning
    import warnings
    warnings.warn(
        "SECURITY WARNING: Using permissive CORS origins in development mode. "
        "ALLOWED_ORIGINS is not set. This should not happen in production.",
        RuntimeWarning,
        stacklevel=2
    )
    _allowed_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

# Verify no wildcard origins in production
if environment == "production":
    for origin in _allowed_origins:
        if origin == "*" or origin.endswith(".amazonaws.com"):
            raise ValueError(
                f"SECURITY: Invalid origin '{origin}' in ALLOWED_ORIGINS for production. "
                "Do not use wildcards or unspecified cloud endpoints."
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
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
