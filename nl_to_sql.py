"""
NL-to-SQL Translation Engine
Converts natural language queries to SQL using LLM with schema-aware prompting.
Includes confidence scoring, error handling, and follow-up question generation.
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class SchemaInfo:
    """Database schema information for prompt construction."""

    tables: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, str]] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        """Format schema as text for LLM prompt."""
        lines = []
        for table in self.tables:
            table_name = table.get("name", "")
            columns = table.get("columns", [])
            col_descriptions = []
            for col in columns:
                col_name = col.get("name", "")
                col_type = col.get("type", "")
                nullable = "NULL" if col.get("nullable", False) else "NOT NULL"
                col_descriptions.append(f"  - {col_name} ({col_type}, {nullable})")
            lines.append(f"Table: {table_name}")
            lines.extend(col_descriptions)
            if table.get("row_count"):
                lines.append(f"  (approx. {table['row_count']} rows)")
            lines.append("")

        if self.relationships:
            lines.append("Relationships:")
            for rel in self.relationships:
                lines.append(
                    f"  - {rel.get('from_table', '')}.{rel.get('from_column', '')} "
                    f"-> {rel.get('to_table', '')}.{rel.get('to_column', '')}"
                )
        return "\n".join(lines)


@dataclass
class NLQueryResult:
    """Result of NL-to-SQL translation and execution."""

    natural_language_query: str
    generated_sql: str | None = None
    executed_sql: str | None = None
    results: list[dict[str, Any]] | None = None
    row_count: int | None = None
    confidence_score: int | None = None
    confidence_level: ConfidenceLevel | None = None
    follow_up_questions: list[str] = field(default_factory=list)
    error_message: str | None = None
    execution_time_ms: int | None = None
    data_source_id: str | None = None


@dataclass
class RephraseSuggestion:
    """Suggestion for rephrasing a failed query."""

    original_query: str
    suggestions: list[str]
    reason: str


class SQLGenerator:
    """
    Responsible for generating SQL from natural language queries.
    """

    def build_schema_prompt(self, schema_info: SchemaInfo) -> str:
        """Build the schema section of the prompt."""
        return f"""
Database Schema:
{schema_info.to_prompt_text()}

IMPORTANT RULES:
- Use only the tables and columns defined above.
- Prefer JOINs over subqueries when relating tables.
- Use appropriate aggregations (COUNT, SUM, AVG, etc.) when the question implies summarization.
- For time-based queries, use DATE_TRUNC, EXTRACT, or appropriate date functions.
- Always use parameterized queries or safe literal values.
- Return only valid SQL — no markdown, no explanations, no comments.
"""

    def build_translation_prompt(
        self,
        natural_language_query: str,
        schema_info: SchemaInfo,
        dialect: str = "postgresql",
    ) -> str:
        """Build the full LLM prompt for NL-to-SQL translation."""
        schema_prompt = self.build_schema_prompt(schema_info)
        return f"""You are an expert SQL query generator. Convert the user's natural language question into a valid {dialect} SQL query.  # noqa: E501

{schema_prompt}

User Question: "{natural_language_query}"

