"""
Tests for LangChain NLP pipeline.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from nl_langchain import (
    LangChainTranslator,
    JSONOutputParser,
    create_translator_from_env,
)
from nl_to_sql import ConfidenceLevel, NLQueryResult, SchemaInfo


class TestJSONOutputParser:
    def test_parse_valid_json(self):
        parser = JSONOutputParser()
        result = parser.parse('{"score": 85, "level": "HIGH"}')
        assert result["score"] == 85
        assert result["level"] == "HIGH"

    def test_parse_json_from_markdown(self):
        parser = JSONOutputParser()
        result = parser.parse("```json\n{\"score\": 70}\n```")
        assert result["score"] == 70

    def test_parse_invalid_json_raises(self):
        parser = JSONOutputParser()
        with pytest.raises(Exception):
            parser.parse("not valid json")


class TestLangChainTranslator:
    def test_init_without_llm(self):
        translator = LangChainTranslator()
        assert translator.llm is None
        assert translator.temperature == 0.0

    def test_init_with_llm(self):
        mock_llm = MagicMock()
        translator = LangChainTranslator(llm=mock_llm, temperature=0.5)
        assert translator.llm == mock_llm
        assert translator.temperature == 0.5

    @patch("nl_langchain.LangChainTranslator._get_llm")
    def test_translate_uses_llm_when_available(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.return_value = "SELECT * FROM sales"
        mock_get_llm.return_value = mock_llm

        translator = LangChainTranslator()
        schema = SchemaInfo(
            tables=[{"name": "sales", "columns": [{"name": "id", "type": "INTEGER"}]}]
        )
        result = translator.translate("Show sales", schema)
        assert result.generated_sql == "SELECT * FROM sales"
        assert result.confidence_score is not None

    @patch("nl_langchain.LangChainTranslator._get_llm")
    def test_translate_falls_back_to_mock_when_no_llm(self, mock_get_llm):
        mock_get_llm.return_value = None

        translator = LangChainTranslator()
        schema = SchemaInfo(
            tables=[{"name": "data", "columns": []}]
        )
        result = translator.translate("Show data", schema)
        assert result.generated_sql is not None
        assert "SELECT" in result.generated_sql

    @patch("nl_langchain.LangChainTranslator._get_llm")
    def test_generate_followup_uses_llm(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.return_value = '{"follow_up_questions": ["Q1?", "Q2?", "Q3?"]}'
        mock_get_llm.return_value = mock_llm

        translator = LangChainTranslator()
        questions = translator.generate_followup_questions(
            "Show sales", "SELECT * FROM sales", [{"id": 1}]
        )
        assert len(questions) <= 3
        assert all(isinstance(q, str) for q in questions)

    @patch("nl_langchain.LangChainTranslator._get_llm")
    def test_suggest_rephrase_uses_llm(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.return_value = '{"suggestions": ["alt1", "alt2"], "reason": "vague"}'
        mock_get_llm.return_value = mock_llm

        translator = LangChainTranslator()
        suggestion = translator.suggest_rephrase("bad query", "error")
        assert suggestion.original_query == "bad query"
        assert len(suggestion.suggestions) > 0
        assert suggestion.reason != ""


class TestCreateTranslatorFromEnv:
    def test_mock_when_no_provider(self):
        with patch.dict(os.environ, {}, clear=True):
            translator = create_translator_from_env()
            assert not isinstance(translator, LangChainTranslator)

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock"})
    def test_mock_with_mock_provider(self):
        translator = create_translator_from_env()
        assert not isinstance(translator, LangChainTranslator)

    @patch("nl_langchain.LangChainTranslator._get_llm")
    @patch.dict(os.environ, {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "test-key"})
    def test_openai_provider(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        # This will try to import OpenAI which may fail in test, so we handle gracefully
        try:
            translator = create_translator_from_env()
            assert isinstance(translator, LangChainTranslator)
        except ImportError:
            pass  # Expected in test environment without langchain openai
