#!/usr/bin/env python3
"""Test that LLM prompt context adapts to context_level setting."""

import pytest
from unittest.mock import Mock, patch

from fungi_fortress.game_state import GameState
from fungi_fortress.config_manager import LLMConfig
from fungi_fortress import llm_interface


@pytest.mark.parametrize("context_level,expected_history_len,expect_mission,expect_resources", [
    ("low", 1, False, False),
    ("medium", 3, True, False),
    ("high", 5, True, True),
])
def test_non_streaming_context_levels(context_level, expected_history_len, expect_mission, expect_resources):
    """Test that handle_oracle_query_non_streaming includes correct context based on level.
    
    Oracle always uses non-streaming (no streaming test needed).
    
    - low: 1 history turn, no mission, no resources
    - medium: 3 history turns, mission included, no resources
    - high: 5 history turns, mission included, resources included
    """
    # Set up game state with history
    llm_config = LLMConfig(
        api_key=None,  # Use mock
        model_name="mock-model",
        enable_streaming=False,
        context_level=context_level
    )
    game_state = GameState(llm_config=llm_config)
    
    # Populate interaction history (10 entries)
    for i in range(10):
        game_state.oracle_llm_interaction_history.append({
            "player": f"Question {i}",
            "oracle": f"Answer {i}"
        })
    
    # Set up mission and resources
    game_state.mission = {
        "description": "Test mission description",
        "objectives": ["Objective 1", "Objective 2"]
    }
    game_state.player_resources = {"wood": 10, "stone": 5}
    
    player_query = "What should I do?"
    oracle_name = "Test Oracle"
    
    # Create event
    event_data = {
        "type": "ORACLE_QUERY",
        "details": {
            "query_text": player_query,
            "oracle_name": oracle_name
        }
    }
    
    # Mock the LLM client's chat method to capture the prompt
    captured_messages = []
    
    def mock_chat(messages, max_tokens=1000, **kwargs):
        nonlocal captured_messages
        captured_messages = messages
        return '{"narrative": "Test response", "actions": []}'
    
    original_create = llm_config.create_llm_client
    
    def mock_create_client():
        mock_client = Mock()
        mock_client.chat = mock_chat
        mock_client.is_mock.return_value = True
        return mock_client
    
    llm_config.create_llm_client = mock_create_client
    
    try:
        # Call handle_oracle_query_non_streaming - it actually calls the LLM
        actions = llm_interface.handle_oracle_query_non_streaming(event_data, game_state)
        
        assert len(captured_messages) > 0, "LLM should have been called"
        
        # Extract prompt from messages
        prompt = ""
        for msg in captured_messages:
            prompt += msg["content"] + "\n"
        
        # Check history in prompt (just count history, not current query)
        player_lines = prompt.count("Player: ")
        oracle_lines = prompt.count("Oracle: ")
        
        # History should have expected number of Player/Oracle pairs
        assert player_lines == expected_history_len, \
            f"Expected {expected_history_len} Player lines in history, got {player_lines}"
        assert oracle_lines == expected_history_len, \
            f"Expected {expected_history_len} Oracle lines in history, got {oracle_lines}"
        
        # Check mission presence
        if expect_mission:
            assert "Mission:" in prompt, f"Mission should be in prompt for {context_level}"
            assert "Test mission description" in prompt
        else:
            assert "Mission:" not in prompt, f"Mission should not be in prompt for {context_level}"
        
        # Check resources presence
        if expect_resources:
            assert "wood" in prompt.lower() or "resources" in prompt.lower(), \
                f"Resources should be in prompt for {context_level}"
        else:
            # For low/medium, resources shouldn't be mentioned
            if context_level in ["low", "medium"]:
                assert "wood: 10" not in prompt, f"Resources should not be in prompt for {context_level}"
    
    finally:
        llm_config.create_llm_client = original_create


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