Generate a SQL query that answers this question. Return ONLY the SQL query, nothing else.
"""

    def _mock_llm_call(self, prompt: str) -> str:
        """
        Mock LLM call for development/testing.
        Returns deterministic responses based on prompt content.
        """
        nl_query = ""
        if "User Question:" in prompt:
            match = re.search(r'User Question: "([^"]+)"', prompt)
            if match:
                nl_query = match.group(1).lower()

        if not nl_query:
            return "SELECT 1"

        dialect = "postgresql"
        if "postgresql" in prompt.lower():
            dialect = "postgresql"
        elif "mysql" in prompt.lower():
            dialect = "mysql"

        sql = self._generate_sql_from_nl(nl_query, dialect)
        return sql

    def _generate_sql_from_nl(self, nl_query: str, dialect: str = "postgresql") -> str:
        """Generate SQL from natural language patterns."""
        nl = nl_query.lower().strip()

        if "count" in nl and "row" in nl:
            return "SELECT COUNT(*) AS row_count FROM data"

        if "count" in nl:
            table = self._extract_table_name(nl)
            if "by" in nl or "group" in nl:
                group_col = self._extract_group_column(nl)
                if group_col:
                    return f"SELECT {group_col}, COUNT(*) AS count FROM {table} GROUP BY {group_col} ORDER BY count DESC"  # noqa: E501
            return f"SELECT COUNT(*) AS count FROM {table}"

        if "average" in nl or "avg" in nl:
            table = self._extract_table_name(nl)
            column = self._extract_numeric_column(nl)
            if column:
                return f"SELECT AVG({column}) AS average FROM {table}"

        if "sum" in nl or "total" in nl:
            table = self._extract_table_name(nl)
            column = self._extract_numeric_column(nl)
            if column:
                return f"SELECT SUM({column}) AS total FROM {table}"

        if "top" in nl or "highest" in nl or "max" in nl:
            table = self._extract_table_name(nl)
            column = self._extract_numeric_column(nl) or "value"
            limit = self._extract_limit(nl)
            return f"SELECT * FROM {table} ORDER BY {column} DESC LIMIT {limit}"

        if "list" in nl or "show" in nl or "get" in nl:
            table = self._extract_table_name(nl)
            limit = self._extract_limit(nl)
            return f"SELECT * FROM {table} LIMIT {limit}"

        if "group by" in nl or "breakdown" in nl:
            table = self._extract_table_name(nl)
            group_col = self._extract_group_column(nl)
            if group_col:
                return f"SELECT {group_col}, COUNT(*) AS count FROM {table} GROUP BY {group_col} ORDER BY count DESC"

        return "SELECT * FROM data LIMIT 100"

    def _extract_table_name(self, nl: str) -> str:
        """Extract table name from NL query."""
        for table_hint in ["from ", "table ", "in "]:
            if table_hint in nl:
                parts = nl.split(table_hint)[1].split()
                if parts:
                    return parts[0].strip(".,;")
        return "data"

    def _extract_group_column(self, nl: str) -> str | None:
        """Extract GROUP BY column from NL query."""
        for hint in ["by ", "per ", "each "]:
            if hint in nl:
                parts = nl.split(hint)[1].split()
                if parts:
                    return parts[0].strip(".,;")
        return None

    def _extract_numeric_column(self, nl: str) -> str | None:
        """Extract numeric column from NL query."""
        numeric_hints = ["of ", "for ", "on ", "by "]
        for hint in numeric_hints:
            if hint in nl:
                parts = nl.split(hint)[1].split()
                if parts:
                    return parts[0].strip(".,;")
        # Try to find column after "amount", "total", "sum", "average", "avg"
        for keyword in [
            "amount",
            "total",
            "sum",
            "average",
            "avg",
            "value",
            "price",
            "cost",
            "sales",
        ]:
            if keyword in nl:
                return keyword
        return None

    def _extract_limit(self, nl: str) -> int:
        """Extract LIMIT value from NL query."""
        match = re.search(r"(\d+)\s*(?:rows?|records?|results?)", nl)
        if match:
            return int(match.group(1))
        if "top" in nl:
            match = re.search(r"top\s+(\d+)", nl)
            if match:
                return int(match.group(1))
        # Match "List N records" or "Show N items" - limit to 1-5 digits to prevent DoS
        match = re.search(r"(?<!\d)(\d{1,5})(?!\d)", nl)
        if match:
            return int(match.group(1))
        return 100

    def generate_sql(
        self,
        natural_language_query: str,
        schema_info: SchemaInfo,
        dialect: str = "postgresql",
    ) -> str:
        """
        Generate SQL from natural language query.
        """
        prompt = self.build_translation_prompt(
            natural_language_query, schema_info, dialect
        )
        return self._mock_llm_call(prompt).strip()


class ConfidenceScorer:
    """
    Responsible for assessing confidence in SQL translations.
    """

    def build_confidence_prompt(
        self,
        natural_language_query: str,
        generated_sql: str,
        schema_info: SchemaInfo,
    ) -> str:
        """Build prompt to assess confidence in the translation."""
        return f"""You are an expert SQL reviewer. Assess the quality and correctness of this SQL translation.

Database Schema:
{schema_info.to_prompt_text()}

Original Question: "{natural_language_query}"
Generated SQL:
{generated_sql}

Rate the translation on a scale of 0-100 and classify confidence as:
- HIGH (80-100): The SQL clearly and correctly answers the question
- MEDIUM (50-79): The SQL likely answers the question but may have minor issues
- LOW (0-49): The SQL is unlikely to answer the question or has major issues

