import pytest
from unittest.mock import patch, MagicMock
import json
import sys
import os

# Add parent directory to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Assuming llm_interface is in the parent directory or accessible via PYTHONPATH
from fungi_fortress import llm_interface
from fungi_fortress.llm_interface import _parse_llm_response, handle_game_event, ORACLE_LOG_FILE
from llm_interface import _detect_provider_and_call_api
from config_manager import load_oracle_config, OracleConfig

# Mock game_state and its attributes for testing handle_game_event
class MockOracleConfig:
    def __init__(self, api_key="testkey", model_name="testmodel", context_level="medium"):
        self.api_key = api_key
        self.model_name = model_name
        self.context_level = context_level

class MockGameState:
    def __init__(self, tick=100, depth=1, mission_desc=None, player_resources=None, history=None, config=None):
        self.tick = tick
        self.depth = depth
        self.mission = {"description": mission_desc} if mission_desc else None
        self.player_resources = player_resources if player_resources else {}
        self.oracle_llm_interaction_history = history if history else []
        self.oracle_config = config if config else MockOracleConfig()

    def get_tile(self, x, y): # Mock method if needed by other parts
        return None

# Tests for _parse_llm_response
def test_parse_llm_response_narrative_only():
    response_text = "This is a simple narrative response."
    narrative, actions = _parse_llm_response(response_text)
    assert narrative == "This is a simple narrative response."
    assert actions == []

def test_parse_llm_response_with_one_action():
    response_text = "Narrative part. ACTION::add_message::{\"text\": \"Hello\"}"
    narrative, actions = _parse_llm_response(response_text)
    assert narrative == "Narrative part."
    assert actions == [{"action_type": "add_message", "details": {"text": "Hello"}}]

def test_parse_llm_response_with_multiple_actions():
    response_text = "Desc. ACTION::spawn::{\"id\":1} ACTION::move::{\"id\":1, \"x\":5}"
    narrative, actions = _parse_llm_response(response_text)
    assert narrative == "Desc."
    assert actions == [
        {"action_type": "spawn", "details": {"id": 1}},
        {"action_type": "move", "details": {"id": 1, "x": 5}}
    ]

def test_parse_llm_response_malformed_json():
    response_text = "Problem. ACTION::data::{'key': 'value\"'}" # Malformed JSON: {'key': 'value"'}
    narrative, actions = _parse_llm_response(response_text)
    assert "Problem." in narrative
    assert "(The Oracle's words concerning an action were muddled: data::{'key': 'value\"'})" in narrative
    assert actions == []

def test_parse_llm_response_malformed_action_string():
    response_text = "Gesture. ACTION::nodetails" # Missing second '::'
    narrative, actions = _parse_llm_response(response_text)
    assert "Gesture." in narrative
    assert "(The Oracle made an unclear gesture: nodetails)" in narrative
    assert actions == []

def test_parse_llm_response_empty_string():
    response_text = ""
    narrative, actions = _parse_llm_response(response_text)
    assert narrative == ""
    assert actions == []

def test_parse_llm_response_action_at_start():
    response_text = "ACTION::add_message::{'text': 'Alert!'} Main narrative."
    # Based on current implementation, if ACTION is first, the first part of narrative becomes empty.
    # If this behavior is not desired, _parse_llm_response needs adjustment.
    narrative, actions = _parse_llm_response(response_text)
    # The first part of the split is "", which becomes the initial narrative.
    # The second part is "add_message::{'text': 'Alert!'} Main narrative."
    # This will fail JSON parsing for the action details.
    assert narrative.strip() == "(The Oracle's words concerning an action were muddled: add_message::{'text': 'Alert!'} Main narrative.)\""
    assert actions == []

def test_parse_llm_response_action_at_start_clean():
    response_text = "ACTION::add_message::{\"text\": \"Alert!\"}"
    narrative, actions = _parse_llm_response(response_text)
    assert narrative == "" # parts[0] is empty
    assert actions == [{"action_type": "add_message", "details": {"text": "Alert!"}}]

