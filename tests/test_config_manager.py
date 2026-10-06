"""Tests for config_manager.py - environment-only configuration."""

import pytest
from unittest.mock import patch
import os

from fungi_fortress.config_manager import LLMConfig, PLACEHOLDER_API_KEYS


def test_from_env_with_no_key():
    """LLMConfig.from_env() with no XAI_API_KEY returns None api_key."""
    with patch.dict(os.environ, {}, clear=True):
        config = LLMConfig.from_env()
        assert config.api_key is None
        assert not config.is_real_api_key_present


def test_from_env_with_real_key():
    """LLMConfig.from_env() picks up XAI_API_KEY from environment."""
    with patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key-123"}, clear=True):
        config = LLMConfig.from_env()
        assert config.api_key == "xai-test-key-123"
        assert config.is_real_api_key_present


@pytest.mark.parametrize("placeholder_key", list(PLACEHOLDER_API_KEYS))
def test_from_env_with_placeholder_key(placeholder_key):
    """Placeholder keys are detected as non-real."""
    with patch.dict(os.environ, {"XAI_API_KEY": placeholder_key}, clear=True):
        config = LLMConfig.from_env()
        assert config.api_key == placeholder_key
        assert not config.is_real_api_key_present


def test_defaults_are_set():
    """All defaults are defined in LLMConfig dataclass."""
    config = LLMConfig.from_env()
    assert config.model_name == "grok-4.3"
    assert config.reasoning_effort == "low"
    assert config.temperature == 0.7
    assert config.context_level == "medium"
    assert config.max_tokens == 500
    assert config.timeout_seconds == 30
    assert config.max_retries == 2
    assert config.enable_structured_outputs is True
    assert config.enable_streaming is True


def test_api_key_not_in_repr():
    """API key is redacted from repr to prevent leaks."""
    config = LLMConfig(api_key="secret-key-abc")
    repr_str = repr(config)
    assert "secret-key-abc" not in repr_str
    assert "api_key" not in repr_str or "***" in repr_str


def test_create_llm_client():
    """LLMConfig.create_llm_client() returns an LLMClient instance."""
    config = LLMConfig.from_env()
    client = config.create_llm_client()
    assert client is not None
    # Client is mock when no real key
    assert client.is_mock()
