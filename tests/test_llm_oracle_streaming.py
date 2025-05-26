#!/usr/bin/env python3
"""Test script to verify Oracle streaming action generation works correctly."""

import pytest
from unittest.mock import patch, MagicMock

from fungi_fortress.config_manager import LLMConfig
from fungi_fortress import llm_interface

# Mock LLM response iterator
def mock_streaming_llm_response_chunks():
    responses = [
        "The Oracle",
        " begins to speak...",
        " ACTION::add_message::{\"text\": \"A vision appears.\"}",
        " More narrative.",
        " ACTION::another_action::{\"param\": \"value\"}"
    ]
    for response_part in responses:
        # Simulate the structure of chunks from _call_xai_api_streaming etc.
        # which yield dicts like {"text_chunk": "...", "is_error": False}
        # or just strings. For simplicity, let\'s assume process_enhanced_oracle_streaming
        # calls a function that yields simple strings directly for this mock.
        # If it expects dicts, this mock needs adjustment.
        # Based on llm_interface, _call_llm_api_streaming yields strings.
        yield response_part

@patch('fungi_fortress.llm_interface._call_llm_api_streaming')
def test_process_enhanced_oracle_streaming_logic(mock_call_api_streaming):
    """Test the enhanced Oracle streaming processing logic with a mock LLM response."""
    print("\\n=== Testing Enhanced Oracle Streaming Logic ===")
    
    # Configure a mock LLMConfig
    mock_config = LLMConfig(
        api_key="test_api_key",
        model_name="test_model",
        provider="test_provider",
        context_level="low",
        enable_streaming=True
    )
    
    # Set up the mock for the underlying streaming API call
    mock_call_api_streaming.return_value = mock_streaming_llm_response_chunks()
    
    oracle_name = "Mock Oracle"
    player_query = "What is the mock meaning of life?"
    # Prompt construction is part of process_enhanced_oracle_streaming, so we don\'t need to pre-form it here.
    
    print(f"Testing streaming for query: \'{player_query}\' with mock LLM.")
    
    action_list = []
    text_chunks_collected = []
    
    try:
        streaming_generator = llm_interface.process_enhanced_oracle_streaming(
            prompt="This will be overridden by internal prompt construction", # Placeholder
            api_key=mock_config.api_key, # Passed to _call_llm_api_streaming
            model_name=mock_config.model_name, # Passed to _call_llm_api_streaming
            provider_hint=mock_config.provider, # Passed to _call_llm_api_streaming
            llm_config=mock_config, # Used for various settings by process_enhanced_oracle_streaming
            player_query=player_query, # Used by process_enhanced_oracle_streaming
            oracle_name=oracle_name # Used by process_enhanced_oracle_streaming
        )
        
        for action_count, action in enumerate(streaming_generator, 1):
            print(f"  Action {action_count}: {action}")
            action_list.append(action)
            action_type = action.get("action_type")
            details = action.get("details", {})
            
            if action_type == "stream_text_chunk":
                text = details.get("text", "")
                if text and not details.get("is_error", False):
                    text_chunks_collected.append(text)
            
            if action_count > 200: # Safety break for test (increased from 20)
                print("  ... (stopping test after 200 actions)")
                break
        
        combined_text = "".join(text_chunks_collected)
        print(f"\\n✓ Mock streaming completed.")
        print(f"  Total actions generated: {len(action_list)}")
        print(f"  Combined text from chunks: \'{combined_text}\'")

        # Assertions
        assert len(action_list) > 0, "No actions were generated"
        mock_call_api_streaming.assert_called_once() # Check that the underlying API call was made
        
        # Revised expectations based on current text_streaming_engine logic:
        # 1. Flavor text chunks (multiple \'stream_text_chunk\' actions)
        # 2. stream_pause (after each flavor text line)
        # 3. set_oracle_state (thinking)
        # 4. "Waiting" text chunks (multiple \'stream_text_chunk\' actions) - e.g., "Oracle communes..."
        # 5. stream_pause (after waiting text line)
        # 6. Narrative from LLM (multiple \'stream_text_chunk\' actions)
        # 7. Parsed game actions from LLM response (e.g., \'add_message\', \'another_action\')
        # 8. set_oracle_state (idle or awaiting_prompt)
        
        action_types = [a.get('action_type') for a in action_list]
        
        # Check for presence of key action types
        assert "stream_text_chunk" in action_types
        assert "stream_pause" in action_types # Pauses occur after flavor/waiting text lines
        assert "set_oracle_state" in action_types
        
        # Check for specific game actions parsed from the mock LLM response
        assert "add_message" in action_types 
        assert "another_action" in action_types
        
        # Verify that "set_oracle_state" to "thinking" and then to "awaiting_prompt" (or "idle") occurs
        thinking_state_set = False
        idle_state_set = False
        for action in action_list:
            if action.get("action_type") == "set_oracle_state":
                if action.get("details", {}).get("state") == "THINKING":
                    thinking_state_set = True
                # The final state might be AWAITING_PROMPT or IDLE depending on exact flow
                if action.get("details", {}).get("state") in ["AWAITING_PROMPT", "IDLE"]:
                    idle_state_set = True
        
        assert thinking_state_set, "Oracle state was not set to THINKING"
        assert idle_state_set, "Oracle state was not set back to AWAITING_PROMPT or IDLE at the end"

        # Check that "The Oracle begins to speak..." is part of the streamed text
        # This part of the original test might be too specific if flavor text is randomized.
        # Instead, check for core parts of the mock LLM response.
        assert "The Oracle" in combined_text # From mock_streaming_llm_response_chunks
        assert "begins to speak..." in combined_text # From mock_streaming_llm_response_chunks
        assert "More narrative." in combined_text # From mock_streaming_llm_response_chunks
        
        # Check that player_query and oracle_name were used in the prompt construction for the mock call
        call_args = mock_call_api_streaming.call_args
        actual_prompt_sent_to_llm = call_args[0][0] # prompt is the first positional argument
        assert player_query in actual_prompt_sent_to_llm
        assert f"You are {oracle_name}" in actual_prompt_sent_to_llm
        
        # Verify llm_config was passed through
        assert call_args[1]['llm_config'] == mock_config


    except Exception as e:
        print(f"❌ Error during mock streaming test: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"Test failed with exception: {e}") 