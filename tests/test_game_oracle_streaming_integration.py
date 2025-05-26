#!/usr/bin/env python3
"""Test script to verify Oracle streaming integration with game logic."""

import pytest
from unittest.mock import patch, MagicMock, call

from fungi_fortress.game_state import GameState
from fungi_fortress.game_logic import GameLogic
from fungi_fortress.config_manager import LLMConfig
from fungi_fortress import llm_interface # يتم استخدامه بواسطة game_logic
from fungi_fortress.text_streaming import text_streaming_engine # للوصول إلى Mock

# Re-use or adapt a mock streaming generator
# This should yield actions as text_streaming_engine.start_oracle_streaming_sequence would
def mock_llm_generated_actions_for_game_logic():
    # These are the actions that process_enhanced_oracle_streaming would yield
    # after talking to the (mocked) LLM and then processing its output through text_streaming_engine
    yield {"action_type": "set_oracle_state", "details": {"state": "CONSULTATION_START"}}
    yield {"action_type": "stream_text_chunk", "details": {"text": "Oracle says: ", "text_type": "FLAVOR_CONSULTATION"}}
    yield {"action_type": "stream_pause", "details": {"duration_ms": 500}}
    yield {"action_type": "stream_text_chunk", "details": {"text": "Hmm... ", "text_type": "FLAVOR_THINKING"}}
    yield {"action_type": "stream_pause", "details": {"duration_ms": 300}}
    yield {"action_type": "set_oracle_state", "details": {"state": "THINKING"}}
    yield {"action_type": "stream_text_chunk", "details": {"text": "Interesting question!", "text_type": "NARRATIVE"}}
    yield {"action_type": "add_message", "details": {"text": "A hidden clue is revealed."}} # Game action from LLM
    yield {"action_type": "set_oracle_state", "details": {"state": "IDLE"}}


@patch('fungi_fortress.llm_interface.process_enhanced_oracle_streaming')
def test_game_logic_handles_oracle_streaming(mock_process_enhanced_oracle_streaming):
    """Test that GameLogic correctly initiates and processes Oracle streaming actions."""
    print("\\n=== Game Logic Oracle Streaming Integration Test ===")
    
    # Configure a mock LLMConfig that enables streaming
    mock_llm_config = LLMConfig(
        api_key="fake_key_for_test",
        model_name="fake_model_for_test",
        provider="fake_provider",
        enable_streaming=True, # Crucial for streaming path
        context_level="low"
    )
    
    # Initialize game state and logic with the mock LLM config
    game_state = GameState(llm_config=mock_llm_config)
    game_logic = GameLogic(game_state)
    
    # Set up the mock for llm_interface.process_enhanced_oracle_streaming
    # This is what GameLogic should call when it processes the 'start_enhanced_oracle_streaming' action
    mock_process_enhanced_oracle_streaming.return_value = mock_llm_generated_actions_for_game_logic()
    
    print(f"✓ Game state initialized with streaming enabled config.")
    
    # Simulate player initiating an Oracle query
    oracle_name = "TestStreamOracle"
    player_query = "Tell me about game logic streaming?"
    
    # This event will be processed by game_logic.update()
    # game_logic will call llm_interface.handle_game_event for ORACLE_QUERY
    # handle_game_event, with streaming enabled, should return a 'start_enhanced_oracle_streaming' action.
    # game_logic should then see this action and call llm_interface.process_enhanced_oracle_streaming
    game_state.add_event("ORACLE_QUERY", {"query_text": player_query, "oracle_name": oracle_name})
    
    print(f"Processing ORACLE_QUERY event...")
    game_logic.update() # First update: processes ORACLE_QUERY, should generate start_enhanced_oracle_streaming, and call the patched process_enhanced_oracle_streaming
    
    # Assert that process_enhanced_oracle_streaming was called by GameLogic
    # The call to process_enhanced_oracle_streaming happens if handle_game_event returns the right action
    # and game_logic.process_action handles it.
    mock_process_enhanced_oracle_streaming.assert_called_once()
    call_args_list = mock_process_enhanced_oracle_streaming.call_args_list
    assert len(call_args_list) == 1
    call_kwargs = call_args_list[0][1] # Get kwargs of the first call
    
    assert call_kwargs['player_query'] == player_query
    assert call_kwargs['oracle_name'] == oracle_name
    assert call_kwargs['oracle_config'] == mock_llm_config
    
    # Check game state after the first update (streaming should be active)
    assert game_state.oracle_interaction_state == "CONSULTATION_START", f"Expected CONSULTATION_START, got {game_state.oracle_interaction_state}"
    assert game_state.oracle_streaming_active is True, "Oracle streaming should be active"
    assert game_state.oracle_streaming_generator is not None, "Oracle streaming generator should be set"
    
    print("✓ Streaming initiated by GameLogic.")
    
    # Process a few streaming updates via game_logic.update()
    max_updates = 20 # Safety break
    updates_done = 0
    initial_dialogue_len = len(game_state.oracle_current_dialogue)
    
    for i in range(max_updates):
        updates_done +=1
        game_logic.update() # This should pull from the mock_llm_generated_actions_for_game_logic generator
        print(f"  Update {i+1}: state={game_state.oracle_interaction_state}, dialogue_len={len(game_state.oracle_current_dialogue)}, streaming_active={game_state.oracle_streaming_active}")
        if not game_state.oracle_streaming_active:
            print(f"  Streaming completed after {updates_done} game logic updates.")
            break
    else:
        pytest.fail(f"Streaming did not complete within {max_updates} updates.")

    # Assertions about the final state after streaming
    assert game_state.oracle_streaming_active is False, "Streaming should be inactive after completion"
    assert game_state.oracle_interaction_state == "IDLE", f"Expected IDLE, got {game_state.oracle_interaction_state}"
    
    # Check that dialogue was added (text_chunks from the mock generator)
    assert len(game_state.oracle_current_dialogue) > initial_dialogue_len, "Dialogue should have been added"
    full_dialogue = "".join(game_state.oracle_current_dialogue)
    assert "Oracle says: Hmm... Interesting question!" in full_dialogue, "Expected text not found in dialogue"
    
    # Check if game actions from the stream were processed (e.g., add_message)
    # This requires GameLogic to have a way to process actions coming from the oracle stream.
    # Let's assume GameLogic.process_action can handle 'add_message' and it would, for example, add to game_state.messages
    # For this test, we'll check if the action was received by GameLogic. If it has a queue or direct processing:
    # This part is more complex as it depends on how GameLogic internalizes actions from the stream.
    # The provided mock generator yields {"action_type": "add_message"}. 
    # GameLogic.update() pulls from the stream; if it sees an action like this, it should process it.
    # We'll assume game_state would have some record if 'add_message' was processed.
    # This is a deeper integration point. For now, we confirmed text streaming. 
    # To verify 'add_message' action, GameLogic needs to be inspectable or have side effects we can check.
    print("Test assumes GameLogic can process actions like 'add_message' from the stream.") 