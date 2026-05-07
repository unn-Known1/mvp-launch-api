"""
Tests for NL-to-SQL Translation Engine
"""

import pytest

from nl_to_sql import (
    NLToSQLTranslator,
    SchemaInfo,
    ConfidenceLevel,
    RephraseSuggestion,
)
from query_history import InMemoryQueryHistory


# --- Fixtures ---

@pytest.fixture
def schema_info():
    return SchemaInfo(
        tables=[
            {
                "name": "sales",
                "columns": [
                    {"name": "id", "type": "INTEGER", "nullable": False},
                    {"name": "amount", "type": "DECIMAL", "nullable": False},
                    {"name": "category", "type": "VARCHAR", "nullable": True},
                    {"name": "created_at", "type": "TIMESTAMP", "nullable": False},
                ],
                "row_count": 5000,
            },
            {
                "name": "users",
                "columns": [
                    {"name": "id", "type": "INTEGER", "nullable": False},
                    {"name": "name", "type": "VARCHAR", "nullable": False},
                    {"name": "email", "type": "VARCHAR", "nullable": False},
                ],
                "row_count": 150,
            },
        ],
        relationships=[
            {"from_table": "sales", "from_column": "user_id", "to_table": "users", "to_column": "id"},
        ],
    )


@pytest.fixture
def translator():
    return NLToSQLTranslator()


@pytest.fixture
def query_history():
    return InMemoryQueryHistory()


# --- SchemaInfo Tests ---

class TestSchemaInfo:
    def test_to_prompt_text(self, schema_info):
        text = schema_info.to_prompt_text()
        assert "Table: sales" in text
        assert "Table: users" in text
        assert "amount (DECIMAL" in text
        assert "approx. 5000 rows" in text
        assert "sales.user_id -> users.id" in text

    def test_empty_schema(self):
        schema = SchemaInfo()
        text = schema.to_prompt_text()
        assert text == ""


# --- NLToSQLTranslator Tests ---

class TestNLToSQLTranslator:
    def test_translate_basic_query(self, translator, schema_info):
        result = translator.translate(
            "Show me all sales data",
            schema_info,
            dialect="postgresql",
        )
        assert result.generated_sql is not None
        assert "SELECT" in result.generated_sql
        assert result.confidence_score is not None
        assert result.confidence_level is not None

    def test_translate_count_query(self, translator, schema_info):
        result = translator.translate(
            "Count the number of rows in sales",
            schema_info,
        )
        assert result.generated_sql is not None
        assert "COUNT" in result.generated_sql

    def test_translate_count_grouped(self, translator, schema_info):
        result = translator.translate(
            "Count sales by category",
            schema_info,
        )
        assert result.generated_sql is not None
        assert "GROUP BY" in result.generated_sql or "group by" in result.generated_sql.lower()

    def test_translate_average(self, translator, schema_info):
        result = translator.translate(
            "What is the average amount of sales?",
            schema_info,
        )
        assert result.generated_sql is not None
        assert "AVG" in result.generated_sql or "avg" in result.generated_sql.lower()

    def test_translate_sum(self, translator, schema_info):
        result = translator.translate(
            "What is the total sales amount?",
            schema_info,
        )
        assert result.generated_sql is not None
        assert "SUM" in result.generated_sql or "sum" in result.generated_sql.lower()

    def test_translate_top_results(self, translator, schema_info):
        result = translator.translate(
            "Show me the top 10 sales by amount",
            schema_info,
        )
        assert result.generated_sql is not None
        assert "ORDER BY" in result.generated_sql
        assert "LIMIT" in result.generated_sql

    def test_translate_with_limit(self, translator, schema_info):
        result = translator.translate(
            "List 50 sales records",
            schema_info,
        )
        assert result.generated_sql is not None
        assert "LIMIT 50" in result.generated_sql or "LIMIT  50" in result.generated_sql

    def test_confidence_high_for_valid_sql(self, translator, schema_info):
        result = translator.translate(
            "Show me all data from sales",
            schema_info,
        )
        assert result.confidence_level in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM]
        assert result.confidence_score > 0

    def test_confidence_low_for_ambiguous(self, translator, schema_info):
        result = translator.translate(
            "Show me stuff",
            schema_info,
        )
        assert result.confidence_score is not None

    def test_execution_time_recorded(self, translator, schema_info):
        result = translator.translate(
            "Show me all sales",
            schema_info,
        )
        assert result.execution_time_ms is not None
        assert result.execution_time_ms >= 0

    def test_query_history_updated(self, translator, schema_info):
        initial_count = len(translator.get_query_history())
        translator.translate("Show me sales", schema_info)
        assert len(translator.get_query_history()) == initial_count + 1

    def test_translate_different_dialects(self, translator, schema_info):
        result_pg = translator.translate("Show sales", schema_info, dialect="postgresql")
        result_mysql = translator.translate("Show sales", schema_info, dialect="mysql")
        assert result_pg.generated_sql is not None
        assert result_mysql.generated_sql is not None


# --- Follow-up Questions Tests ---

