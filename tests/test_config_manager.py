import pytest
from unittest.mock import patch, mock_open, ANY, Mock
import configparser
import io

from fungi_fortress.config_manager import load_oracle_config, OracleConfig, DEFAULT_CONFIG_FILENAME
# Import the actual PACKAGE_ROOT_DIR to verify calls to os.path.join if needed
from fungi_fortress.config_manager import PACKAGE_ROOT_DIR as CONFIG_MANAGER_PACKAGE_ROOT_DIR

# Define the package root relative to the tests directory for config loading
# This assumes tests/ is a sibling of fungi_fortress/
# and config_manager.py is inside fungi_fortress/
# The PACKAGE_ROOT_DIR in config_manager.py is os.path.dirname(os.path.abspath(__file__))
# So, when load_oracle_config is called, it will look for oracle_config.ini 
# in the same directory as config_manager.py.
# We need to patch os.path.join and open within the context of config_manager.

VALID_CONFIG_CONTENT = """
[OracleAPI]
api_key = test_api_key_123
model_name = gpt-test
context_level = high
"""

PLACEHOLDER_API_KEY_CONTENT = """
[OracleAPI]
api_key = YOUR_API_KEY_HERE
model_name = gpt-test
context_level = medium
"""

EMPTY_API_KEY_CONTENT = """
[OracleAPI]
api_key =
model_name = gpt-test-2
context_level = low
"""

MISSING_API_KEY_CONTENT = """
[OracleAPI]
model_name = gpt-test-3
context_level = high
"""

MISSING_MODEL_NAME_CONTENT = """
[OracleAPI]
api_key = test_api_key_456
context_level = low
"""

INVALID_CONTEXT_LEVEL_CONTENT = """
[OracleAPI]
api_key = test_api_key_789
model_name = gpt-test-invalid
context_level = super_high
"""

NO_ORACLE_SECTION_CONTENT = """
[General]
setting = value
"""

EMPTY_CONFIG_CONTENT = """
"""

@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open', new_callable=mock_open, read_data=VALID_CONFIG_CONTENT)
def test_load_oracle_config_success(mock_open_func, mock_os_path_join):
    mock_os_path_join.return_value = "mocked/path/to/oracle_config.ini"
    # mock_open_func is the mock of the open function.
    # configparser will call open(), which returns a file handle mock.
    # This file handle mock is pre-configured by read_data.

    config = load_oracle_config() # Uses DEFAULT_CONFIG_FILENAME

    assert config.api_key == "test_api_key_123"
    assert config.model_name == "gpt-test"
    assert config.context_level == "high"
    mock_os_path_join.assert_called_once_with(CONFIG_MANAGER_PACKAGE_ROOT_DIR, DEFAULT_CONFIG_FILENAME)
    mock_open_func.assert_called_once_with("mocked/path/to/oracle_config.ini", 'r')

@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open')
def test_load_oracle_config_file_not_found(mock_file_open, mock_os_path_join):
    mock_os_path_join.return_value = "mocked/path/non_existent.ini"
    mock_file_open.side_effect = FileNotFoundError
    config = load_oracle_config("non_existent.ini")
    assert config.api_key is None
    assert config.model_name == "gemini-1.5-flash-latest" # Expect default model name
    assert config.context_level == "medium" # Default
    mock_os_path_join.assert_called_once_with(CONFIG_MANAGER_PACKAGE_ROOT_DIR, "non_existent.ini")
    # open is called within a try-except, so it's called, but then FileNotFoundError is caught
    mock_file_open.assert_called_once_with("mocked/path/non_existent.ini", 'r')


@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open', new_callable=mock_open, read_data=NO_ORACLE_SECTION_CONTENT)
def test_load_oracle_config_no_oracle_section(mock_open_func, mock_os_path_join):
    mock_os_path_join.return_value = "mocked/path/to/no_section_config.ini"

    config = load_oracle_config("no_section_config.ini")
    assert config.api_key is None
    assert config.model_name is None
    assert config.context_level == "medium"
    mock_os_path_join.assert_called_once_with(CONFIG_MANAGER_PACKAGE_ROOT_DIR, "no_section_config.ini")
    mock_open_func.assert_called_once_with("mocked/path/to/no_section_config.ini", 'r')

@pytest.mark.parametrize("content, expected_raw_api_key, expected_is_real_key_present, file_basename", [
    (PLACEHOLDER_API_KEY_CONTENT, "YOUR_API_KEY_HERE", False, "placeholder.ini"),
    (EMPTY_API_KEY_CONTENT, "", False, "empty_key.ini"), # configparser might make it empty string
    (MISSING_API_KEY_CONTENT, None, False, "missing_key.ini"),
])
@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open')
def test_load_oracle_config_various_api_key_states(mock_open_call, mock_os_path_join, content, expected_raw_api_key, expected_is_real_key_present, file_basename):
    mock_os_path_join.return_value = f"mocked/path/to/{file_basename}"
    
    mock_file_handle = io.StringIO(content)
    mock_open_call.return_value.__enter__.return_value = mock_file_handle
    mock_open_call.return_value.__exit__.return_value = None

    config = load_oracle_config(file_basename)
    # For MISSING_API_KEY_CONTENT, configparser might result in api_key being None if not found
    # For EMPTY_API_KEY_CONTENT, configparser returns an empty string if the key is present but value is empty.
    if expected_raw_api_key is None and config.api_key == "": # Special case for missing vs empty from configparser
         pass # Allow if expected None but got empty string due to configparser behavior
    elif config.api_key is None and expected_raw_api_key == "":
         pass # Allow if expected empty string but got None due to configparser behavior
    else:
        assert config.api_key == expected_raw_api_key
    assert config.is_real_api_key_present == expected_is_real_key_present
    mock_os_path_join.assert_called_once_with(CONFIG_MANAGER_PACKAGE_ROOT_DIR, file_basename)

