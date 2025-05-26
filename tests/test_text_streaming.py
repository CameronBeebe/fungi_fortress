#!/usr/bin/env python
"""Test script for the new text streaming system."""

# Import the text streaming engine
from fungi_fortress.text_streaming import text_streaming_engine

def test_narrative_action_separation():
    """Test that the streaming engine can separate narrative from actions."""
    print("Testing narrative/action separation...")
    
    # Test structured JSON response
    json_response = '''{"narrative": "The Oracle speaks of ancient wisdom.", "actions": [{"action_type": "add_message", "details": {"text": "A mystical energy fills the air."}}]}'''
    
    narrative, actions = text_streaming_engine.separate_narrative_from_actions(json_response)
    print(f"JSON Response - Narrative: '{narrative}'")
    print(f"JSON Response - Actions: {actions}")
    
    # Test legacy ACTION:: format
    legacy_response = '''The Oracle gazes into the fungal network and speaks: "Your path is illuminated by ancient spores." ACTION::add_message::{"text": "The chamber glows with bioluminescent light."}'''
    
    narrative, actions = text_streaming_engine.separate_narrative_from_actions(legacy_response)
    print(f"Legacy Response - Narrative: '{narrative}'")
    print(f"Legacy Response - Actions: {actions}")
    
    print("✓ Narrative/action separation test completed\n")

def test_flavor_text_generation():
    """Test that the streaming engine can generate flavor text."""
    print("Testing flavor text generation...")
    
    flavor_texts = text_streaming_engine.create_oracle_flavor_text("Ancient Sporekeeper", "consultation", "mystical chamber")
    print(f"Generated {len(flavor_texts)} flavor texts:")
    for i, text in enumerate(flavor_texts, 1):
        print(f"  {i}. {text}")
    
    waiting_texts = text_streaming_engine.create_oracle_waiting_text("Ancient Sporekeeper")
    print(f"Generated waiting text: {waiting_texts[0]}")
    
    print("✓ Flavor text generation test completed\n")

def test_streaming_sequence():
    """Test the complete Oracle streaming sequence."""
    print("Testing complete Oracle streaming sequence...")
    
    # Mock LLM response iterator
    def mock_llm_response():
        responses = [
            "The Oracle",
            " gazes into",
            " the vast",
            " mycelial network",
            " and speaks:",
            " \"Your destiny",
            " is intertwined",
            " with the",
            " ancient fungi.\"",
            " ACTION::add_message::",
            "{\"text\": \"Spores",
            " dance in",
            " the air.\"}"
        ]
        for response in responses:
            yield response
    
    oracle_name = "Test Oracle"
    player_query = "What is my destiny?"
    
    print(f"Starting streaming sequence for {oracle_name}...")
    print(f"Player query: '{player_query}'")
    print("\nStreaming actions:")
    
    action_count = 0
    for action in text_streaming_engine.start_oracle_streaming_sequence(
        oracle_name, player_query, mock_llm_response()
    ):
        action_count += 1
        action_type = action.get("action_type", "unknown")
        
        if action_type == "stream_text_chunk":
            details = action.get("details", {})
            text = details.get("text", "")
            text_type = details.get("text_type", "unknown")
            add_newline = details.get("add_newline", False)
            print(f"  {action_count}. TEXT: '{text}' (type: {text_type}, newline: {add_newline})")
        elif action_type == "stream_pause":
            duration = action.get("details", {}).get("duration_ms", 0)
            print(f"  {action_count}. PAUSE: {duration}ms")
        else:
            print(f"  {action_count}. ACTION: {action_type}")
    
    print(f"\n✓ Streaming sequence test completed ({action_count} actions)\n")

# Pytest will discover and run functions starting with "test_"
# The __main__ block is not needed for pytest execution but can be kept for direct script running if desired.
# For now, let's remove it to make it a pure pytest file.
# if __name__ == "__main__":
#     print("=== Text Streaming Engine Test ===\n")
    
#     try:
#         test_narrative_action_separation()
#         test_flavor_text_generation()
#         test_streaming_sequence()
        
#         print("🎉 All tests passed! The text streaming system is working correctly.")
        
#     except Exception as e:
#         print(f"❌ Test failed with error: {e}")
#         import traceback
#         traceback.print_exc()
#         # sys.exit(1) # sys is not imported 