# Tests for handle_game_event
@patch('fungi_fortress.llm_interface._log_oracle_interaction') # Path to log in the module where it's called from
@patch('fungi_fortress.llm_interface._call_llm_api')        # Path to api call in the module
def test_handle_game_event_simple_query(mock_call_llm, mock_log_interaction):
    mock_call_llm.return_value = "LLM says hi. ACTION::test_action::{\"detail\": \"value\"}"
    game_state = MockGameState()
    event_data = {"type": "ORACLE_QUERY", "details": {"query_text": "Hello Oracle?"}}

    actions_to_execute = handle_game_event(event_data, game_state)

    mock_call_llm.assert_called_once()
    # Check that the prompt was constructed (can be more specific here if needed)
    assert "Hello Oracle?" in mock_call_llm.call_args[0][0] # prompt is the first arg
    
    assert len(actions_to_execute) == 3 # add_oracle_dialogue, test_action, set_oracle_state
    assert actions_to_execute[0]["action_type"] == "add_oracle_dialogue"
    assert actions_to_execute[0]["details"]["text"] == "LLM says hi."
    assert actions_to_execute[1]["action_type"] == "test_action"
    assert actions_to_execute[1]["details"] == {"detail": "value"}
    assert actions_to_execute[2]["action_type"] == "set_oracle_state"

    mock_log_interaction.assert_called_once()
    log_args = mock_log_interaction.call_args[1] # kwargs
    assert log_args["player_query"] == "Hello Oracle?"
    assert log_args["raw_response"] == "LLM says hi. ACTION::test_action::{\"detail\": \"value\"}"
    assert log_args["parsed_narrative"] == "LLM says hi."
    assert log_args["parsed_actions"] == [{"action_type": "test_action", "details": {"detail": "value"}}]
    assert log_args["error_message"] is None

@patch('fungi_fortress.llm_interface._log_oracle_interaction')
@patch('fungi_fortress.llm_interface._call_llm_api')
def test_handle_game_event_api_error(mock_call_llm, mock_log_interaction):
    # Simulate _call_llm_api returning one of its error strings
    mock_call_llm.return_value = "The Oracle's connection is disrupted. (Error: API Key not configured)"
    game_state = MockGameState(config=MockOracleConfig(api_key="YOUR_API_KEY_HERE")) # Simulate bad key
    event_data = {"type": "ORACLE_QUERY", "details": {"query_text": "Test query"}}

    actions_to_execute = handle_game_event(event_data, game_state)

    mock_call_llm.assert_called_once()
    assert len(actions_to_execute) == 2 # add_oracle_dialogue (with error), set_oracle_state
    assert actions_to_execute[0]["action_type"] == "add_oracle_dialogue"
    assert "The Oracle's connection is disrupted." in actions_to_execute[0]["details"]["text"]
    
    mock_log_interaction.assert_called_once()
    log_args = mock_log_interaction.call_args[1]
    assert log_args["player_query"] == "Test query"
    # raw_response will contain the error message returned by _call_llm_api
    assert "(Error: API Key not configured)" in log_args["raw_response"]
    # If _call_llm_api returns an error STRING, this string IS llm_response_text.
    # _parse_llm_response will then treat this entire string as narrative if it doesn't contain ACTION::
    assert log_args["parsed_narrative"] == "The Oracle's connection is disrupted. (Error: API Key not configured)"
    assert log_args["parsed_actions"] == [] # Because the error string was treated as pure narrative
    assert log_args["error_message"] is None # error_for_log is for when llm_response_text is None/empty or _call_llm_api raises an exception

@patch('fungi_fortress.llm_interface._log_oracle_interaction')
@patch('fungi_fortress.llm_interface._call_llm_api')
def test_handle_game_event_empty_llm_response(mock_call_llm, mock_log_interaction):
    mock_call_llm.return_value = None # Simulate LLM API returning None
    game_state = MockGameState()
    event_data = {"type": "ORACLE_QUERY", "details": {"query_text": "Query for empty response"}}

    actions_to_execute = handle_game_event(event_data, game_state)

    mock_call_llm.assert_called_once()
    assert len(actions_to_execute) == 2 # add_oracle_dialogue (error), set_oracle_state
    assert "empty or no response from API" in actions_to_execute[0]["details"]["text"]

    mock_log_interaction.assert_called_once()
    log_args = mock_log_interaction.call_args[1]
    assert log_args["raw_response"] is None
    assert log_args["parsed_narrative"] is None
    assert log_args["parsed_actions"] is None
    assert "empty or no response from API" in log_args["error_message"]

