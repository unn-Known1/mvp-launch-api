# System Architecture - FOR-27

## Project Overview
MVP Launch - A platform with React/TypeScript frontend, Python FastAPI backend, ML capabilities (Prophet, NLP), deployed on AWS.

## Technical Stack
- **Frontend**: React + TypeScript, D3.js
- **Backend**: Python FastAPI + SQLAlchemy
- **ML**: Prophet, NLP pipeline
- **Infrastructure**: AWS (S3, RDS, Lambda), Docker, GitHub Actions

## 1. System Architecture Diagram

### 1.1 High-Level Component Architecture
```
┌─────────────────────────────────────────────────────────────────────┐
│                           Client Layer                              │
│  ┌─────────────────────┐   ┌─────────────────────┐                 │
│  │   React Frontend    │   │   D3.js Visualizer  │                 │
│  │   (SPA + TypeScript)│   │   (Charts/Graphs)  │                 │
│  └─────────┬───────────┘   └─────────┬───────────┘                 │
│            │                         │                             │
└────────────┼─────────────────────────┼─────────────────────────────┘
             │                         │
             ▼                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API Gateway Layer                           │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    FastAPI Application                        │  │
│  │  - Authentication/Authorization (JWT)                         │  │
│  │  - Rate Limiting                                             │  │
│  │  - Request Validation                                        │  │
│  │  - API Versioning                                            │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
             │
    ┌────────┴────────┬────────────────┬──────────────────┐
    ▼                 ▼                ▼                  ▼
┌─────────┐     ┌─────────┐    ┌─────────────┐    ┌─────────────┐
│  Core   │     │  ML     │    │   Data      │    │  External   │
│ Service │     │ Service │    │  Ingestion  │    │   Services  │
│         │     │         │    │             │    │             │
│ - Users │     │ - Prop- │    │ - S3 Batch  │    │ - Auth0/    │
│ - Auth  │     │   het    │    │ - API Poll  │    │   Cognito   │
│ - RBAC  │     │ - NLP   │    │ - Webhooks  │    │ - AWS S3    │
└─────────┘     └─────────┘    └─────────────┘    └─────────────┘
       │              │               │                  │
       └──────────────┴───────────────┴──────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Data Layer                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │
│  │   PostgreSQL    │  │      S3        │  │    Redis       │       │
│  │   (RDS/Aurora)  │  │   (Raw Data)   │  │   (Cache)      │       │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 AWS Deployment Architecture
- **Compute**: ECS Fargate for backend services, Lambda for ML inference
- **Data**: RDS PostgreSQL, S3 for file storage, ElastiCache Redis
- **Networking**: VPC with public/private subnets, ALB for load balancing
- **CI/CD**: GitHub Actions → ECR → ECS Fargate

### 1.3 Communication Patterns
- **Synchronous**: REST API (FastAPI) for client interactions
- **Asynchronous**: Redis/RQ for background job processing, EventBridge for event streaming

> **Note**: The architecture originally planned to use AWS SQS for background job processing, but the implementation uses Redis with RQ (Redis Queue) for task scheduling. This provides similar functionality with lower infrastructure complexity for MVP.

## 2. API Contract Definitions (OpenAPI 3.0)

### 2.1 API Structure
```
/api/v1/
├── /auth
│   ├── POST /login
│   ├── POST /logout
│   └── POST /refresh
├── /users
│   ├── GET /users
│   ├── GET /users/{id}
│   ├── POST /users
│   └── PATCH /users/{id}
├── /data
│   ├── GET /data
│   ├── POST /data
│   ├── GET /data/{id}
│   └── DELETE /data/{id}
├── /ml
│   ├── POST /ml/forecast
│   ├── POST /ml/analyze
│   └── GET /ml/models
└── /admin
    ├── GET /admin/users
    └── POST /admin/roles
