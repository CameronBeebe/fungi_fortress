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


def test_api_key_not_in_repr():
    """API key is redacted from repr to prevent leaks."""
    config = LLMConfig(api_key="secret-key-abc")
    repr_str = repr(config)
    assert "secret-key-abc" not in repr_str


def test_api_key_not_in_logs(caplog):
    """API keys are never logged when GameState is created."""
    from fungi_fortress.game_state import GameState
    
    secret_key = "xai-secret-key-should-not-appear-in-logs"
    llm_config = LLMConfig(api_key=secret_key)
    
    # Create GameState with the secret key
    with caplog.at_level("DEBUG"):
        game_state = GameState(llm_config=llm_config)
    
    # Assert the secret is not in any log output
    assert secret_key not in caplog.text


def test_no_api_keys_in_source_files():
    """Scan source files for accidentally committed API keys."""
    import re
    
    source_files = [
        "fungi_fortress/config_manager.py",
        "fungi_fortress/app.py",
        "fungi_fortress/game_state.py",
        "fungi_fortress/llm_interface.py"
    ]
    
    api_key_patterns = [
        r'xai-[a-zA-Z0-9]{40,}',
        r'sk-[a-zA-Z0-9]{40,}', 
        r'claude-[a-zA-Z0-9]{40,}',
        r'gsk_[a-zA-Z0-9]{40,}',
    ]
    
    for file_path in source_files:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                content = f.read()
            
            for pattern in api_key_patterns:
                matches = re.findall(pattern, content)
                assert len(matches) == 0, f"Found potential API key in {file_path}: {matches}"


def test_create_llm_client():
    """LLMConfig.create_llm_client() returns an LLMClient instance."""
    config = LLMConfig.from_env()
    client = config.create_llm_client()
    assert client is not None
    # Client is mock when no real key
    assert client.is_mock()
