"""
NL Query API Router
FastAPI router for natural language to SQL translation and query execution.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth import get_current_user
from connectors import create_connector, data_source_store
from connectors.base import DataSourceConfig
from nl_langchain import create_translator_from_env
from nl_to_sql import ConfidenceLevel, NLQueryResult, SchemaInfo
from query_history import query_history_store

router = APIRouter(prefix="/api/v1/nl-query", tags=["NL Query"])


# --- Request/Response Models ---


class NLQueryRequest(BaseModel):
    query: str
    data_source_id: str
    execute: bool = True
    max_rows: int = 10000


class RephraseRequest(BaseModel):
    query: str
    error_message: str


class SchemaRequest(BaseModel):
    data_source_id: str


class NLQueryResponse(BaseModel):
    id: str | None = None
    natural_language_query: str
    generated_sql: str | None = None
    executed_sql: str | None = None
    results: list[dict[str, Any]] | None = None
    row_count: int | None = None
    confidence_score: int | None = None
    confidence_level: str | None = None
    confidence_indicator: str | None = None
    follow_up_questions: list[str] = []
    error_message: str | None = None
    execution_time_ms: int | None = None
    status: str = "completed"
    created_at: str | None = None


class RephraseResponse(BaseModel):
    original_query: str
    suggestions: list[str]
    reason: str


class QueryHistoryItem(BaseModel):
    id: str
    query: str
    sql: str | None = None
    confidence: str | None = None
    status: str
    created_at: str


class QueryHistoryResponse(BaseModel):
    queries: list[QueryHistoryItem]
    total: int


# --- Helpers ---


def _get_datasource_config(data_source_id: str, user_id: str = "") -> DataSourceConfig:
    """Retrieve and validate data source configuration with user ownership check.
    
    NEW-004 FIX: Now verifies user ownership at store level to prevent access bypass.
    """
    config = data_source_store.get(data_source_id, user_id=user_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source not found or access denied: {data_source_id}",
        )
    return config


def _get_schema_info(config: DataSourceConfig) -> SchemaInfo:
    """Get schema info from a data source connector."""
    try:
        connector = create_connector(config)
        raw_schema = connector.get_schema_info()

        tables = []
        relationships = []

        # Parse raw schema into SchemaInfo format
        if isinstance(raw_schema, dict):
            if "tables" in raw_schema:
                raw_tables = raw_schema["tables"]
                relationships = raw_schema.get("relationships", [])
            else:
                raw_tables = [raw_schema]
        elif isinstance(raw_schema, list):
            raw_tables = raw_schema
        else:
            raw_tables = []

        # Convert connector format to SchemaInfo format
        for t in raw_tables:
            table_name = t.get("table") or t.get("name") or t.get("table_name", "")
            tables.append(
                {
                    "name": table_name,
                    "columns": t.get("columns", []),
                    "row_count": t.get("row_count"),
                }
            )

        return SchemaInfo(tables=tables, relationships=relationships)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve schema: {str(e)}",
        )


def _nl_result_to_response(
    result: NLQueryResult, stored_id: str | None = None
) -> NLQueryResponse:
    """Convert NLQueryResult to API response."""
    confidence_indicator = None
    if result.confidence_level:
        if result.confidence_level == ConfidenceLevel.HIGH:
            confidence_indicator = "high"
        elif result.confidence_level == ConfidenceLevel.MEDIUM:
            confidence_indicator = "medium"
        else:
            confidence_indicator = "low"

    return NLQueryResponse(
        id=stored_id,
        natural_language_query=result.natural_language_query,
        generated_sql=result.generated_sql,
        executed_sql=result.executed_sql,
        results=result.results,
        row_count=result.row_count,
        confidence_score=result.confidence_score,
        confidence_level=(
            result.confidence_level.value if result.confidence_level else None
        ),
        confidence_indicator=confidence_indicator,
        follow_up_questions=result.follow_up_questions,
        error_message=result.error_message,
        execution_time_ms=result.execution_time_ms,
        status="completed" if not result.error_message else "error",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


# --- Endpoints ---


@router.post("/translate", response_model=NLQueryResponse)
async def translate_query(
    request: NLQueryRequest, current_user=Depends(get_current_user)
):
    """
    Translate a natural language query to SQL with confidence scoring.
    Optionally executes the query if execute=True.
    """
    config = _get_datasource_config(request.data_source_id, str(current_user.id))
    schema_info = _get_schema_info(config)

    translator = create_translator_from_env()
    result = translator.translate(
        natural_language_query=request.query,
        schema_info=schema_info,
        dialect=config.db_type,
        data_source_id=request.data_source_id,
    )

    executed_sql = None
    query_results = None
    row_count = None
    error_message = result.error_message

    if request.execute and result.generated_sql and not result.error_message:
        try:
            connector = create_connector(config)
            query_results, row_count, exec_error = translator.execute_query(
                sql=result.generated_sql,
                connector=connector,
                max_rows=request.max_rows,
            )
            if exec_error:
                error_message = exec_error
            else:
                executed_sql = result.generated_sql
                result.results = query_results
                result.row_count = row_count

                # Generate follow-up questions
                follow_ups = translator.generate_followup_questions(
                    natural_language_query=request.query,
                    generated_sql=result.generated_sql,
                    results=query_results[:10],
                )
                result.follow_up_questions = follow_ups

        except Exception as e:
            error_message = f"Query execution failed: {str(e)}"

    # Store in history
    stored = query_history_store.store_query(
        user_id=str(current_user.id),
        natural_language_query=request.query,
        generated_sql=result.generated_sql,
        executed_sql=executed_sql,
        results=query_results,
        confidence_score=result.confidence_score,
        confidence_level=(
            result.confidence_level.value if result.confidence_level else None
        ),
        follow_up_questions=result.follow_up_questions,
        execution_time_ms=result.execution_time_ms,
        row_count=row_count,
        error_message=error_message,
        status="completed" if not error_message else "error",
        data_source_id=request.data_source_id,
    )

    response = _nl_result_to_response(result, stored_id=stored["id"])
    response.error_message = error_message
    return response


@router.post("/suggest-rephrase", response_model=RephraseResponse)
async def suggest_rephrase(
    request: RephraseRequest, current_user=Depends(get_current_user)
):
    """
    Suggest rephrasing for a failed or ambiguous query.
    """
    translator = create_translator_from_env()
    suggestion = translator.suggest_rephrase(
        natural_language_query=request.query,
        error_message=request.error_message,
    )
    return RephraseResponse(
        original_query=suggestion.original_query,
        suggestions=suggestion.suggestions,
        reason=suggestion.reason,
    )


@router.get("/schema", response_model=dict)
async def get_schema(data_source_id: str, current_user=Depends(get_current_user)):
    """
    Get the database schema for a data source (for prompt construction).
    """
    config = _get_datasource_config(data_source_id, str(current_user.id))
    schema_info = _get_schema_info(config)
    return {
        "data_source_id": data_source_id,
        "schema": schema_info.to_prompt_text(),
        "tables": schema_info.tables,
        "relationships": schema_info.relationships,
    }


@router.get("/history", response_model=QueryHistoryResponse)
async def get_query_history(
    limit: int = 50,
    offset: int = 0,
    data_source_id: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """
    Get NL query history for the current user.
    """
    queries = query_history_store.get_user_history(
        user_id=str(current_user.id),
        limit=limit,
        offset=offset,
        data_source_id=data_source_id,
    )
    total = len(query_history_store.get_user_history(str(current_user.id)))

    return QueryHistoryResponse(
        queries=[
            QueryHistoryItem(
                id=q["id"],
                query=q["natural_language_query"],
                sql=q.get("generated_sql"),
                confidence=q.get("confidence_level"),
                status=q.get("status", "completed"),
                created_at=q.get("created_at", ""),
            )
            for q in queries
        ],
        total=total,
    )


@router.get("/history/{query_id}", response_model=NLQueryResponse)
async def get_query_by_id(query_id: str, current_user=Depends(get_current_user)):
    """
    Get a specific query from history by ID.
    NEW-007 FIX: Add UUID format validation before passing to store.
    """
    from uuid import UUID
    try:
        UUID(query_id)  # Validate UUID format
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid query ID format",
        )
    entry = query_history_store.get_by_id(query_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found",
        )
    if entry["user_id"] != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found",
        )

    return NLQueryResponse(
        id=entry["id"],
        natural_language_query=entry["natural_language_query"],
        generated_sql=entry.get("generated_sql"),
        executed_sql=entry.get("executed_sql"),
        results=entry.get("query_results"),
        row_count=entry.get("row_count"),
        confidence_score=entry.get("confidence_score"),
        confidence_level=entry.get("confidence_level"),
        confidence_indicator=entry.get("confidence_level"),
        follow_up_questions=entry.get("follow_up_questions", []),
        error_message=entry.get("error_message"),
        execution_time_ms=entry.get("execution_time_ms"),
        status=entry.get("status", "completed"),
        created_at=entry.get("created_at", ""),
    )


@router.delete("/history/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_query(query_id: str, current_user=Depends(get_current_user)):
    """
    Delete a query from history.
    """
    success = query_history_store.delete_query(query_id, str(current_user.id))
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found",
        )


@router.get("/recent", response_model=list[QueryHistoryItem])
async def get_recent_queries(current_user=Depends(get_current_user), limit: int = 10):
    """
    Get recent queries for sidebar display.
    """
    queries = query_history_store.get_recent_queries(str(current_user.id), limit=limit)
    return [
        QueryHistoryItem(
            id=q["id"],
            query=q["query"],
            sql=q.get("sql"),
            confidence=q.get("confidence"),
            status=q.get("status", "completed"),
            created_at=q.get("created_at", ""),
        )
        for q in queries
    ]


@router.post("/confidence", response_model=dict)
async def get_confidence(
    request: NLQueryRequest, current_user=Depends(get_current_user)
):
    """
    Get confidence score for a NL-to-SQL translation without executing.
    """
    config = _get_datasource_config(request.data_source_id, str(current_user.id))
    schema_info = _get_schema_info(config)

    translator = create_translator_from_env()
    result = translator.translate(
        natural_language_query=request.query,
        schema_info=schema_info,
        dialect=config.db_type,
        data_source_id=request.data_source_id,
    )

    return {
        "query": request.query,
        "generated_sql": result.generated_sql,
        "confidence_score": result.confidence_score,
        "confidence_level": (
            result.confidence_level.value if result.confidence_level else None
        ),
        "confidence_indicator": (
            result.confidence_level.value if result.confidence_level else None
        ),
    }