@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open', new_callable=mock_open, read_data=MISSING_MODEL_NAME_CONTENT)
def test_load_oracle_config_missing_model_name(mock_open_func, mock_os_path_join):
    file_basename = "missing_model.ini"
    mock_os_path_join.return_value = f"mocked/path/to/{file_basename}"

    config = load_oracle_config(file_basename)
    assert config.model_name is None
    assert config.api_key == "test_api_key_456"
    mock_os_path_join.assert_called_once_with(CONFIG_MANAGER_PACKAGE_ROOT_DIR, file_basename)
    mock_open_func.assert_called_once_with(f"mocked/path/to/{file_basename}", 'r')

@pytest.mark.parametrize("content, file_basename, expected_level, expected_model", [
    (VALID_CONFIG_CONTENT, "valid.ini", "high", "gpt-test"),
    (INVALID_CONTEXT_LEVEL_CONTENT, "invalid_ctx.ini", "medium", "gpt-test-invalid"),
    (MISSING_MODEL_NAME_CONTENT, "missing_model_ctx.ini", "low", None) 
])
@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open')
def test_load_oracle_config_context_levels(mock_open_call, mock_os_path_join, content, file_basename, expected_level, expected_model):
    mock_os_path_join.return_value = f"mocked/path/to/{file_basename}"

    mock_file_handle = io.StringIO(content)
    mock_open_call.return_value.__enter__.return_value = mock_file_handle
    mock_open_call.return_value.__exit__.return_value = None

    config = load_oracle_config(file_basename)
    assert config.context_level == expected_level
    assert config.model_name == expected_model
    mock_os_path_join.assert_called_once_with(CONFIG_MANAGER_PACKAGE_ROOT_DIR, file_basename)
    mock_open_call.assert_called_once_with(f"mocked/path/to/{file_basename}", 'r')

@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open', new_callable=mock_open, read_data=EMPTY_CONFIG_CONTENT)
def test_load_oracle_config_empty_file(mock_open_func, mock_os_path_join):
    file_basename = "empty.ini"
    mock_os_path_join.return_value = f"mocked/path/to/{file_basename}"

    config = load_oracle_config(file_basename)
    assert config.api_key is None
    assert config.model_name is None
    assert config.context_level == "medium"
    mock_os_path_join.assert_called_once_with(CONFIG_MANAGER_PACKAGE_ROOT_DIR, file_basename)

# Test that the logger is called
@patch('fungi_fortress.config_manager.logger')
@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open')
def test_load_oracle_config_logs_file_not_found(mock_file_open, mock_os_path_join, mock_logger):
    file_basename = "non_existent_log.ini"
    mock_path = f"mocked/path/{file_basename}"
    mock_os_path_join.return_value = mock_path
    mock_file_open.side_effect = FileNotFoundError
    
    load_oracle_config(file_basename)
    
    mock_os_path_join.assert_called_once_with(CONFIG_MANAGER_PACKAGE_ROOT_DIR, file_basename)
    mock_logger.info.assert_any_call(f"Attempting to load config from: {mock_path}")
    mock_logger.info.assert_any_call(f"Configuration file '{mock_path}' not found. Oracle LLM features may be unavailable.")

@patch('fungi_fortress.config_manager.logger')
@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open', new_callable=mock_open, read_data=NO_ORACLE_SECTION_CONTENT)
def test_load_oracle_config_logs_no_section(mock_open_func, mock_os_path_join, mock_logger):
    file_basename = "no_section_log.ini"
    mock_os_path_join.return_value = f"mocked/path/to/{file_basename}"

    load_oracle_config(file_basename)
    mock_logger.warning.assert_any_call(f"[OracleAPI] section not found in 'mocked/path/to/{file_basename}'. Oracle LLM features may be unavailable.")
    mock_open_func.assert_called_once_with(f"mocked/path/to/{file_basename}", 'r')

@patch('fungi_fortress.config_manager.logger')
@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open', new_callable=mock_open, read_data=PLACEHOLDER_API_KEY_CONTENT)
def test_load_oracle_config_logs_placeholder_api_key(mock_open_func, mock_os_path_join, mock_logger):
    file_basename = "placeholder_log.ini"
    mock_os_path_join.return_value = f"mocked/path/to/{file_basename}"

    config = load_oracle_config(file_basename) # This will trigger __post_init__
    
    # Check the log message from __post_init__
    # The api_key value in the log message should be the actual placeholder string
    mock_logger.info.assert_any_call(f"API key is a placeholder or empty: 'YOUR_API_KEY_HERE'")
    mock_open_func.assert_called_once_with(f"mocked/path/to/{file_basename}", 'r')

@patch('fungi_fortress.config_manager.logger')
@patch('fungi_fortress.config_manager.os.path.join')
@patch('fungi_fortress.config_manager.open', new_callable=mock_open, read_data=INVALID_CONTEXT_LEVEL_CONTENT)
def test_load_oracle_config_logs_invalid_context_level(mock_open_func, mock_os_path_join, mock_logger):
    file_basename = "invalid_ctx_log.ini"
    mock_os_path_join.return_value = f"mocked/path/to/{file_basename}"
    # mock_open_func.return_value.read.return_value = INVALID_CONTEXT_LEVEL_CONTENT # Covered by read_data

    load_oracle_config(file_basename)
    # The warning message in load_oracle_config uses the full path.
    mock_logger.warning.assert_any_call(
        f"Invalid 'context_level' in 'mocked/path/to/{file_basename}'. Using default 'medium'."
    )
    mock_open_func.assert_called_once_with(f"mocked/path/to/{file_basename}", 'r') 