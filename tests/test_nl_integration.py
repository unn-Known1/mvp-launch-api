"""
Integration tests for NL-to-SQL with mocked connectors.
"""

import pytest
from unittest.mock import MagicMock, patch

from nl_to_sql import NLToSQLTranslator, SchemaInfo, ConfidenceLevel
from query_history import InMemoryQueryHistory


def make_mock_connector():
    """Create a mock connector that returns test data."""
    connector = MagicMock()

    # Mock get_schema_info
    def mock_get_schema():
        return {
            "tables": [
                {
                    "name": "sales",
                    "columns": [
                        {"name": "id", "type": "INTEGER", "nullable": False},
                        {"name": "amount", "type": "DECIMAL", "nullable": False},
                        {"name": "category", "type": "VARCHAR", "nullable": True},
                    ],
                }
            ]
        }

    # Mock execute_query
    def mock_execute(sql, params=None):
        return [
            {"id": 1, "amount": 100.0, "category": "Electronics"},
            {"id": 2, "amount": 200.0, "category": "Books"},
        ]

    connector.get_schema_info = mock_get_schema
    connector.execute_query = mock_execute
    return connector


class TestNLToSQLIntegration:
    def test_full_translation_and_execution(self):
        """Test full flow: NL -> SQL -> execution -> history."""
        translator = NLToSQLTranslator()
        history = InMemoryQueryHistory()

        schema = SchemaInfo(
            tables=[
                {
                    "name": "sales",
                    "columns": [
                        {"name": "id", "type": "INTEGER"},
                        {"name": "amount", "type": "DECIMAL"},
                    ],
                }
            ]
        )

        # Step 1: Translate
        result = translator.translate(
            "Show me all sales",
            schema,
            data_source_id="ds-123",
        )
        assert result.generated_sql is not None
        assert result.confidence_level is not None

        # Step 2: Execute (mocked)
        mock_connector = make_mock_connector()
        results, row_count, error = translator.execute_query(
            result.generated_sql, mock_connector
        )
        assert error is None
        assert len(results) == 2
        assert row_count == 2
        result.results = results
        result.row_count = row_count

        # Step 3: Generate follow-ups
        follow_ups = translator.generate_followup_questions(
            result.natural_language_query, result.generated_sql, results
        )
        assert len(follow_ups) <= 3
        result.follow_up_questions = follow_ups

        # Step 4: Store in history
        stored = history.store_query(
            user_id="user-1",
            natural_language_query=result.natural_language_query,
            generated_sql=result.generated_sql,
            executed_sql=result.generated_sql,
            results=results,
            confidence_score=result.confidence_score,
            confidence_level=result.confidence_level.value if result.confidence_level else None,
            follow_up_questions=result.follow_up_questions,
        )
        assert stored["id"] is not None
        assert stored["natural_language_query"] == "Show me all sales"

        # Step 5: Retrieve from history
        retrieved = history.get_by_id(stored["id"])
        assert retrieved is not None
        assert retrieved["generated_sql"] == result.generated_sql

    def test_error_handling_with_rephrase(self):
        """Test error handling and rephrase suggestions."""
        translator = NLToSQLTranslator()

        suggestion = translator.suggest_rephrase(
            "gimme data now!!!",
            "SQL syntax error near 'gimme'",
        )
        assert len(suggestion.suggestions) > 0
        assert suggestion.original_query == "gimme data now!!!"
        assert suggestion.reason != ""

    def test_confidence_low_triggers_rephrase(self):
        """Test that low confidence queries get rephrase suggestions."""
        translator = NLToSQLTranslator()
        schema = SchemaInfo(tables=[])

        result = translator.translate("???", schema)
        assert result.confidence_score is not None
        # Low confidence should trigger rephrase suggestion
        if result.confidence_score < 50:
            suggestion = translator.suggest_rephrase(
                result.natural_language_query,
                "Low confidence translation",
            )
            assert len(suggestion.suggestions) > 0

    def test_query_history_sidebar_format(self):
        """Test that history is correctly formatted for sidebar."""
        history = InMemoryQueryHistory()

        for i in range(5):
            history.store_query(
                user_id="user-1",
                natural_language_query=f"Query {i}",
                generated_sql=f"SELECT * FROM table_{i}",
                confidence_level="high" if i % 2 == 0 else "low",
            )

        recent = history.get_recent_queries("user-1", limit=3)
        assert len(recent) == 3
        assert recent[0]["query"] == "Query 4"
        assert "sql" in recent[0]

    def test_different_query_types(self):
        """Test different types of NL queries."""
        translator = NLToSQLTranslator()
        schema = SchemaInfo(
            tables=[
                {
                    "name": "sales",
                    "columns": [
                        {"name": "amount", "type": "DECIMAL"},
                        {"name": "category", "type": "VARCHAR"},
                    ],
                }
            ]
        )

        queries = [
            ("Count sales by category", "GROUP BY"),
            ("Total sales amount", "SUM"),
            ("Average amount", "AVG"),
            ("Top 10 sales", "ORDER BY"),
        ]

        for nl_query, expected_keyword in queries:
            result = translator.translate(nl_query, schema)
            assert result.generated_sql is not None
            assert expected_keyword in result.generated_sql or expected_keyword.lower() in result.generated_sql.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