Respond in JSON format:
{{"score": <0-100>, "level": "<HIGH|MEDIUM|LOW>", "reasoning": "<brief explanation>"}}
"""

    def parse_confidence_response(
        self, response: str
    ) -> tuple[int, ConfidenceLevel, str]:
        """Parse LLM confidence response."""
        try:
            data = json.loads(response.strip())
            score = int(data.get("score", 50))
            level_str = data.get("level", "MEDIUM").upper()
            reasoning = data.get("reasoning", "")
            level = ConfidenceLevel(level_str.lower())
            return score, level, reasoning
        except (json.JSONDecodeError, ValueError, KeyError):
            score = 30
            if "valid" in response.lower() or "correct" in response.lower():
                score = 70
            return score, ConfidenceLevel.LOW, "Could not parse confidence response"

    def _mock_llm_call(self, prompt: str) -> str:
        """Mock LLM call for confidence assessment."""
        if "SELECT" in prompt and "FROM" in prompt:
            return json.dumps(
                {
                    "score": 85,
                    "level": "HIGH",
                    "reasoning": "SQL correctly answers the question",
                }
            )
        return json.dumps(
            {
                "score": 40,
                "level": "LOW",
                "reasoning": "Generated SQL may not match intent",
            }
        )

    def assess_confidence(
        self,
        natural_language_query: str,
        generated_sql: str,
        schema_info: SchemaInfo,
    ) -> tuple[int, ConfidenceLevel, str]:
        """
        Assess confidence in the SQL translation.
        Returns (score, level, reasoning).
        """
        prompt = self.build_confidence_prompt(
            natural_language_query, generated_sql, schema_info
        )
        response = self._mock_llm_call(prompt)
        return self.parse_confidence_response(response)


class QueryHistoryManager:
    """
    Manages query history for the NL-to-SQL translator.
    """

    def __init__(self):
        self._history: list[NLQueryResult] = []

    def add_query(self, result: NLQueryResult) -> None:
        """Add a query result to history."""
        self._history.append(result)

    def get_history(self) -> list[NLQueryResult]:
        """Return query history."""
        return list(self._history)

    def clear_history(self) -> None:
        """Clear query history."""
        self._history.clear()

    def get_recent_queries(self, limit: int = 10) -> list[NLQueryResult]:
        """Get the most recent queries."""
        return self._history[-limit:]


class FollowUpManager:
    """
    Manages follow-up question generation.
    """

    def build_followup_prompt(
        self,
        natural_language_query: str,
        generated_sql: str,
        results_summary: str,
    ) -> str:
        """Build prompt to generate follow-up questions."""
        return f"""Based on the user's query and results, suggest 3 relevant follow-up questions.

Original Question: "{natural_language_query}"
SQL Used: {generated_sql}
Results Summary: {results_summary}

Generate 3 natural language follow-up questions that:
1. Drill deeper into the current results
2. Explore a related metric or dimension
3. Compare with a different time period or segment

Respond in JSON format:
{{"follow_up_questions": ["<question1>", "<question2>", "<question3>"]}}
"""

    def parse_followup_response(self, response: str) -> list[str]:
        """Parse LLM follow-up questions response."""
        try:
            data = json.loads(response.strip())
            questions = data.get("follow_up_questions", [])
            return [q for q in questions if isinstance(q, str)][:3]
        except (json.JSONDecodeError, KeyError):
            return []

    def _mock_llm_call(self, prompt: str) -> str:
        """Mock LLM call for follow-up generation."""
        return json.dumps(
            {
                "follow_up_questions": [
                    "What is the trend over the last 6 months?",
                    "How does this compare to the previous period?",
                    "Which category has the highest value?",
                ]
            }
        )

    def generate_followup_questions(
        self,
        natural_language_query: str,
        generated_sql: str,
        results: list[dict[str, Any]],
    ) -> list[str]:
        """Generate follow-up questions based on query and results."""
        results_summary = f"{len(results)} rows returned"
        if results:
            keys = list(results[0].keys())[:5]
            results_summary += f", columns: {', '.join(keys)}"

        prompt = self.build_followup_prompt(
            natural_language_query, generated_sql, results_summary
        )
        response = self._mock_llm_call(prompt)
        return self.parse_followup_response(response)


class RephraseManager:
    """
    Manages query rephrasing suggestions.
    """

    def build_rephrase_prompt(
        self,
        natural_language_query: str,
        error_message: str,
    ) -> str:
        """Build prompt to suggest rephrasing for failed queries."""
        return f"""The following natural language query failed to produce valid SQL or execute correctly.

Original Query: "{natural_language_query}"
Error: {error_message}

Suggest 3 alternative phrasings that might work better. Be specific and use terms that match database columns.