@patch('fungi_fortress.llm_interface._log_oracle_interaction')
@patch('fungi_fortress.llm_interface._call_llm_api')
def test_handle_game_event_no_query_text(mock_call_llm, mock_log_interaction):
    game_state = MockGameState()
    event_data = {"type": "ORACLE_QUERY", "details": {}} # No query_text

    actions_to_execute = handle_game_event(event_data, game_state)

    assert not mock_call_llm.called # LLM should not be called
    assert len(actions_to_execute) == 1
    assert actions_to_execute[0]["action_type"] == "add_oracle_dialogue"
    assert actions_to_execute[0]["details"]["text"] == "(You offer your thoughts, but no words escape.)"
    # Logging is not performed if query_text is missing because it returns early
    assert not mock_log_interaction.called

@patch('fungi_fortress.llm_interface._log_oracle_interaction')
@patch('fungi_fortress.llm_interface._call_llm_api')
def test_handle_game_event_context_levels(mock_call_llm, mock_log_interaction):
    mock_call_llm.return_value = "Response"
    
    # Low context
    game_state_low = MockGameState(config=MockOracleConfig(context_level="low"), history=[{"player":"p1", "oracle":"o1"},{"player":"p2", "oracle":"o2"}])
    handle_game_event({"type": "ORACLE_QUERY", "details": {"query_text": "q_low"}}, game_state_low)
    prompt_low = mock_call_llm.call_args[0][0]
    assert "Tick: 100" in prompt_low
    assert "Player depth: 1" in prompt_low
    assert "Mission:" not in prompt_low # Low context doesn't include mission
    assert "Player: p2\nOracle: o2" in prompt_low # Last 1 history item
    assert "Player: p1\nOracle: o1" not in prompt_low

    # High context
    game_state_high = MockGameState(config=MockOracleConfig(context_level="high"), 
                                  mission_desc="Defeat goblin king", 
                                  player_resources={"gold": 50}, 
                                  history=[{"player":f"p{i}", "oracle":f"o{i}"} for i in range(6)])
    handle_game_event({"type": "ORACLE_QUERY", "details": {"query_text": "q_high"}}, game_state_high)
    prompt_high = mock_call_llm.call_args[0][0]
    assert "Mission: Defeat goblin king" in prompt_high
    assert "Player resources: {'gold': 50}" in prompt_high
    for i in range(1, 6): # Last 5 history items (indices 1 to 5 from a 6-item list)
        assert f"Player: p{i}\nOracle: o{i}" in prompt_high 
    assert "Player: p0\nOracle: o0" not in prompt_high # Oldest item should be out

    # Ensure log is called for each (it will be, due to the setup)
    assert mock_log_interaction.call_count == 2

# Basic test to ensure the log file is mentioned in a constant
# This doesn't write to the file system, just checks the constant
def test_oracle_log_file_constant():
    assert ORACLE_LOG_FILE == "oracle_interactions.log"

