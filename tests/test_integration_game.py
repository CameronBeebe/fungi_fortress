#!/usr/bin/env python3
"""
Test the Oracle integration within the game context to make sure XAI responses work properly.
"""

import json
from llm_interface import handle_game_event, _call_llm_api, _parse_llm_response
from config_manager import load_oracle_config

class MockGameState:
    """Mock game state for testing"""
    def __init__(self):
        self.tick = 100
        self.depth = 5
        self.mission = {"description": "Test Mission Alpha"}
        self.player_resources = {"wood": 10, "stone": 5}
        self.oracle_llm_interaction_history = [
            {"player": "P_query_6", "oracle": "O_response_6"}
        ]
        self.oracle_config = load_oracle_config()

def test_direct_llm_call():
    """Test calling the LLM API directly"""
    print("\n=== Testing Direct LLM API Call ===")
    
    oracle_config = load_oracle_config()
    if not oracle_config.is_real_api_key_present:
        print("ERROR: Invalid API key configuration")
        assert False, "Invalid API key configuration"
    
    prompt = """You are Great Oracle, a wise, ancient, and somewhat cryptic Oracle in the Fungi Fortress. Respond to the player's query with insightful, thematic, and sometimes enigmatic guidance. Your responses should be a single paragraph.

Game Context: Tick: 100. Player depth: 5.

Player Query: What is the meaning of this mushroom?"""
    
    response = _call_llm_api(
        prompt=prompt,
        api_key=oracle_config.api_key,
        model_name=oracle_config.model_name,
        provider=oracle_config.provider,
        oracle_config=oracle_config
    )
    
    print(f"Raw LLM Response: {response}")
    
    if response and "Oracle says... nothing much" not in response:
        print("✅ Direct LLM call successful!")
        
        # Test parsing
        narrative, actions = _parse_llm_response(response)
        print(f"Parsed Narrative: {narrative}")
        print(f"Parsed Actions: {actions}")
        assert True  # Test passed
    else:
        print("❌ Direct LLM call failed or returned default response")
        assert False, "Direct LLM call failed or returned default response"

def test_game_event_handling():
    """Test the full game event handling pipeline"""
    print("\n=== Testing Game Event Handling ===")
    
    mock_game_state = MockGameState()
    
    # Create an Oracle query event
    event_data = {
        "type": "ORACLE_QUERY",
        "details": {
            "query_text": "What is the meaning of this mushroom?",
            "oracle_name": "Great Oracle"
        }
    }
    
    # Process the event
    actions = handle_game_event(event_data, mock_game_state)
    
    print(f"Generated Actions: {actions}")
    
    assert actions is not None, "No actions generated"
    
    # Look for Oracle dialogue action
    oracle_response = None
    for action in actions:
        if action.get("action_type") == "add_oracle_dialogue":
            oracle_response = action.get("details", {}).get("text")
            break
    
    if oracle_response and "Oracle says... nothing much" not in oracle_response:
        print("✅ Game event handling successful!")
        print(f"Oracle Response: {oracle_response}")
        assert True  # Test passed
    else:
        print("❌ Game event handling failed - got default response")
        print(f"Oracle Response: {oracle_response}")
        assert False, f"Game event handling failed - got default response: {oracle_response}"

def test_structured_vs_text_responses():
    """Test both structured and text response formats"""
    print("\n=== Testing Response Format Variations ===")
    
    # Test text response parsing
    text_response = "Ah, seeker of hidden wonders, this mushroom represents transformation and growth through darkness. ACTION::add_message::{'text': 'The spores shimmer with ancient magic.'}"
    
    narrative, actions = _parse_llm_response(text_response)
    print(f"Text format - Narrative: {narrative}")
    print(f"Text format - Actions: {actions}")
    
    # Test JSON structured response parsing
    structured_response = {
        "narrative": "The Oracle contemplates the mysterious fungus before you, its cap gleaming with otherworldly light.",
        "actions": [
            {
                "action_type": "add_message",
                "details": {"text": "A vision of the mycelial network flashes before your eyes."}
            }
        ]
    }
    
    json_response = json.dumps(structured_response)
    narrative2, actions2 = _parse_llm_response(json_response)
    print(f"JSON format - Narrative: {narrative2}")
    print(f"JSON format - Actions: {actions2}")
    
    # Verify parsing worked correctly
    assert "Ah, seeker of hidden wonders" in narrative
    assert len(actions) == 1
    assert actions[0]["action_type"] == "add_message"
    
    assert "Oracle contemplates" in narrative2
    assert len(actions2) == 1
    assert actions2[0]["action_type"] == "add_message"

def main():
    """Run all tests"""
    print("Testing XAI/Oracle Integration")
    print("=" * 50)
    
    tests = [
        test_direct_llm_call,
        test_game_event_handling,
        test_structured_vs_text_responses
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ {test_func.__name__} failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("Test Summary:")
    print(f"Passed: {sum(results)}/{len(results)}")
    
    if all(results):
        print("🎉 All tests passed! Oracle integration is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return all(results)

if __name__ == "__main__":
    main() 