class TestFollowUpQuestions:
    def test_generate_followup(self, translator):
        results = [{"amount": 100, "category": "Electronics"}]
        questions = translator.generate_followup_questions(
            "Show me sales by category",
            "SELECT category, COUNT(*) FROM sales GROUP BY category",
            results,
        )
        assert isinstance(questions, list)
        assert len(questions) <= 3

    def test_followup_empty_results(self, translator):
        questions = translator.generate_followup_questions(
            "Show me sales",
            "SELECT * FROM sales",
            [],
        )
        assert isinstance(questions, list)


# --- Rephrase Suggestion Tests ---

class TestRephraseSuggestion:
    def test_suggest_rephrase(self, translator):
        suggestion = translator.suggest_rephrase(
            "gimme data",
            "Query could not be parsed",
        )
        assert isinstance(suggestion, RephraseSuggestion)
        assert suggestion.original_query == "gimme data"
        assert len(suggestion.suggestions) <= 3
        assert suggestion.reason != ""

    def test_rephrase_has_suggestions(self, translator):
        suggestion = translator.suggest_rephrase(
            "bad query",
            "Invalid SQL",
        )
        assert len(suggestion.suggestions) > 0
        for s in suggestion.suggestions:
            assert isinstance(s, str)
            assert len(s) > 0


# --- Confidence Parsing Tests ---

class TestConfidenceParsing:
    def test_parse_valid_confidence(self, translator):
        response = '{"score": 85, "level": "HIGH", "reasoning": "Good match"}'
        score, level, reasoning = translator.parse_confidence_response(response)
        assert score == 85
        assert level == ConfidenceLevel.HIGH
        assert "Good match" in reasoning

    def test_parse_low_confidence(self, translator):
        response = '{"score": 30, "level": "LOW", "reasoning": "Unclear"}'
        score, level, reasoning = translator.parse_confidence_response(response)
        assert score == 30
        assert level == ConfidenceLevel.LOW

    def test_parse_invalid_json(self, translator):
        score, level, reasoning = translator.parse_confidence_response("not json")
        assert score == 30
        assert level == ConfidenceLevel.LOW
        assert "Could not parse" in reasoning

    def test_parse_medium_confidence(self, translator):
        response = '{"score": 65, "level": "MEDIUM", "reasoning": "Okay"}'
        score, level, _ = translator.parse_confidence_response(response)
        assert level == ConfidenceLevel.MEDIUM


# --- Query History Service Tests ---

class TestInMemoryQueryHistory:
    def test_store_query(self, query_history):
        entry = query_history.store_query(
            user_id="user-1",
            natural_language_query="Show me sales",
            generated_sql="SELECT * FROM sales",
            confidence_level="high",
            status="completed",
        )
        assert entry["id"] is not None
        assert entry["natural_language_query"] == "Show me sales"
        assert entry["confidence_level"] == "high"

    def test_get_user_history(self, query_history):
        query_history.store_query(user_id="user-1", natural_language_query="Query 1")
        query_history.store_query(user_id="user-1", natural_language_query="Query 2")
        query_history.store_query(user_id="user-2", natural_language_query="Query 3")

        history = query_history.get_user_history(user_id="user-1")
        assert len(history) == 2
        assert history[0]["natural_language_query"] == "Query 2"

    def test_get_user_history_with_limit(self, query_history):
        for i in range(10):
            query_history.store_query(user_id="user-1", natural_language_query=f"Query {i}")
        history = query_history.get_user_history(user_id="user-1", limit=5)
        assert len(history) == 5

    def test_get_by_id(self, query_history):
        entry = query_history.store_query(user_id="user-1", natural_language_query="Find me")
        retrieved = query_history.get_by_id(entry["id"])
        assert retrieved is not None
        assert retrieved["natural_language_query"] == "Find me"

    def test_delete_query(self, query_history):
        entry = query_history.store_query(user_id="user-1", natural_language_query="To delete")
        result = query_history.delete_query(entry["id"], user_id="user-1")
        assert result is True
        assert query_history.get_by_id(entry["id"]) is None

    def test_delete_other_user_query(self, query_history):
        entry = query_history.store_query(user_id="user-1", natural_language_query="Protected")
        result = query_history.delete_query(entry["id"], user_id="user-2")
        assert result is False

    def test_get_recent_queries(self, query_history):
        for i in range(5):
            query_history.store_query(user_id="user-1", natural_language_query=f"Q{i}")
        recent = query_history.get_recent_queries(user_id="user-1", limit=3)
        assert len(recent) == 3
        assert recent[0]["query"] == "Q4"

    def test_store_with_data_source(self, query_history):
        query_history.store_query(
            user_id="user-1",
            natural_language_query="Query with DS",
            data_source_id="ds-123",
        )
        history = query_history.get_user_history(user_id="user-1", data_source_id="ds-123")
        assert len(history) == 1


# --- Integration Tests ---

class TestIntegration:
    def test_full_translation_flow(self, translator, schema_info):
        result = translator.translate(
            "Show me the total sales amount",
            schema_info,
        )
        assert result.natural_language_query == "Show me the total sales amount"
        assert result.generated_sql is not None
        assert result.confidence_score is not None
        assert result.confidence_level is not None
        assert result.execution_time_ms is not None

    def test_error_handling(self, translator):
        schema = SchemaInfo(tables=[])
        result = translator.translate("Show me data", schema)
        assert result.generated_sql is not None
        assert result.confidence_score is not None
