import pytest
from unittest.mock import patch, mock_open, ANY, Mock
import configparser
import io
import os
from unittest.mock import call

from fungi_fortress.config_manager import load_llm_config, LLMConfig, DEFAULT_CONFIG_FILENAME
# Import the actual PACKAGE_ROOT_DIR to verify calls to os.path.join if needed
from fungi_fortress.config_manager import PACKAGE_ROOT_DIR as CONFIG_MANAGER_PACKAGE_ROOT_DIR

# Define the package root relative to the tests directory for config loading
# This assumes tests/ is a sibling of fungi_fortress/
# and config_manager.py is inside fungi_fortress/
# The PACKAGE_ROOT_DIR in config_manager.py is os.path.dirname(os.path.abspath(__file__))
# So, when load_llm_config is called, it will look for llm_config.ini 
# in the same directory as config_manager.py.
# We need to patch os.path.join and open within the context of config_manager.

VALID_CONFIG_CONTENT = """
[LLM]
model_name = gpt-test
context_level = high
"""

PLACEHOLDER_API_KEY_CONTENT = """
[LLM]
api_key = YOUR_API_KEY_HERE
model_name = gpt-test
context_level = medium
"""

EMPTY_API_KEY_CONTENT = """
[LLM]
api_key =
model_name = gpt-test-2
context_level = low
"""

MISSING_API_KEY_CONTENT = """
[LLM]
model_name = gpt-test-3
context_level = high
"""

MISSING_MODEL_NAME_CONTENT = """
[LLM]
api_key = test_api_key_456
context_level = low
"""

INVALID_CONTEXT_LEVEL_CONTENT = """
[LLM]
api_key = test_api_key_789
model_name = gpt-test-invalid
context_level = super_high
"""

NO_LLM_SECTION_CONTENT = """
[General]
setting = value
"""

EMPTY_CONFIG_CONTENT = """
"""

@patch.dict(os.environ, {"XAI_API_KEY": "test_api_key_123"}, clear=False)
@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open', new_callable=mock_open, read_data=VALID_CONFIG_CONTENT)
def test_load_llm_config_success(mock_open_func, mock_os_path_join):
    mock_os_path_join.return_value = "mocked/path/to/llm_config.ini"
    # mock_open_func is the mock of the open function.
    # configparser will call open(), which returns a file handle mock.
    # This file handle mock is pre-configured by read_data.

    config = load_llm_config() # Uses DEFAULT_CONFIG_FILENAME

    # API key comes from env var, not config file (security design)
    # XAI_API_KEY for XAI provider
    assert config.api_key == "test_api_key_123"
    assert config.model_name == "gpt-test"
    assert config.context_level == "high"
    mock_os_path_join.assert_called_once_with(CONFIG_MANAGER_PACKAGE_ROOT_DIR, DEFAULT_CONFIG_FILENAME)
    mock_open_func.assert_called_once_with("mocked/path/to/llm_config.ini", 'r')

@patch('fungi_fortress.config_manager.os.path.exists')
@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open')
def test_load_llm_config_file_not_found(mock_file_open, mock_os_path_join, mock_os_path_exists):
    mock_config_path = "mocked/path/non_existent.ini"
    mock_example_path = "mocked/path/llm_config.ini.example"
    
    # Simulate behavior of os.path.join
    def join_side_effect(path, filename):
        if filename == "non_existent.ini":
            return mock_config_path
        elif filename == "llm_config.ini.example":
            return mock_example_path
        return os.path.join(path, filename) # Fallback for any other calls
        
    mock_os_path_join.side_effect = join_side_effect
    mock_file_open.side_effect = FileNotFoundError
    mock_os_path_exists.return_value = False # Assume example file also doesn't exist for this specific original test logic
    
    config = load_llm_config("non_existent.ini")
    assert config.api_key is None
    assert config.model_name == LLMConfig().model_name  # Expect default model name from LLMConfig
    assert config.context_level == "medium" # Default
    
    # Updated: we no longer look for example file
    expected_join_calls = [
        call(CONFIG_MANAGER_PACKAGE_ROOT_DIR, "non_existent.ini"),
    ]
    mock_os_path_join.assert_has_calls(expected_join_calls, any_order=False)

