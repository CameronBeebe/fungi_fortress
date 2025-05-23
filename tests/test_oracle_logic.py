import pytest
from unittest.mock import Mock
from fungi_fortress.oracle_logic import get_canned_response

# Mock a simple Oracle class for testing purposes
class MockOracle:
    def __init__(self, name="TestOracle", canned_responses=None):
        self.name = name
        # Ensure canned_responses is always a dict if provided, or None
        if canned_responses is not None and not isinstance(canned_responses, dict):
            raise ValueError("canned_responses must be a dictionary or None")
        self.canned_responses = canned_responses


def test_get_canned_response_no_oracle():
    """Test behavior when the oracle object itself is None."""
    response = get_canned_response(None, "greeting")
    assert response == ["The Oracle remains eerily silent.", "(Error: Oracle has no responses defined)"]

def test_get_canned_response_oracle_has_no_canned_responses_attribute():
    """Test behavior when the oracle object doesn't have a canned_responses attribute."""
    oracle_without_attribute = Mock()
    # Simulate the attribute being missing entirely for a more robust test
    delattr(oracle_without_attribute, 'canned_responses') 
    # We expect a specific error or handling, but the current function handles it by checking hasattr
    # So, we need to ensure our mock behaves as if hasattr(oracle, 'canned_responses') is false.
    # A simple way is to not define it. Forcing an AttributeError is another way if hasattr was not used.

    # Re-mocking to ensure canned_responses is not present
    oracle_missing_attr = Mock(spec=['name']) # Only has 'name' attribute
    
    response = get_canned_response(oracle_missing_attr, "greeting")
    # Based on current get_canned_response, if 'canned_responses' is missing, it hits the first 'if not oracle or not hasattr...'
    assert response == ["The Oracle remains eerily silent.", "(Error: Oracle has no responses defined)"]


def test_get_canned_response_empty_canned_responses_dict():
    """Test with an oracle that has an empty canned_responses dictionary."""
    oracle = MockOracle(canned_responses={})
    response = get_canned_response(oracle, "greeting")
    assert response == ["The Oracle remains eerily silent.", "(Error: Oracle has no responses defined)"]

def test_get_canned_response_valid_trigger_list_of_strings():
    """Test a valid trigger that returns a list of strings."""
    responses = {"greeting": ["Hello there!", "Welcome!"]}
    oracle = MockOracle(canned_responses=responses)
    response = get_canned_response(oracle, "greeting")
    assert response == ["Hello there!", "Welcome!"]

def test_get_canned_response_valid_trigger_single_string():
    """Test a valid trigger that returns a single string."""
    responses = {"farewell": "Goodbye!"}
    oracle = MockOracle(canned_responses=responses)
    response = get_canned_response(oracle, "farewell")
    assert response == ["Goodbye!"]

def test_get_canned_response_invalid_trigger_with_fallback():
    """Test an invalid trigger when a fallback_error response is defined."""
    responses = {"fallback_error": ["Something went wrong.", "Please try again."]}
    oracle = MockOracle(canned_responses=responses)
    response = get_canned_response(oracle, "unknown_trigger")
    assert response == ["Something went wrong.", "Please try again."]

def test_get_canned_response_invalid_trigger_no_fallback():
    """Test an invalid trigger when no fallback_error response is defined."""
    responses = {"greeting": ["Hello!"]} # No fallback_error
    oracle = MockOracle(canned_responses=responses)
    response = get_canned_response(oracle, "unknown_trigger")
    assert response == ["The Oracle offers no clear answer at this moment.", "(Error: Trigger 'unknown_trigger' not found and no fallback_error defined in Oracle responses)"]

def test_get_canned_response_malformed_dialogue_entry_integer():
    """Test behavior with a malformed dialogue entry (e.g., an integer)."""
    responses = {"greeting": 123} # Malformed entry
    oracle = MockOracle(canned_responses=responses)
    response = get_canned_response(oracle, "greeting")
    assert response == ["The Oracle's words are jumbled.", "(Error: Malformed dialogue for trigger 'greeting')"]

def test_get_canned_response_malformed_dialogue_entry_dict():
    """Test behavior with a malformed dialogue entry (e.g., a dictionary)."""
    responses = {"greeting": {"text": "Hello"}} # Malformed entry
    oracle = MockOracle(canned_responses=responses)
    response = get_canned_response(oracle, "greeting")
    assert response == ["The Oracle's words are jumbled.", "(Error: Malformed dialogue for trigger 'greeting')"]
    
def test_get_canned_response_trigger_exists_but_value_is_none():
    """Test a trigger that exists but its value is None."""
    responses = {"empty_greeting": None}
    oracle = MockOracle(canned_responses=responses)
    response = get_canned_response(oracle, "empty_greeting")
    # Based on current logic, if dialogue_lines is None, it proceeds to fallback
    assert response == ["The Oracle offers no clear answer at this moment.", "(Error: Trigger 'empty_greeting' not found and no fallback_error defined in Oracle responses)"]

def test_get_canned_response_trigger_exists_value_is_none_with_fallback():
    """Test a trigger that exists but its value is None, with a fallback defined."""
    responses = {
        "empty_greeting": None,
        "fallback_error": ["Fallback activated."]
    }
    oracle = MockOracle(canned_responses=responses)
    response = get_canned_response(oracle, "empty_greeting")
    assert response == ["Fallback activated."]

def test_get_canned_response_default_trigger():
    """Test the default trigger if none is provided in the call."""
    responses = {"default_query_response": ["The Oracle ponders..."]}
    oracle = MockOracle(canned_responses=responses)
    response = get_canned_response(oracle) # No trigger specified
    assert response == ["The Oracle ponders..."]

def test_get_canned_response_default_trigger_not_defined_with_fallback():
    """Test when default trigger is not defined, but fallback exists."""
    responses = {"fallback_error": ["Default not found, using fallback."]}
    oracle = MockOracle(canned_responses=responses)
    response = get_canned_response(oracle) # No trigger specified
    assert response == ["Default not found, using fallback."]
    
def test_get_canned_response_default_trigger_not_defined_no_fallback():
    """Test when default trigger is not defined and no fallback exists."""
    responses = {"other_response": ["This is not the default."]}
    oracle = MockOracle(canned_responses=responses)
    response = get_canned_response(oracle) # No trigger specified
    expected_message_part1 = "The Oracle offers no clear answer at this moment."
    expected_message_part2 = "(Error: Trigger 'default_query_response' not found and no fallback_error defined in Oracle responses)"
    assert response == [expected_message_part1, expected_message_part2]

def test_get_canned_response_fallback_is_single_string():
    """Test when the fallback_error itself is a single string."""
    responses = {"fallback_error": "A single string fallback."}
    oracle = MockOracle(canned_responses=responses)
    response = get_canned_response(oracle, "unknown_trigger")
    assert response == ["A single string fallback."] 