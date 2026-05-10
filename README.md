# Forge Intelligence — MVP Launch API

A FastAPI-based backend for the Forge Intelligence BI platform, providing data ingestion, natural-language querying, forecasting, anomaly detection, and automated reporting. Built with Python, PostgreSQL (pgvector), Redis, and AWS.

## Project Status

| Feature | Status | Details |
|---------|--------|---------|
| Database schema (pgvector, pooling) | ✅ Done | Core entities, pgvector for embeddings |
| RBAC and authentication | ✅ Done | JWT auth, role-based access, token blacklisting |
| Automated reporting engine | ✅ Done | AI summaries, scheduled report generation |
| Predictive analytics (Prophet) | ✅ Done | Time-series forecasting with Prophet |
| Anomaly detection system | ✅ Done | Real-time Z-score based anomaly detection |
| Infrastructure (Terraform + AWS) | ✅ Done | CI/CD pipeline, ECS Fargate, RDS, S3 |
| Chart generation & visualization | ✅ Done | Backend chart rendering layer |
| Frontend project setup | ✅ Done | React + TypeScript + Vite |
| Natural Language Query | ✅ Done | NL-to-SQL via LangChain pipeline |
| Data connectors (CSV, DB) | ✅ Done | CSV auto-detection, SQL connectors |
| Dashboard & Data Visualization UI | ✅ Done | Interactive dashboards with D3.js |
| Dataset Management UI | ✅ Done | Dataset CRUD, schema management |
| Anomaly Detection Dashboard | ✅ Done | Anomaly visualization panel |
| Real-Time Anomaly Alerts | ✅ Done | WebSocket-based alert system |
| User Onboarding Flow | ✅ Done | Guided onboarding |
| Data Export Download | ✅ Done | CSV/JSON export |
| E2E Integration Tests | ✅ Done | End-to-end test suite |
| Report Scheduling UI | ✅ Done | Frontend schedule configuration |
| API Versioning Strategy | ✅ Done | Versioned API routes |
| Frontend Bundle Optimization | ✅ Done | Code splitting, lazy loading |
| Observability Wiring | ✅ Done | Structured logging, metrics |

## Features

- **Data Ingestion** — CSV upload with auto-schema detection, PostgreSQL and MySQL connectors
- **Natural Language Query** — Ask questions in plain English; LangChain translates to SQL
- **Anomaly Detection** — Real-time Z-score based detection in time-series data
- **Forecasting** — Predictive analytics with Prophet and scikit-learn
- **Automated Reporting** — AI-generated report summaries with scheduling
- **Role-Based Access Control** — JWT authentication with granular permissions
- **RESTful API** — Auto-documented OpenAPI 3.0 endpoints

## Architecture

See the full architecture and security documents:

- [System Architecture](ARCHITECTURE.md) — component diagram, data flow, deployment topology
- [Security Architecture](SECURITY.md) — auth, encryption, VPC layout, incident response
- [OpenAPI Specification](openapi.yaml) — full API contract (1768 lines)

## API Examples

### Authentication

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "your-password"}'

# Response
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "expires_in": 900
}
```

### Natural Language Query

```bash
curl -X POST http://localhost:8000/api/v1/nl/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me total sales by region for last quarter"}'

# Response
{
  "generated_sql": "SELECT region, SUM(sales) FROM orders WHERE created_at >= NOW() - INTERVAL '3 months' GROUP BY region",
  "results": [...],
  "confidence_score": 92,
  "confidence_level": "high",
  "follow_up_questions": ["Would you like to see a breakdown by month?"],
  "execution_time_ms": 145
}
```

### Anomaly Detection

```bash
curl -X POST http://localhost:8000/api/v1/anomaly/detect \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"dataset_id": "uuid", "metric": "page_views", "window": "24h"}'

# Response
{
  "anomalies": [
    {"timestamp": "2026-05-01T14:00:00Z", "value": 12450, "z_score": 3.8, "severity": "high"}
  ],
  "threshold": 3.0,
  "total_points_analyzed": 1440
}
```

### Forecasting

```bash
curl -X POST http://localhost:8000/api/v1/ml/forecast \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"dataset_id": "uuid", "periods": 30, "interval": "daily"}'

