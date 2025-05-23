# oracle_logic.py
"""This module contains logic specific to Oracle interactions,
including handling canned responses and managing LLM communication flow.
"""

from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .characters import Oracle # For type hinting
    from .game_state import GameState # For type hinting, if needed later

def get_canned_response(oracle: 'Oracle', trigger: str = "default_query_response") -> List[str]:
    """Retrieves a canned response from the Oracle based on a trigger.

    Args:
        oracle (Oracle): The Oracle entity providing the response.
        trigger (str): The key for the type of response needed (e.g., "greeting", "no_api_key").
                       Defaults to "default_query_response".

    Returns:
        List[str]: A list of dialogue lines. Returns a generic error message if the
                   specified trigger is not found or if the Oracle has no canned responses.
    """
    if not oracle or not hasattr(oracle, 'canned_responses') or not oracle.canned_responses:
        return ["The Oracle remains eerily silent.", "(Error: Oracle has no responses defined)"]

    # Check if the trigger exists directly in the canned_responses dictionary
    dialogue_lines = oracle.canned_responses.get(trigger)

    if dialogue_lines:
        if isinstance(dialogue_lines, list):
            return dialogue_lines
        elif isinstance(dialogue_lines, str): # Handle single string dialogue for convenience
            return [dialogue_lines]
        else:
            # This case should ideally not happen if data is structured correctly
            return [f"The Oracle's words are jumbled.", f"(Error: Malformed dialogue for trigger '{trigger}')"]
    
    # Fallback if the specific trigger isn't found
    fallback_dialogue = oracle.canned_responses.get("fallback_error")
    if fallback_dialogue:
        if isinstance(fallback_dialogue, list):
            return fallback_dialogue
        elif isinstance(fallback_dialogue, str):
            return [fallback_dialogue]
            
    return ["The Oracle offers no clear answer at this moment.", f"(Error: Trigger '{trigger}' not found and no fallback_error defined in Oracle responses)"]

# Example usage (can be run if characters.py and this file are in the same dir for simple testing)
if __name__ == "__main__":
    # This is a simplified mock for testing; real Oracle would come from game_state
    class MockOracle:
        def __init__(self, name, canned_responses):
            self.name = name
            self.canned_responses = canned_responses

    sample_responses = { # Changed to dictionary structure
        "greeting": ["Greetings, seeker."],
        "farewell": "Until we meet again.", # Kept as string to test that path
        "fallback_error": ["Something is amiss."]
    }
    test_oracle = MockOracle("Test Oracle", sample_responses)

    print(f"Greeting: {get_canned_response(test_oracle, 'greeting')}")
    print(f"Farewell: {get_canned_response(test_oracle, 'farewell')}")
    print(f"Unknown Trigger: {get_canned_response(test_oracle, 'unknown_trigger')}") # Will use fallback_error
    
    empty_oracle = MockOracle("Empty Oracle", {}) # Changed to empty dict
    print(f"Empty Oracle Greeting: {get_canned_response(empty_oracle, 'greeting')}")

    malformed_oracle = MockOracle("Malformed Oracle", {"greeting": 123}) # Changed to dict
    print(f"Malformed Oracle Greeting: {get_canned_response(malformed_oracle, 'greeting')}") 