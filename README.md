# 🧠 Forge Intelligence — BI Platform MVP

FastAPI backend for an AI-powered Business Intelligence platform. Ingest data, ask questions in plain English, get forecasts, and catch anomalies — automatically.

![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge)
![AI](https://img.shields.io/badge/AI-Powered-FF6B6B?style=for-the-badge)

## ✨ Features

- **💬 Natural language queries** — ask your data questions in plain English, get SQL + results
- **📈 Forecasting** — time-series predictions using statistical models
- **🚨 Anomaly detection** — automated flagging of unusual data patterns
- **📊 Automated reports** — scheduled email reports with visualizations
- **🔍 Vector search** — semantic search across your data using pgvector embeddings
- **⚡ Real-time ingestion** — REST API for streaming data from any source

## 🚀 Quick Start

```bash
git clone https://github.com/unn-known1/mvp-launch-api.git
cd mvp-launch-api
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` for the interactive API docs.

## 🔌 Key Endpoints

```
POST /ingest          — Stream data into the platform
POST /query          — Natural language query → SQL + results
GET  /forecast/{metric}  — Get forecasts for a metric
GET  /anomalies      — Pull detected anomalies
GET  /reports        — List scheduled reports
POST /reports        — Create a new scheduled report
```

## 🏗️ Stack

- **Backend:** FastAPI + Python 3.11+
- **Database:** PostgreSQL + pgvector (vector embeddings)
- **AI/ML:** scikit-learn (forecasting), LLM integration (NL query)
- **Frontend:** React + TypeScript (separate repo)

## 💡 Use Cases

- BI dashboards that non-technical stakeholders can actually use
- Automated anomaly alerting (fraud, data quality issues, drops)
- Business metric forecasting without a data science team
- Self-serve reporting without SQL knowledge

## ⭐ If this helped you, star the repo!

MIT License — built with 💻 by [Gaurang Patel](https://github.com/unn-known1)