# Response
{
  "forecast": [
    {"ds": "2026-06-01", "yhat": 15200, "yhat_lower": 14100, "yhat_upper": 16300}
  ],
  "model": "prophet",
  "metrics": {"mae": 320, "rmse": 410}
}
```

## Prerequisites

- Python 3.11+
- PostgreSQL 15+ (with pgvector extension for embeddings)
- Redis 7+
- Node.js 20+ (for frontend development)
- Docker (optional, for containerized deployment)

## Setup

### Local Development (Backend)

```bash
# Clone and enter
git clone https://github.com/unn-Known1/mvp-launch-api.git
cd mvp-launch-api

# Virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Environment variables
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/app_db"
export REDIS_URL="redis://localhost:6379/0"
export SECRET_KEY="your-secret-key"

# Initialize database
python init_db.py

# Run server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Local Development (Frontend)

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server runs on `http://localhost:5173` and proxies API requests to the backend.

### Docker

```bash
docker build -t mvp-launch-api .
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql://postgres:postgres@host.docker.internal:5432/app_db" \
  -e REDIS_URL="redis://host.docker.internal:6379/0" \
  mvp-launch-api
```

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI spec**: http://localhost:8000/openapi.json

## Testing

```bash
# Backend tests
pytest tests/ -v
pytest tests/ -v --cov=. --cov-report=term
pytest tests/test_anomaly.py -v

# Frontend tests (when frontend directory present)
cd frontend && npm test
```

## Project Structure

```
mvp-launch-api/
├── main.py                 # FastAPI entry point
├── database.py             # DB config + pgvector
├── models.py               # SQLAlchemy ORM models (with soft delete)
├── auth.py                 # JWT auth + RBAC logic + API key support
├── auth_router.py          # Auth endpoints (paginated)
├── role_router.py          # Role management endpoints
├── anomaly.py              # Anomaly detection engine (with email notifications)
├── anomaly_router.py       # Anomaly API routes (with date filtering, bulk delete)
├── forecast.py             # Prophet forecasting
├── forecast_router.py      # Forecasting API routes (with task queue, caching)
├── ml_workers.py           # Async ML worker tasks
├── nl_langchain.py         # LangChain NL pipeline
├── nl_to_sql.py            # NL-to-SQL translator (refactored)
├── nl_query_router.py      # Query API routes
├── csv_upload_router.py    # CSV ingestion
├── query_history.py        # Query history + follow-ups
├── report_router.py        # Report generation (refactored)
├── audit_router.py         # Audit log query API (NEW)
├── connectors/             # External DB connectors
│   ├── base.py           # Base connector (circuit breaker, retry)
│   ├── postgres.py
│   ├── mysql.py
│   ├── encryption.py      # Credential encryption
│   └── store.py          # Thread-safe in-memory store
├── services/
│   └── storage.py        # StorageBackend ABC + S3Storage (NEW)
├── frontend/               # React + TypeScript SPA
│   ├── src/
│   └── package.json
├── tests/                  # Pytest suite
│   ├── test_anomaly.py
│   ├── test_auth.py
│   ├── test_auth_router.py      (NEW)
│   ├── test_role_router.py       (NEW)
│   ├── test_connectors_router.py (NEW)
│   └── test_ml_workers.py
├── infrastructure/         # Terraform + deployment
│   └── terraform/
├── .github/workflows/      # CI/CD pipeline
├── alembic/                # DB migrations
├── openapi.yaml            # API contract
├── Dockerfile
├── requirements.txt
├── ARCHITECTURE.md
├── SECURITY.md
├── PERFORMANCE.md
├── CI-CD-SETUP-GUIDE.md
└── bug_report.md          # Full bug fix documentation (NEW)
```

## Contributing

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Proprietary and confidential. All rights reserved. &copy; Forge Intelligence