```

### 2.2 Authentication Endpoints
- `POST /api/v1/auth/login` - User login, returns JWT
- `POST /api/v1/auth/logout` - Invalidate token
- `POST /api/v1/auth/refresh` - Refresh access token

### 2.3 Data Endpoints
- CRUD operations for core data entities
- Bulk import/export support
- Webhook callbacks for real-time updates

### 2.4 ML Endpoints
- `POST /api/v1/ml/forecast` - Prophet time-series forecasting
- `POST /api/v1/ml/analyze` - NLP text analysis

## 3. Database Schema Design

### 3.1 Core Entities
```python
# SQLAlchemy Models

class User(Base):
    __tablename__ = "users"
    id = Column(UUID, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role_id = Column(UUID, ForeignKey("roles.id"))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, onupdate=lambda: datetime.now(timezone.utc))

class Role(Base):
    __tablename__ = "roles"
    id = Column(UUID, primary_key=True)
    name = Column(String, unique=True)
    permissions = Column(JSON)

class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(UUID, primary_key=True)
    name = Column(String)
    user_id = Column(UUID, ForeignKey("users.id"))
    s3_key = Column(String)
    schema = Column(JSON)
    created_at = Column(DateTime)

class Forecast(Base):
    __tablename__ = "forecasts"
    id = Column(UUID, primary_key=True)
    dataset_id = Column(UUID, ForeignKey("datasets.id"))
    model_type = Column(String)
    predictions = Column(JSON)
    created_at = Column(DateTime)

class NLQueryHistory(Base):
    __tablename__ = "nl_query_history"
    id = Column(UUID, primary_key=True)
    user_id = Column(UUID, ForeignKey("users.id"))
    data_source_id = Column(String)
    natural_language_query = Column(Text)
    generated_sql = Column(Text)
    executed_sql = Column(Text)
    query_results = Column(JSON)
    confidence_score = Column(Integer)
    confidence_level = Column(String)
    follow_up_questions = Column(JSON)
    execution_time_ms = Column(Integer)
    row_count = Column(Integer)
    error_message = Column(Text)
    status = Column(String)
    created_at = Column(DateTime)
```

### 3.2 Entity Relationships
- User (1) → Role (many)
- User (1) → Dataset (many)
- Dataset (1) → Forecast (many)
- User (1) → NLQueryHistory (many)

## 4. Service Boundaries

### 4.1 Monolithic vs Microservices Decision
**Recommendation**: Monolithic FastAPI application for MVP
- Single deployable unit
- Simpler operations and debugging
- Lower infrastructure costs
- Easier team coordination

**Future consideration**: Split ML service into separate container when scale requires

### 4.2 Service Communication
- Internal function calls within FastAPI app
- External API integrations via dependency injection
- Background tasks via Celery or Python asyncio

## 5. Security Architecture

### 5.1 Authentication & Authorization
- JWT-based authentication with short-lived access tokens (15min)
- Refresh tokens stored in HTTP-only secure cookies
- OAuth 2.0 provider integration (Auth0/Cognito) for SSO

### 5.2 RBAC Implementation
```
Roles:
- admin: Full system access
- analyst: Data access, ML operations, no user management
- viewer: Read-only access to own data
```

### 5.3 Encryption
- **In Transit**: TLS 1.3 for all communications
- **At Rest**: AES-256 encryption on S3, RDS encryption enabled
- **Secrets**: AWS Secrets Manager for database credentials, API keys

### 5.4 Credential Storage
- Database credentials: AWS Secrets Manager
- JWT signing keys: Secrets Manager with rotation
- API keys: Environment variables or Secrets Manager

## 6. Performance Targets

### 6.1 Latency SLAs
- API responses: < 200ms (p95)
- ML inference: < 2s (p95)
- Page load: < 1.5s (First Contentful Paint)

### 6.2 Throughput
- Concurrent users: 100 (MVP target)
- API requests: 1000 req/min
- Data ingestion: 100 records/sec

### 6.3 Scalability Targets
- Horizontal scaling via ECS Auto Scaling
- Database read replicas for read-heavy workloads
- CloudFront CDN for static assets

## Deliverables Status
- [x] Architecture document (this file)
- [ ] OpenAPI specification (openapi.yaml)
- [ ] Database schema (models.py)
- [ ] Security architecture document
- [ ] Performance requirements document