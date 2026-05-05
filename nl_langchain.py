"""
LangChain NLP Pipeline for query understanding.
Integrates LangChain with LLMs for NL-to-SQL translation, confidence scoring,
follow-up generation, and query rephrasing.
"""

import json
import logging
import os
from typing import Any, Optional

from nl_to_sql import (
    NLToSQLTranslator,
    SchemaInfo,
    ConfidenceLevel,
    NLQueryResult,
    RephraseSuggestion,
)

logger = logging.getLogger(__name__)


class JSONOutputParser:
    """Parser for JSON outputs from LLM."""

    def parse(self, text: str) -> dict:
        try:
            text = text.strip()
            if text.startswith("```"):
                parts = text.split("```")
                if len(parts) >= 2:
                    text = parts[1]
                    if text.startswith("json"):
                        text = text[4:]
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON: {text}") from e


class LangChainTranslator(NLToSQLTranslator):
    """
    LangChain-powered NL-to-SQL translator.
    Uses LangChain to interface with LLMs for robust NLP pipeline.
    """

    def __init__(self, llm: Any = None, temperature: float = 0.0):
        super().__init__(llm_client=llm)
        self.llm = llm
        self.temperature = temperature

    def _get_llm(self):
        """Get or initialize the LLM."""
        if self.llm is not None:
            return self.llm

        provider = os.getenv("LLM_PROVIDER", "mock").lower()
        model_name = os.getenv("LLM_MODEL", "gpt-3.5-turbo")

        try:
            if provider == "openai":
                try:
                    from langchain_openai import OpenAI
                except ImportError:
                    from langchain.llms import OpenAI
                api_key = os.getenv("OPENAI_API_KEY")
                self.llm = OpenAI(
                    model_name=model_name,
                    temperature=self.temperature,
                    openai_api_key=api_key,
                )
            elif provider == "anthropic":
                try:
                    from langchain_anthropic import Anthropic
                except ImportError:
                    from langchain.llms import Anthropic
                api_key = os.getenv("ANTHROPIC_API_KEY")
                self.llm = Anthropic(
                    model=model_name,
                    temperature=self.temperature,
                    anthropic_api_key=api_key,
                )
            elif provider == "huggingface":
                from langchain.llms import HuggingFaceHub
                self.llm = HuggingFaceHub(
                    repo_id=model_name,
                    model_kwargs={"temperature": self.temperature},
                )
            else:
                logger.warning("Unknown provider %s, falling back to mock", provider)
                return None
        except ImportError as e:
            logger.warning("Failed to import LLM provider: %s. Using mock.", e)
            return None

        return self.llm

    def translate(
        self,
        natural_language_query: str,
        schema_info: SchemaInfo,
        dialect: str = "postgresql",
        data_source_id: Optional[str] = None,
    ) -> NLQueryResult:
        """Translate natural language to SQL using LangChain LLM."""
        import time
        start_time = time.time()

        result = NLQueryResult(
            natural_language_query=natural_language_query,
            data_source_id=data_source_id,
        )

        try:
            llm = self._get_llm()
            prompt_text = self.build_translation_prompt(
                natural_language_query, schema_info, dialect
            )

            if llm is not None:
                sql = llm(prompt_text)
                result.generated_sql = sql.strip()

                confidence_prompt = self.build_confidence_prompt(
                    natural_language_query, result.generated_sql, schema_info
                )
                confidence_response = llm(confidence_prompt)
                try:
                    parser = JSONOutputParser()
                    parsed = parser.parse(confidence_response)
                    result.confidence_score = int(parsed.get("score", 50))
                    level_str = parsed.get("level", "medium").lower()
                    result.confidence_level = ConfidenceLevel(level_str)
                except Exception:
                    result.confidence_score = 50
                    result.confidence_level = ConfidenceLevel.MEDIUM
            else:
                return super().translate(
                    natural_language_query, schema_info, dialect, data_source_id
                )

        except Exception as e:
            logger.error("LangChain translation failed: %s", e)
            result.error_message = f"Translation failed: {str(e)}"
            result.confidence_score = 0
            result.confidence_level = ConfidenceLevel.LOW

        elapsed_ms = int((time.time() - start_time) * 1000)
        result.execution_time_ms = elapsed_ms

        self._query_history.append(result)
        return result

    def generate_followup_questions(
        self,
        natural_language_query: str,
        generated_sql: str,
        results: list,
    ) -> list:
        """Generate follow-up questions using LangChain LLM."""
        results_summary = f"{len(results)} rows returned"
        if results:
            keys = list(results[0].keys())[:5]
            results_summary += f", columns: {', '.join(keys)}"

        prompt_text = self.build_followup_prompt(
            natural_language_query, generated_sql, results_summary
        )

        llm = self._get_llm()
        if llm is not None:
            try:
                response = llm(prompt_text)
                parser = JSONOutputParser()
                parsed = parser.parse(response)
                questions = parsed.get("follow_up_questions", [])
                return [q for q in questions if isinstance(q, str)][:3]
            except Exception as e:
                logger.error("Follow-up generation failed: %s", e)

        return super().generate_followup_questions(
            natural_language_query, generated_sql, results
        )

    def suggest_rephrase(
        self,
        natural_language_query: str,
        error_message: str,
    ) -> RephraseSuggestion:
        """Suggest rephrasing using LangChain LLM."""
        prompt_text = self.build_rephrase_prompt(
            natural_language_query, error_message
        )

        llm = self._get_llm()
        if llm is not None:
            try:
                response = llm(prompt_text)
                parser = JSONOutputParser()
                parsed = parser.parse(response)
                suggestions = [
                    s for s in parsed.get("suggestions", []) if isinstance(s, str)
                ][:3]
                reason = parsed.get("reason", "Query could not be processed")
                return RephraseSuggestion(
                    original_query=natural_language_query,
                    suggestions=suggestions,
                    reason=reason,
                )
            except Exception as e:
                logger.error("Rephrase suggestion failed: %s", e)

        return super().suggest_rephrase(natural_language_query, error_message)


def create_translator_from_env() -> NLToSQLTranslator:
    """Factory function to create a translator based on environment config."""
    provider = os.getenv("LLM_PROVIDER", "mock").lower()
    if provider and provider != "mock":
        return LangChainTranslator(temperature=0.0)
    return NLToSQLTranslator()