class TestProviderDetection:
    """Test the LLM provider detection logic."""
    
    def test_xai_model_detection(self):
        """Test that Grok models are correctly detected as XAI provider."""
        test_cases = [
            "grok-3",
            "grok-3-beta", 
            "grok-2-1212",
            "grok-beta",
            "grok-vision-beta"
        ]
        
        for model in test_cases:
            with patch('llm_interface._call_xai_api') as mock_xai:
                mock_xai.return_value = "Test response"
                
                result = _detect_provider_and_call_api(
                    "test prompt", 
                    "test-api-key", 
                    model,
                    None,  # provider_hint
                    None   # oracle_config
                )
                
                mock_xai.assert_called_once()
                assert result == "Test response"
    
    def test_openai_model_detection(self):
        """Test that OpenAI models are correctly detected."""
        test_cases = [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
            "text-davinci-003"
        ]
        
        for model in test_cases:
            with patch('llm_interface._call_openai_compatible_api') as mock_openai:
                mock_openai.return_value = "Test response"
                
                result = _detect_provider_and_call_api(
                    "test prompt", 
                    "test-api-key", 
                    model,
                    None,  # provider_hint
                    None   # oracle_config
                )
                
                mock_openai.assert_called_once()
                assert result == "Test response"
    
    def test_anthropic_model_detection(self):
        """Test that Claude models are correctly detected as Anthropic."""
        test_cases = [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022", 
            "claude-3-opus-20240229",
            "claude-2.1"
        ]
        
        for model in test_cases:
            with patch('llm_interface._call_openai_compatible_api') as mock_anthropic:
                mock_anthropic.return_value = "Test response"
                
                result = _detect_provider_and_call_api(
                    "test prompt", 
                    "test-api-key", 
                    model,
                    None,  # provider_hint
                    None   # oracle_config
                )
                
                mock_anthropic.assert_called_once()
                assert result == "Test response"
    
    def test_groq_model_detection(self):
        """Test that open-source models are correctly detected as Groq."""
        test_cases = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "gemma2-9b-it"
        ]
        
        for model in test_cases:
            with patch('llm_interface._call_groq_api') as mock_groq:
                mock_groq.return_value = "Test response"
                
                result = _detect_provider_and_call_api(
                    "test prompt", 
                    "test-api-key", 
                    model,
                    None,  # provider_hint
                    None   # oracle_config
                )
                
                mock_groq.assert_called_once()
                assert result == "Test response"
    
    def test_provider_hint_override(self):
        """Test that explicit provider hints override auto-detection."""
        with patch('llm_interface._call_xai_api') as mock_xai:
            mock_xai.return_value = "Test response"
            
            # Use a non-XAI model name but force XAI provider
            result = _detect_provider_and_call_api(
                "test prompt", 
                "test-api-key", 
                "unknown-model",
                "xai",  # provider_hint
                None    # oracle_config
            )
            
            mock_xai.assert_called_once()
            assert result == "Test response"
    
    def test_invalid_api_key_handling(self):
        """Test that invalid API keys are handled properly."""
        invalid_keys = [
            None,
            "",
            "YOUR_API_KEY_HERE",
            "testkey123"
        ]
        
        for key in invalid_keys:
            result = _detect_provider_and_call_api(
                "test prompt",
                key,
                "gpt-4o",
                None,  # provider_hint
                None   # oracle_config
            )
            
            assert "Oracle's connection is disrupted" in result
            assert "API Key not configured" in result
    
    def test_missing_model_name_handling(self):
        """Test that missing model names are handled properly."""
        result = _detect_provider_and_call_api(
            "test prompt",
            "valid-api-key",
            None,
            None,  # provider_hint
            None   # oracle_config
        )
        
        assert "Oracle's connection is unstable" in result
        assert "LLM Model not specified" in result


class TestOracleConfig:
    """Test the Oracle configuration loading and validation."""
    
    def test_oracle_config_defaults(self):
        """Test that OracleConfig has correct defaults."""
        config = OracleConfig()
        
        assert config.api_key is None
        assert config.model_name == "gpt-4o-mini"
        assert config.provider == "auto"
        assert config.context_level == "medium"
        assert config.is_real_api_key_present is False
    
    def test_oracle_config_api_key_validation(self):
        """Test that API key validation works correctly."""
        # Test with real-looking key
        config = OracleConfig(api_key="sk-1234567890abcdef")
        assert config.is_real_api_key_present is True
        
        # Test with placeholder keys
        invalid_keys = ["YOUR_API_KEY_HERE", "testkey123", "None", "", None]
        for key in invalid_keys:
            config = OracleConfig(api_key=key)
            assert config.is_real_api_key_present is False
    
    @patch('builtins.open')
    @patch('os.path.exists')
    def test_config_file_not_found(self, mock_exists, mock_open):
        """Test behavior when config file doesn't exist."""
        mock_exists.return_value = False
        mock_open.side_effect = FileNotFoundError()
        
        config = load_oracle_config("nonexistent.ini")
        
        assert isinstance(config, OracleConfig)
        assert config.api_key is None
        assert config.model_name == "gpt-4o-mini"
        assert config.provider == "auto"


if __name__ == "__main__":
    pytest.main([__file__]) 