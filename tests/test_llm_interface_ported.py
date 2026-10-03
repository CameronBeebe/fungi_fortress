"""Ported tests for llm_interface from old test file.

These tests cover _parse_llm_response and other core functionality
that was working in the old implementation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from fungi_fortress import llm_interface, llm_client
from fungi_fortress.llm_interface import _parse_llm_response, handle_game_event
from fungi_fortress.config_manager import LLMConfig


# Mock classes for testing
class MockGameState:
    def __init__(self, tick=100, depth=1, mission_desc=None, player_resources=None, history=None, config=None):
        self.tick = tick
        self.depth = depth
        self.mission = {"description": mission_desc} if mission_desc else None
        self.player_resources = player_resources if player_resources else {}
        self.oracle_llm_interaction_history = history if history else []
        self.llm_config = config if config else LLMConfig(api_key=None, model_name="grok-3-mini", context_level="medium")
    
    def get_tile(self, x, y):
        return None


# Tests for _parse_llm_response
def test_parse_llm_response_narrative_only():
    """Test parsing response with only narrative text."""
    response_text = "This is a simple narrative response."
    narrative, actions = _parse_llm_response(response_text)
    assert narrative == "This is a simple narrative response."
    assert actions == []


def test_parse_llm_response_with_one_action():
    """Test parsing response with one ACTION marker."""
    response_text = "Narrative part. ACTION::add_message::{\"text\": \"Hello\"}"
    narrative, actions = _parse_llm_response(response_text)
    assert narrative == "Narrative part."
    assert actions == [{"action_type": "add_message", "details": {"text": "Hello"}}]


def test_parse_llm_response_with_multiple_actions():
    """Test parsing response with multiple ACTION markers."""
    response_text = "Desc. ACTION::spawn::{\"id\":1} ACTION::move::{\"id\":1, \"x\":5}"
    narrative, actions = _parse_llm_response(response_text)
    assert narrative == "Desc."
    assert actions == [
        {"action_type": "spawn", "details": {"id": 1}},
        {"action_type": "move", "details": {"id": 1, "x": 5}}
    ]


def test_parse_llm_response_malformed_json():
    """Test parsing with malformed JSON in action."""
    response_text = "Problem. ACTION::data::{'key': 'value\"'}"
    narrative, actions = _parse_llm_response(response_text)
    assert "Problem." in narrative
    assert "(The Oracle's words concerning an action were muddled: data::{'key': 'value\"'})" in narrative
    assert actions == []


def test_parse_llm_response_malformed_action_string():
    """Test parsing with malformed ACTION string (missing ::)."""
    response_text = "Gesture. ACTION::nodetails"
    narrative, actions = _parse_llm_response(response_text)
    assert "Gesture." in narrative
    assert "(The Oracle made an unclear gesture: nodetails)" in narrative
    assert actions == []


def test_parse_llm_response_empty_string():
    """Test parsing empty response."""
    response_text = ""
    narrative, actions = _parse_llm_response(response_text)
    assert narrative == ""
    assert actions == []


def test_parse_llm_response_action_at_start_clean():
    """Test parsing with ACTION at start of response."""
    response_text = "ACTION::add_message::{\"text\": \"Alert!\"}"
    narrative, actions = _parse_llm_response(response_text)
    assert narrative == ""
    assert actions == [{"action_type": "add_message", "details": {"text": "Alert!"}}]


def test_parse_llm_response_json_format():
    """Test parsing structured JSON format."""
    response_text = '{"narrative": "Test narrative", "actions": [{"action_type": "add_message", "details": {"text": "Test"}}]}'
    narrative, actions = _parse_llm_response(response_text)
    assert narrative == "Test narrative"
    assert len(actions) == 1
    assert actions[0]["action_type"] == "add_message"


# Tests for handle_game_event
def test_handle_game_event_no_query_text():
    """Test handle_game_event with missing query text."""
    game_state = MockGameState()
    event_data = {"type": "ORACLE_QUERY", "details": {}}
    
    actions_to_execute = handle_game_event(event_data, game_state)
    
    assert len(actions_to_execute) == 1
    assert actions_to_execute[0]["action_type"] == "add_oracle_dialogue"
    assert actions_to_execute[0]["details"]["text"] == "(You offer your thoughts, but no words escape.)"


def test_handle_game_event_non_streaming():
    """Test handle_game_event with non-streaming enabled."""
    config = LLMConfig(api_key=None, model_name="grok-3-mini", enable_streaming=False)
    game_state = MockGameState(config=config)
    event_data = {"type": "ORACLE_QUERY", "details": {"query_text": "Hello"}}
    
    actions = handle_game_event(event_data, game_state)
    
    # Should return actions (with mock provider)
    assert actions is not None
    assert len(actions) >= 2  # At least dialogue + set_oracle_state


def test_handle_game_event_streaming():
    """Test handle_game_event with streaming enabled."""
    config = LLMConfig(api_key=None, model_name="grok-3-mini", enable_streaming=True)
    game_state = MockGameState(config=config)
    event_data = {"type": "ORACLE_QUERY", "details": {"query_text": "Hello", "oracle_name": "Test Oracle"}}
    
    actions = handle_game_event(event_data, game_state)
    
    # Should return start_enhanced_oracle_streaming action
    assert actions is not None
    assert len(actions) == 1
    assert actions[0]["action_type"] == "start_enhanced_oracle_streaming"
    assert "player_query" in actions[0]["details"]
    assert "game_context" in actions[0]["details"]


# Config tests
def test_llm_config_api_key_validation():
    """Test API key validation in LLMConfig."""
    assert not LLMConfig(api_key="YOUR_API_KEY_HERE").is_real_api_key_present
    assert not LLMConfig(api_key="testkey123").is_real_api_key_present
    assert not LLMConfig(api_key="None").is_real_api_key_present
    assert not LLMConfig(api_key="").is_real_api_key_present
    assert not LLMConfig(api_key=None).is_real_api_key_present
    assert LLMConfig(api_key="real_api_key_value").is_real_api_key_present


def test_client_invalid_key_uses_mock():
    """Test that invalid API keys result in mock client."""
    config = LLMConfig(api_key="YOUR_API_KEY_HERE", model_name="grok-3-mini")
    client = config.create_llm_client()
    assert client.is_mock()


def test_client_no_key_uses_mock():
    """Test that no API key results in mock client."""
    config = LLMConfig(api_key=None, model_name="grok-3-mini")
    client = config.create_llm_client()
    assert client.is_mock()


def test_llm_config_defaults():
    """Test that LLMConfig defaults are set correctly."""
    config = LLMConfig()
    assert config.api_key is None
    assert config.model_name == "grok-3-mini"
    assert config.context_level == "medium"
    assert not config.is_real_api_key_present


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
