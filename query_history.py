"""
NL Query History Service
Stores and retrieves NL query history using the database models.
"""

from datetime import datetime, timezone

from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session

from models import NLQueryHistory, Base


class QueryHistoryService:
    """Service for managing NL query history."""

    def __init__(self, database_url: str = "sqlite:///query_history.db"):
        self.engine = create_engine(database_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def _get_session(self) -> Session:
        return self.SessionLocal()

    def store_query(
        self,
        user_id: str,
        natural_language_query: str,
        generated_sql: str | None = None,
        executed_sql: str | None = None,
        results: list | None = None,
        confidence_score: int | None = None,
        confidence_level: str | None = None,
        follow_up_questions: list[str] | None = None,
        execution_time_ms: int | None = None,
        row_count: int | None = None,
        error_message: str | None = None,
        status: str = "completed",
        data_source_id: str | None = None,
    ) -> NLQueryHistory:
        """Store a NL query in the history."""
        session = self._get_session()
        try:
            entry = NLQueryHistory(
                user_id=user_id,
                data_source_id=data_source_id,
                natural_language_query=natural_language_query,
                generated_sql=generated_sql,
                executed_sql=executed_sql,
                query_results=results,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
                follow_up_questions=follow_up_questions or [],
                execution_time_ms=execution_time_ms,
                row_count=row_count,
                error_message=error_message,
                status=status,
                created_at=datetime.now(timezone.utc),
            )
            session.add(entry)
            session.commit()
            session.refresh(entry)
            return entry
        finally:
            session.close()

    def get_user_history(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        data_source_id: str | None = None,
    ) -> list[NLQueryHistory]:
        """Get query history for a user."""
        session = self._get_session()
        try:
            query = session.query(NLQueryHistory).filter(
                NLQueryHistory.user_id == user_id
            )
            if data_source_id:
                query = query.filter(NLQueryHistory.data_source_id == data_source_id)
            return (
                query.order_by(desc(NLQueryHistory.created_at))
                .offset(offset)
                .limit(limit)
                .all()
            )
        finally:
            session.close()

    def get_by_id(self, query_id: str) -> NLQueryHistory | None:
        """Get a specific query by ID."""
        session = self._get_session()
        try:
            return session.query(NLQueryHistory).filter(
                NLQueryHistory.id == query_id
            ).first()
        finally:
            session.close()

    def delete_query(self, query_id: str, user_id: str) -> bool:
        """Delete a query from history (only if owned by user)."""
        session = self._get_session()
        try:
            entry = session.query(NLQueryHistory).filter(
                NLQueryHistory.id == query_id,
                NLQueryHistory.user_id == user_id,
            ).first()
            if entry:
                session.delete(entry)
                session.commit()
                return True
            return False
        finally:
            session.close()

    def get_recent_queries(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """Get recent queries formatted for sidebar display."""
        queries = self.get_user_history(user_id, limit=limit)
        return [
            {
                "id": str(q.id),
                "query": q.natural_language_query,
                "sql": q.generated_sql,
                "confidence": q.confidence_level,
                "status": q.status,
                "created_at": q.created_at.isoformat() if q.created_at else None,
            }
            for q in queries
        ]


# In-memory store for MVP (fallback when no DB is configured)
class InMemoryQueryHistory:
    """In-memory query history store for MVP development."""

    def __init__(self):
        self._store: dict[str, list[dict]] = {}

    def store_query(
        self,
        user_id: str,
        natural_language_query: str,
        generated_sql: str | None = None,
        executed_sql: str | None = None,
        results: list | None = None,
        confidence_score: int | None = None,
        confidence_level: str | None = None,
        follow_up_questions: list[str] | None = None,
        execution_time_ms: int | None = None,
        row_count: int | None = None,
        error_message: str | None = None,
        status: str = "completed",
        data_source_id: str | None = None,
    ) -> dict:
        """Store a query in memory."""
        import uuid
        entry = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "data_source_id": data_source_id,
            "natural_language_query": natural_language_query,
            "generated_sql": generated_sql,
            "executed_sql": executed_sql,
            "query_results": results,
            "confidence_score": confidence_score,
            "confidence_level": confidence_level,
            "follow_up_questions": follow_up_questions or [],
            "execution_time_ms": execution_time_ms,
            "row_count": row_count,
            "error_message": error_message,
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if user_id not in self._store:
            self._store[user_id] = []
        self._store[user_id].insert(0, entry)
        return entry

    def get_user_history(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        data_source_id: str | None = None,
    ) -> list[dict]:
        """Get query history for a user."""
        queries = self._store.get(user_id, [])
        if data_source_id:
            queries = [q for q in queries if q.get("data_source_id") == data_source_id]
        return queries[offset:offset + limit]

    def get_by_id(self, query_id: str) -> dict | None:
        """Get a specific query by ID."""
        for user_queries in self._store.values():
            for q in user_queries:
                if q["id"] == query_id:
                    return q
        return None

    def delete_query(self, query_id: str, user_id: str) -> bool:
        """Delete a query from history."""
        if user_id not in self._store:
            return False
        before = len(self._store[user_id])
        self._store[user_id] = [q for q in self._store[user_id] if q["id"] != query_id]
        return len(self._store[user_id]) < before

    def get_recent_queries(self, user_id: str, limit: int = 10) -> list[dict]:
        """Get recent queries formatted for sidebar display."""
        queries = self.get_user_history(user_id, limit=limit)
        return [
            {
                "id": q["id"],
                "query": q["natural_language_query"],
                "sql": q["generated_sql"],
                "confidence": q["confidence_level"],
                "status": q["status"],
                "created_at": q["created_at"],
            }
            for q in queries
        ]


# Global in-memory store for MVP
query_history_store = InMemoryQueryHistory()