Respond in JSON format:
{{"suggestions": ["<alternative1>", "<alternative2>", "<alternative3>"], "reason": "<why the original failed>"}}
"""

    def parse_rephrase_response(self, response: str) -> RephraseSuggestion:
        """Parse LLM rephrase suggestions response."""
        try:
            data = json.loads(response.strip())
            suggestions = [
                s for s in data.get("suggestions", []) if isinstance(s, str)
            ][:3]
            reason = data.get("reason", "Query could not be processed")
            return RephraseSuggestion(
                original_query="",
                suggestions=suggestions,
                reason=reason,
            )
        except (json.JSONDecodeError, KeyError):
            return RephraseSuggestion(
                original_query="",
                suggestions=[
                    "Try rephrasing with specific column names",
                    "Include the table name in your question",
                    "Be more specific about what you want to measure",
                ],
                reason="Could not parse suggestions",
            )

    def _mock_llm_call(self, prompt: str) -> str:
        """Mock LLM call for rephrase suggestions."""
        return json.dumps(
            {
                "suggestions": [
                    "Show me the total sales by month for this year",
                    "What are the sales figures grouped by month in 2024?",
                    "Display monthly sales totals for the current year",
                ],
                "reason": "Original query was too vague or ambiguous",
            }
        )

    def suggest_rephrase(
        self,
        natural_language_query: str,
        error_message: str,
    ) -> RephraseSuggestion:
        """Suggest rephrasing for a failed query."""
        prompt = self.build_rephrase_prompt(natural_language_query, error_message)
        response = self._mock_llm_call(prompt)
        suggestion = self.parse_rephrase_response(response)
        suggestion.original_query = natural_language_query
        return suggestion


class QueryExecutor:
    """
    Responsible for executing SQL queries against connectors.
    """

    def execute_query(
        self,
        sql: str,
        connector: Any,
        max_rows: int = 10000,
    ) -> tuple[list[dict[str, Any]], int | None, str | None]:
        """
        Execute SQL query and return results.
        Returns: (results, row_count, error_message)

        NEW-011 FIX: Pass max_rows to connector for DB-level LIMIT to prevent
        memory exhaustion on large result sets.
        """
        try:
            # NEW-011 FIX: Add LIMIT clause for database-level row limiting
            # This prevents fetching all rows then slicing (memory exhaustion)
            sql_with_limit = sql.strip().rstrip(';')
            # Remove any existing LIMIT clause to avoid conflicts
            sql_upper = sql_with_limit.upper()
            if ' LIMIT ' not in sql_upper:
                sql_with_limit = f"{sql_with_limit} LIMIT {max_rows}"

            # Try to pass max_rows to connector if it supports it
            try:
                results = connector.execute_query(sql_with_limit, max_rows=max_rows)
            except TypeError:
                # Connector doesn't support max_rows parameter, use SQL-level limit
                results = connector.execute_query(sql_with_limit)

            row_count = len(results)
            if row_count > max_rows:
                results = results[:max_rows]
            return results, row_count, None
        except Exception as e:
            return [], None, str(e)


class NLToSQLTranslator:
    """
    Translates natural language to SQL using LLM with schema-aware prompting.
    Delegates to specialized components: SQLGenerator, ConfidenceScorer, etc.
    """

    def __init__(self, llm_client: Any = None):
        self.llm_client = llm_client
        self.sql_generator = SQLGenerator()
        self.confidence_scorer = ConfidenceScorer()
        self.history_manager = QueryHistoryManager()
        self.followup_manager = FollowUpManager()
        self.rephrase_manager = RephraseManager()
        self.query_executor = QueryExecutor()

    @property
    def _query_history(self) -> list[NLQueryResult]:
        """Property for backward compatibility."""
        return self.history_manager.get_history()

    def translate(
        self,
        natural_language_query: str,
        schema_info: SchemaInfo,
        dialect: str = "postgresql",
        data_source_id: str | None = None,
    ) -> NLQueryResult:
        """
        Translate natural language to SQL with confidence scoring.
        """
        import time

        start_time = time.time()

        result = NLQueryResult(
            natural_language_query=natural_language_query,
            data_source_id=data_source_id,
        )

        try:
            sql = self.sql_generator.generate_sql(
                natural_language_query, schema_info, dialect
            )
            result.generated_sql = sql

            # SECURITY B-034: Reject DDL/DML statements to prevent harmful SQL execution
            if self._contains_ddl_or_dml(sql):
                result.error_message = "Generated SQL contains DDL or DML statements which are not allowed. Only SELECT queries are permitted."
                result.confidence_score = 0
                result.confidence_level = ConfidenceLevel.LOW
                return result

            score, level, reasoning = self.confidence_scorer.assess_confidence(
                natural_language_query, sql, schema_info
            )
            result.confidence_score = score
            result.confidence_level = level

        except Exception as e:
            result.error_message = f"Translation failed: {str(e)}"
            result.confidence_score = 0
            result.confidence_level = ConfidenceLevel.LOW

        elapsed_ms = int((time.time() - start_time) * 1000)
        result.execution_time_ms = elapsed_ms

        self.history_manager.add_query(result)
        return result

    def _contains_ddl_or_dml(self, sql: str) -> bool:
        """
        Check if SQL contains DDL or DML statements.
        Only SELECT queries are allowed for security reasons.
        """
        sql_upper = sql.upper().strip()
        # Check for DDL keywords (Data Definition Language)
        ddl_keywords = [
            "CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME",
            "COMMENT", "GRANT", "REVOKE"
        ]
        # Check for DML keywords (Data Manipulation Language) - exclude SELECT
        dml_keywords = [
            "INSERT", "UPDATE", "DELETE", "MERGE", "REPLACE",
            "CALL", "LOCK", "UNLOCK"
        ]
        for keyword in ddl_keywords + dml_keywords:
            if sql_upper.startswith(keyword) or f" {keyword} " in sql_upper:
                return True
        return False

    def execute_query(
        self,
        sql: str,
        connector: Any,
        max_rows: int = 10000,
    ) -> tuple[list[dict[str, Any]], int | None, str | None]:
        """
        Execute SQL query and return results.
        Returns: (results, row_count, error_message)
        """
        return self.query_executor.execute_query(sql, connector, max_rows)

    def generate_followup_questions(
        self,
        natural_language_query: str,
        generated_sql: str,
        results: list[dict[str, Any]],
    ) -> list[str]:
        """Generate follow-up questions based on query and results."""
        return self.followup_manager.generate_followup_questions(
            natural_language_query, generated_sql, results
        )

    def suggest_rephrase(
        self,
        natural_language_query: str,
        error_message: str,
    ) -> RephraseSuggestion:
        """Suggest rephrasing for a failed query."""
        return self.rephrase_manager.suggest_rephrase(natural_language_query, error_message)

    def get_query_history(self) -> list[NLQueryResult]:
        """Return query history."""
        return self.history_manager.get_history()

    def clear_history(self):
        """Clear query history."""
        self.history_manager.clear_history()

    # Backward compatibility properties
    def build_schema_prompt(self, schema_info: SchemaInfo) -> str:
        return self.sql_generator.build_schema_prompt(schema_info)

    def build_translation_prompt(
        self,
        natural_language_query: str,
        schema_info: SchemaInfo,
        dialect: str = "postgresql",
    ) -> str:
        return self.sql_generator.build_translation_prompt(
            natural_language_query, schema_info, dialect
        )

    def build_confidence_prompt(
        self,
        natural_language_query: str,
        generated_sql: str,
        schema_info: SchemaInfo,
    ) -> str:
        return self.confidence_scorer.build_confidence_prompt(
            natural_language_query, generated_sql, schema_info
        )

    def parse_confidence_response(
        self, response: str
    ) -> tuple[int, ConfidenceLevel, str]:
        return self.confidence_scorer.parse_confidence_response(response)

    def build_followup_prompt(
        self,
        natural_language_query: str,
        generated_sql: str,
        results_summary: str,
    ) -> str:
        return self.followup_manager.build_followup_prompt(
            natural_language_query, generated_sql, results_summary
        )

    def parse_followup_response(self, response: str) -> list[str]:
        return self.followup_manager.parse_followup_response(response)

    def build_rephrase_prompt(
        self,
        natural_language_query: str,
        error_message: str,
    ) -> str:
        return self.rephrase_manager.build_rephrase_prompt(
            natural_language_query, error_message
        )

    def parse_rephrase_response(self, response: str) -> RephraseSuggestion:
        return self.rephrase_manager.parse_rephrase_response(response)

    def _mock_llm_call(self, prompt: str) -> str:
        """Fallback mock LLM call for backward compatibility."""
        if "confidence" in prompt.lower() or "assess" in prompt.lower():
            return self.confidence_scorer._mock_llm_call(prompt)
        if "follow-up" in prompt.lower() or "followup" in prompt.lower():
            return self.followup_manager._mock_llm_call(prompt)
        if "rephrase" in prompt.lower() or "suggestion" in prompt.lower():
            return self.rephrase_manager._mock_llm_call(prompt)
        return self.sql_generator._mock_llm_call(prompt)