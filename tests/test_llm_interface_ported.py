"""Ported tests for llm_interface from old test file.

These tests cover handle_game_event and config functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from fungi_fortress import llm_interface, llm_client
from fungi_fortress.llm_interface import handle_game_event
from fungi_fortress.config_manager import LLMConfig


# Mock classes for testing
class MockGameState:
    def __init__(self, tick=100, depth=1, mission_desc=None, player_resources=None, history=None, config=None):
        self.tick = tick
        self.depth = depth
        self.mission = {"description": mission_desc} if mission_desc else None
        self.player_resources = player_resources if player_resources else {}
        self.oracle_llm_interaction_history = history if history else []
        self.llm_config = config if config else LLMConfig(api_key=None, context_level="medium")
    
    def get_tile(self, x, y):
        return None


# Tests for handle_game_event
def test_handle_game_event_no_query_text():
    """Test handle_game_event with missing query text."""
    game_state = MockGameState()
    event_data = {"type": "ORACLE_QUERY", "details": {}}
    
    actions_to_execute = handle_game_event(event_data, game_state)
    
    assert len(actions_to_execute) == 1
    assert actions_to_execute[0]["action_type"] == "add_oracle_dialogue"
    assert actions_to_execute[0]["details"]["text"] == "(You offer your thoughts, but no words escape.)"


def test_handle_game_event_oracle_typed_path():
    """Test handle_game_event with Oracle uses typed non-streaming path."""
    config = LLMConfig(api_key=None)  # Uses defaults
    game_state = MockGameState(config=config)
    event_data = {"type": "ORACLE_QUERY", "details": {"query_text": "Hello", "oracle_name": "Test Oracle"}}
    
    actions = handle_game_event(event_data, game_state)
    
    # Oracle uses typed non-streaming path, should return dialogue actions
    assert actions is not None
    assert len(actions) >= 1
    assert actions[0]["action_type"] == "add_oracle_dialogue"


# Config tests
def test_llm_config_api_key_validation():
    """Test API key validation in LLMConfig."""
    assert not LLMConfig(api_key="YOUR_API_KEY_HERE").is_real_api_key_present
    assert not LLMConfig(api_key="None").is_real_api_key_present
    assert not LLMConfig(api_key="").is_real_api_key_present
    assert not LLMConfig(api_key=None).is_real_api_key_present
    assert LLMConfig(api_key="real_api_key_value").is_real_api_key_present
    assert LLMConfig(api_key="testkey123").is_real_api_key_present  # Not a placeholder


def test_client_invalid_key_uses_mock():
    """Test that invalid API keys result in mock client."""
    config = LLMConfig(api_key="YOUR_API_KEY_HERE")
    client = config.create_llm_client()
    assert client.is_mock()


def test_client_no_key_uses_mock():
    """Test that no API key results in mock client."""
    config = LLMConfig(api_key=None)
    client = config.create_llm_client()
    assert client.is_mock()


def test_llm_config_defaults():
    """Test that LLMConfig defaults are set correctly."""
    config = LLMConfig()
    assert config.api_key is None
    assert config.model_name == "grok-4.3"
    assert config.context_level == "medium"
    assert not config.is_real_api_key_present


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
