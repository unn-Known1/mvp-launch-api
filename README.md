# MVP Launch API

A FastAPI-based backend for the MVP Launch platform, providing data ingestion, forecasting, NLP, and anomaly detection capabilities.

## Features

- **Data Ingestion**: CSV upload and database connectors
- **Natural Language Query**: SQL generation from natural language
- **Anomaly Detection**: Real-time anomaly detection in time series data
- **Forecasting**: Predictive analytics using Prophet and scikit-learn
- **RESTful API**: FastAPI with automatic OpenAPI documentation

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker (optional, for containerized deployment)

## Setup

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd mvp-launch-api
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/app_db"
   export REDIS_URL="redis://localhost:6379/0"
   ```

5. **Initialize the database**
   ```bash
   python init_db.py
   ```

6. **Run the application**
   ```bash
   python main.py
   # or
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### Docker

1. **Build the Docker image**
   ```bash
   docker build -t mvp-launch-api .
   ```

2. **Run the container**
   ```bash
   docker run -p 8000:8000 -e DATABASE_URL="postgresql://..." mvp-launch-api
   ```

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI spec**: http://localhost:8000/openapi.json

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=. --cov-report=term

# Run specific test file
pytest tests/test_anomaly.py -v
```

## Project Structure

```
mvp-launch-api/
├── main.py                 # FastAPI application entry point
├── database.py            # Database configuration
├── models.py              # SQLAlchemy models
├── anomaly.py             # Anomaly detection logic
├── anomaly_router.py      # Anomaly detection API routes
├── nl_to_sql.py           # Natural language to SQL conversion
├── nl_query_router.py     # NLP query API routes
├── csv_upload_router.py   # CSV upload API routes
├── query_history.py       # Query history management
├── connectors/            # Database connectors
├── tests/                 # Test suite
├── infrastructure/        # Terraform and deployment configs
├── .github/workflows/     # CI/CD pipeline
├── Dockerfile             # Docker configuration
├── requirements.txt       # Python dependencies
└── alembic/               # Database migrations
```

## Contributing

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to this project.

## License

This project is proprietary and confidential. All rights reserved.