@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open', new_callable=mock_open, read_data=NO_LLM_SECTION_CONTENT)
def test_load_llm_config_no_llm_section(mock_open_func, mock_os_path_join):
    mock_os_path_join.return_value = "mocked/path/to/no_section_config.ini"

    config = load_llm_config("no_section_config.ini")
    assert config.api_key is None
    assert config.model_name == LLMConfig().model_name # Default XAI model
    assert config.context_level == "medium"
    mock_os_path_join.assert_called_once_with(CONFIG_MANAGER_PACKAGE_ROOT_DIR, "no_section_config.ini")
    mock_open_func.assert_called_once_with("mocked/path/to/no_section_config.ini", 'r')

@pytest.mark.parametrize("content, file_basename", [
    (PLACEHOLDER_API_KEY_CONTENT, "placeholder.ini"),
    (EMPTY_API_KEY_CONTENT, "empty_key.ini"),
    (MISSING_API_KEY_CONTENT, "missing_key.ini"),
])
@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open')
def test_load_llm_config_various_api_key_states(mock_open_call, mock_os_path_join, content, file_basename):
    """API keys come from env vars, not config file. Test that config loads successfully."""
    mock_os_path_join.return_value = f"mocked/path/to/{file_basename}"
    
    mock_file_handle = io.StringIO(content)
    mock_open_call.return_value.__enter__.return_value = mock_file_handle
    mock_open_call.return_value.__exit__.return_value = None

    config = load_llm_config(file_basename)
    # API key comes from env vars (will be None without env var set)
    assert config.api_key is None  # No env var set in this test
    assert config.is_real_api_key_present == False
    mock_os_path_join.assert_called_once_with(CONFIG_MANAGER_PACKAGE_ROOT_DIR, file_basename)

@patch.dict(os.environ, {"OPENAI_API_KEY": "test_api_key_456"}, clear=False)
@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open', new_callable=mock_open, read_data=MISSING_MODEL_NAME_CONTENT)
def test_load_llm_config_missing_model_name(mock_open_func, mock_os_path_join):
    """Config file has no model_name - should use default and get API key from env."""
    file_basename = "missing_model.ini"
    mock_os_path_join.return_value = f"mocked/path/to/{file_basename}"

    config = load_llm_config(file_basename)
    assert config.model_name == LLMConfig().model_name  # Default XAI model
    assert config.api_key is None  # No XAI_API_KEY in env
    mock_os_path_join.assert_called_once_with(CONFIG_MANAGER_PACKAGE_ROOT_DIR, file_basename)
    mock_open_func.assert_called_once_with(f"mocked/path/to/{file_basename}", 'r')

@pytest.mark.parametrize("content, file_basename, expected_level, expected_model", [
    (VALID_CONFIG_CONTENT, "valid.ini", "high", "gpt-test"),
    (INVALID_CONTEXT_LEVEL_CONTENT, "invalid_ctx.ini", "medium", "gpt-test-invalid"), # Default context_level
    (MISSING_MODEL_NAME_CONTENT, "missing_model_ctx.ini", "low", LLMConfig().model_name) # Default XAI model
])
@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open')
def test_load_llm_config_context_levels(mock_open_call, mock_os_path_join, content, file_basename, expected_level, expected_model):
    mock_os_path_join.return_value = f"mocked/path/to/{file_basename}"

    mock_file_handle = io.StringIO(content)
    mock_open_call.return_value.__enter__.return_value = mock_file_handle
    mock_open_call.return_value.__exit__.return_value = None

    config = load_llm_config(file_basename)
    assert config.context_level == expected_level
    assert config.model_name == expected_model
    mock_os_path_join.assert_called_once_with(CONFIG_MANAGER_PACKAGE_ROOT_DIR, file_basename)
    mock_open_call.assert_called_once_with(f"mocked/path/to/{file_basename}", 'r')

