#!/usr/bin/env python3
"""Test GameLogic streaming Oracle integration with mock LLM client."""

import pytest
from unittest.mock import patch, MagicMock

from fungi_fortress.game_state import GameState
from fungi_fortress.game_logic import GameLogic
from fungi_fortress.config_manager import LLMConfig


def test_game_logic_streaming_oracle_with_mock_client(monkeypatch):
    """Test GameLogic Oracle interaction with mock LLM client (non-streaming path).
    
    Oracle now always uses non-streaming typed path to get structured actions.
    
    Verifies:
    1. Oracle history grows by exactly 1 turn
    2. Each action executes exactly once (not doubled)
    3. No 'disruption' error message appears
    4. Mock provider is actually used (no network calls)
    """
    # Inject test action into mock response for this test only
    from fungi_fortress.llm_client import MockLLMProvider
    
    original_mock_response = MockLLMProvider._mock_response
    
    def mock_response_with_action(self, user_content):
        # Call original to get the response type
        import re
        import json
        normalized = user_content.lower()
        def has_word(pattern: str) -> bool:
            return bool(re.search(r'\b' + re.escape(pattern) + r'\b', normalized))
        
        # For fungi queries, return JSON format (Oracle now uses non-streaming)
        if any(has_word(word) for word in ["fungi", "mushroom", "spore"]):
            return json.dumps({
                "narrative": "The sacred fungi hold memories of ages past. They grow in places of deep magic, where stone and root intertwine.",
                "actions": [
                    {
                        "action_type": "add_message",
                        "text": "Test action from mock"
                    }
                ]
            })
        else:
            # Use original for other queries
            return original_mock_response(self, user_content)
    
    monkeypatch.setattr(MockLLMProvider, "_mock_response", mock_response_with_action)
    
    # Initialize game state with NO API key to force mock usage
    llm_config = LLMConfig(
        api_key=None,  # Force mock provider
        model_name="mock-model",
        enable_streaming=True,
        context_level="low"
    )
    game_state = GameState(llm_config=llm_config)
    game_logic = GameLogic(game_state)
    
    # Set up Oracle on the map and open dialogue
    from fungi_fortress.characters import Oracle
    oracle = Oracle(name="Test Oracle", x=5, y=5)
    game_state.characters.append(oracle)
    game_state.show_oracle_dialog = True
    game_state.oracle_interaction_state = "AWAITING_PROMPT"
    game_state.oracle_current_dialogue = []
    
    # Track initial state
    initial_history_len = len(game_state.oracle_llm_interaction_history)
    
    # Track add_message action executions
    add_message_count = 0
    original_add_debug = game_state.add_debug_message
    def counting_add_debug(msg):
        nonlocal add_message_count
        if "LLM: Test action from mock" in msg:
            add_message_count += 1
        return original_add_debug(msg)
    game_state.add_debug_message = counting_add_debug
    
    # Simulate Oracle query about fungi (triggers mock response)
    player_query = "Tell me about the ancient fungi"
    game_state.add_event("ORACLE_QUERY", {
        "query_text": player_query,
        "oracle_name": "Test Oracle"
    })
    
    # Process until Oracle completes (non-streaming should be immediate)
    game_logic.update()
    
    max_ticks = 100
    for tick in range(max_ticks):
        if game_state.oracle_interaction_state == "AWAITING_PROMPT":
            break
        game_logic.update()
    else:
        pytest.fail(f"Oracle query did not complete within {max_ticks} ticks")
    
    # Verify 1: History grew by exactly 1 turn
    final_history_len = len(game_state.oracle_llm_interaction_history)
    assert final_history_len == initial_history_len + 1, (
        f"Expected history to grow by 1, grew by {final_history_len - initial_history_len}"
    )
    
    # Verify the history entry
    latest_entry = game_state.oracle_llm_interaction_history[-1]
    assert latest_entry["player"] == player_query
    assert "fungi" in latest_entry["oracle"].lower()
    
    # Verify 2: No 'disruption' error
    all_dialogue = []
    for line in game_state.oracle_current_dialogue:
        if isinstance(line, tuple):
            all_dialogue.append(line[0])
        else:
            all_dialogue.append(str(line))
    dialogue_text = "\n".join(all_dialogue)
    assert "disruption" not in dialogue_text.lower(), "Found 'disruption' error in dialogue"
    
    # Verify 3: Mock action ran exactly once (not doubled)
    assert add_message_count == 1, f"add_message action ran {add_message_count} times (expected exactly 1)"
    
    print(f"✓ Oracle test passed (non-streaming typed path):")
    print(f"  - History grew from {initial_history_len} to {final_history_len}")
    print(f"  - No disruption errors")
    print(f"  - Completed in {tick} ticks")


def test_game_logic_non_streaming_oracle_with_mock_client():
    """Test GameLogic non-streaming path with mock LLM client.
    
    Verifies:
    1. History grows by exactly 1 turn
    2. Response is from mock (not network error)
    3. No disruption errors
    4. No network calls (api_key=None forces mock)
    """
    # Initialize game state with NO API key (forces mock, no network)
    llm_config = LLMConfig(
        api_key=None,  # Force mock provider, prevent network calls
        model_name="mock-model",
        enable_streaming=False,  # Non-streaming mode
        context_level="low"
    )
    game_state = GameState(llm_config=llm_config)
    game_logic = GameLogic(game_state)
    
    # Set up Oracle
    from fungi_fortress.characters import Oracle
    oracle = Oracle(name="Test Oracle", x=5, y=5)
    game_state.characters.append(oracle)
    game_state.show_oracle_dialog = True
    game_state.oracle_interaction_state = "AWAITING_PROMPT"
    game_state.oracle_current_dialogue = []
    
    initial_history_len = len(game_state.oracle_llm_interaction_history)
    
    # Simulate Oracle query that triggers "default" mock response
    player_query = "What secrets do you hold?"
    game_state.add_event("ORACLE_QUERY", {
        "query_text": player_query,
        "oracle_name": "Test Oracle"
    })
    
    # Process the query
    game_logic.update()
    
    # Wait for non-streaming response (should complete quickly)
    for i in range(10):
        if game_state.oracle_interaction_state == "AWAITING_PROMPT":
            break
        game_logic.update()
    
    # Verify history grew by one turn
    final_history_len = len(game_state.oracle_llm_interaction_history)
    assert final_history_len == initial_history_len + 1, (
        f"Expected history to grow by 1, but grew by {final_history_len - initial_history_len}"
    )
    
    # Verify response is from mock, not network error
    latest_entry = game_state.oracle_llm_interaction_history[-1]
    oracle_response = latest_entry["oracle"].lower()
    assert "spores whisper" in oracle_response, f"Expected mock response text, got: {oracle_response[:100]}"
    assert "connection cannot be established" not in oracle_response, "Got network error instead of mock response"
    assert "error" not in oracle_response, f"Got error response: {oracle_response[:100]}"
    
    # Verify no disruption errors
    all_dialogue = "\n".join(str(line) for line in game_state.oracle_current_dialogue)
    assert "disruption" not in all_dialogue.lower()
    
    print(f"✓ Non-streaming test passed:")
    print(f"  - History entries: {initial_history_len} → {final_history_len}")
    print(f"  - Response is from mock (no network)")
    print(f"  - No disruption errors")


if __name__ == "__main__":
    test_game_logic_streaming_oracle_with_mock_client()
    test_game_logic_non_streaming_oracle_with_mock_client()
    print("\nAll GameLogic streaming tests passed!")