@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open', new_callable=mock_open, read_data=EMPTY_CONFIG_CONTENT)
def test_load_llm_config_empty_file(mock_open_func, mock_os_path_join):
    file_basename = "empty.ini"
    mock_os_path_join.return_value = f"mocked/path/to/{file_basename}"

    config = load_llm_config(file_basename)
    assert config.api_key is None
    assert config.model_name == LLMConfig().model_name # Default XAI model
    assert config.context_level == "medium"
    mock_os_path_join.assert_called_once_with(CONFIG_MANAGER_PACKAGE_ROOT_DIR, file_basename)

@patch('fungi_fortress.config_manager.logger')
@patch('fungi_fortress.config_manager.os.path.exists')
@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open')
def test_load_llm_config_logs_file_not_found(mock_file_open, mock_os_path_join, mock_os_path_exists, mock_logger):
    file_basename = "non_existent_log.ini"
    mock_config_path = f"mocked/path/{file_basename}"
    mock_example_path = f"mocked/path/llm_config.ini.example" # Standard example name

    def join_side_effect(path, filename):
        if filename == file_basename:
            return mock_config_path
        elif filename == "llm_config.ini.example":
            return mock_example_path
        return os.path.join(path, filename)

    mock_os_path_join.side_effect = join_side_effect
    mock_file_open.side_effect = FileNotFoundError
    # Simulate example file found to test the print path in config_manager
    mock_os_path_exists.return_value = True 

    load_llm_config(file_basename)

    # Updated: we no longer look for example file, just log and use defaults
    expected_join_calls = [
        call(CONFIG_MANAGER_PACKAGE_ROOT_DIR, file_basename),
    ]
    mock_os_path_join.assert_has_calls(expected_join_calls, any_order=False)
    mock_logger.info.assert_any_call(f"Configuration file '{mock_config_path}' not found.")

@patch('fungi_fortress.config_manager.logger')
@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open', new_callable=mock_open, read_data=NO_LLM_SECTION_CONTENT)
def test_load_llm_config_logs_no_section(mock_open_func, mock_os_path_join, mock_logger):
    file_basename = "no_section_log.ini"
    mock_os_path_join.return_value = f"mocked/path/to/{file_basename}"

    load_llm_config(file_basename)
    mock_logger.warning.assert_any_call(f"[LLM] section not found in 'mocked/path/to/{file_basename}'. Using defaults.")
    mock_open_func.assert_called_once_with(f"mocked/path/to/{file_basename}", 'r')

@patch('fungi_fortress.config_manager.logger')
@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open', new_callable=mock_open, read_data=PLACEHOLDER_API_KEY_CONTENT)
def test_load_llm_config_logs_placeholder_api_key(mock_open_func, mock_os_path_join, mock_logger):
    """API keys come from env vars, not config file, so no placeholder warning."""
    file_basename = "placeholder_log.ini"
    mock_os_path_join.return_value = f"mocked/path/to/{file_basename}"

    config = load_llm_config(file_basename)
    
    # API key comes from env vars (None without env var), not from config file
    assert config.api_key is None
    # No placeholder log message since we don't read api_key from file

@patch('fungi_fortress.config_manager.logger')
@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open', new_callable=mock_open, read_data=INVALID_CONTEXT_LEVEL_CONTENT)
def test_load_llm_config_logs_invalid_context_level(mock_open_func, mock_os_path_join, mock_logger):
    file_basename = "invalid_ctx_log.ini"
    mock_config_path = f"mocked/path/to/{file_basename}"
    mock_os_path_join.return_value = mock_config_path

    config = load_llm_config(file_basename)
    assert config.context_level == "medium"
    # Check that validation warned about invalid context_level
    warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
    assert any("context_level" in call and "super_high" in call for call in warning_calls)
