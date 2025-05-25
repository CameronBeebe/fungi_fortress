#!/usr/bin/env python3
"""
Security tests for Fungi Fortress LLM integration.

These tests ensure that:
1. No API keys are exposed in configuration files
2. Environment variable loading works correctly
3. No API keys leak into logs or debug output
4. Configuration files don't contain sensitive data
"""

import pytest
import os
import tempfile
import configparser
from unittest.mock import patch, mock_open
import sys
import re

# Add the parent directory to the path to import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_manager import load_llm_config, get_api_key_from_env, LLMConfig


class TestAPIKeySecurity:
    """Test that API keys are never exposed in files or logs."""
    
    def test_no_api_keys_in_example_config(self):
        """Ensure the example config file contains no real API keys."""
        example_path = "llm_config.ini.example"
        if os.path.exists(example_path):
            with open(example_path, 'r') as f:
                content = f.read()
            
            # Check for common API key patterns
            api_key_patterns = [
                r'xai-[a-zA-Z0-9]{40,}',  # XAI API keys
                r'sk-[a-zA-Z0-9]{40,}',   # OpenAI API keys
                r'claude-[a-zA-Z0-9]{40,}',  # Anthropic API keys
                r'gsk_[a-zA-Z0-9]{40,}',  # Groq API keys
            ]
            
            for pattern in api_key_patterns:
                matches = re.findall(pattern, content)
                assert len(matches) == 0, f"Found potential API key in example config: {matches}"
    
    def test_no_api_keys_in_source_files(self):
        """Scan source files for accidentally committed API keys."""
        source_files = [
            "config_manager.py",
            "main.py", 
            "game_state.py",
            "llm_interface.py"
        ]
        
        api_key_patterns = [
            r'xai-[a-zA-Z0-9]{40,}',
            r'sk-[a-zA-Z0-9]{40,}', 
            r'claude-[a-zA-Z0-9]{40,}',
            r'gsk_[a-zA-Z0-9]{40,}',
        ]
        
        for file_path in source_files:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    content = f.read()
                
                for pattern in api_key_patterns:
                    matches = re.findall(pattern, content)
                    assert len(matches) == 0, f"Found potential API key in {file_path}: {matches}"
    
    def test_config_file_contains_no_api_keys(self):
        """Test that any existing config files don't contain API keys."""
        config_files = ["llm_config.ini"]
        
        for config_file in config_files:
            if os.path.exists(config_file):
                parser = configparser.ConfigParser()
                parser.read(config_file)
                
                # Check all sections and keys
                for section_name in parser.sections():
                    section = parser[section_name]
                    for key, value in section.items():
                        if 'api_key' in key.lower():
                            # API key should be empty, placeholder, or instruction
                            safe_values = [
                                "", 
                                "YOUR_API_KEY_HERE", 
                                "your-api-key-here",
                                "testkey123",
                                "None"
                            ]
                            assert value in safe_values, f"Found potential real API key in {config_file}: {key}={value}"


class TestEnvironmentVariableLoading:
    """Test that environment variable loading works correctly and securely."""
    
    def test_get_api_key_from_env_xai(self):
        """Test XAI API key loading from environment."""
        test_key = "xai-test-key-12345"
        with patch.dict(os.environ, {'XAI_API_KEY': test_key}):
            result = get_api_key_from_env("xai")
            assert result == test_key
    
    def test_get_api_key_from_env_openai(self):
        """Test OpenAI API key loading from environment."""
        test_key = "sk-test-key-12345"
        with patch.dict(os.environ, {'OPENAI_API_KEY': test_key}):
            result = get_api_key_from_env("openai")
            assert result == test_key
    
    def test_get_api_key_from_env_anthropic(self):
        """Test Anthropic API key loading from environment."""
        test_key = "claude-test-key-12345"
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': test_key}):
            result = get_api_key_from_env("anthropic")
            assert result == test_key
    
    def test_get_api_key_from_env_groq(self):
        """Test Groq API key loading from environment."""
        test_key = "gsk_test_key_12345"
        with patch.dict(os.environ, {'GROQ_API_KEY': test_key}):
            result = get_api_key_from_env("groq")
            assert result == test_key
    
    def test_get_api_key_from_env_missing(self):
        """Test behavior when environment variable is missing."""
        # Clear any existing API keys
        env_vars = ['XAI_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GROQ_API_KEY']
        with patch.dict(os.environ, {}, clear=True):
            result = get_api_key_from_env("xai")
            assert result is None
    
    def test_get_api_key_from_env_unknown_provider(self):
        """Test behavior with unknown provider."""
        result = get_api_key_from_env("unknown_provider")
        assert result is None


class TestConfigurationSecurity:
    """Test that configuration loading is secure and robust."""
    
    def test_load_llm_config_with_env_var(self):
        """Test loading config with API key from environment variable."""
        # Create a temporary config file
        config_content = """[LLM]
provider = xai
model_name = grok-3
context_level = medium
max_tokens = 500
"""
        
        test_api_key = "xai-test-secure-key-12345"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write(config_content)
            temp_config_path = f.name
        
        try:
            with patch.dict(os.environ, {'XAI_API_KEY': test_api_key}, clear=True):
                # Mock the config loading to use our temporary file
                with patch('config_manager.os.path.join') as mock_join:
                    mock_join.return_value = temp_config_path
                    config = load_llm_config()
                    
                    assert config.api_key == test_api_key
                    assert config.is_real_api_key_present == True
                    assert config.provider == "xai"
                    assert config.model_name == "grok-3"
        finally:
            os.unlink(temp_config_path)
    
    def test_load_llm_config_no_env_var(self):
        """Test loading config without API key in environment."""
        config_content = """[LLM]
provider = openai
model_name = gpt-4o-mini
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write(config_content)
            temp_config_path = f.name
        
        try:
            # Clear environment variables
            with patch.dict(os.environ, {}, clear=True):
                # Mock the config loading to use our temporary file
                with patch('config_manager.os.path.join') as mock_join:
                    mock_join.return_value = temp_config_path
                    config = load_llm_config()
                    
                    assert config.api_key is None
                    assert config.is_real_api_key_present == False
                    assert config.provider == "openai"
        finally:
            os.unlink(temp_config_path)
    
    def test_config_never_logs_api_keys(self):
        """Test that API keys are never logged in debug output."""
        test_api_key = "xai-secret-key-should-not-appear-in-logs"
        
        with patch.dict(os.environ, {'XAI_API_KEY': test_api_key}):
            with patch('config_manager.logger') as mock_logger:
                get_api_key_from_env("xai")
                
                # Check all logging calls
                for call in mock_logger.info.call_args_list:
                    args = call[0]
                    for arg in args:
                        assert test_api_key not in str(arg), f"API key found in log message: {arg}"


class TestConfigurationRobustness:
    """Test that the configuration system is robust and user-friendly."""
    
    def test_auto_provider_detection(self):
        """Test automatic provider detection from model names."""
        test_cases = [
            ("grok-3", "xai"),
            ("gpt-4o", "openai"),
            ("claude-3-5-sonnet", "anthropic"),
            ("llama-3.1-8b-instant", "groq"),
        ]
        
        for model_name, expected_provider in test_cases:
            config_content = f"""[LLM]
provider = auto
model_name = {model_name}
"""
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
                f.write(config_content)
                temp_config_path = f.name
            
            try:
                # Set appropriate API key
                env_var = {
                    "xai": "XAI_API_KEY",
                    "openai": "OPENAI_API_KEY", 
                    "anthropic": "ANTHROPIC_API_KEY",
                    "groq": "GROQ_API_KEY"
                }[expected_provider]
                
                with patch.dict(os.environ, {env_var: "test-key"}, clear=True):
                    # Mock the config loading to use our temporary file
                    with patch('config_manager.os.path.join') as mock_join:
                        mock_join.return_value = temp_config_path
                        config = load_llm_config()
                        
                        assert config.model_name == model_name
                        assert config.api_key == "test-key"
                        assert config.is_real_api_key_present == True
            finally:
                os.unlink(temp_config_path)
    
    def test_config_validation(self):
        """Test that configuration validation works correctly."""
        config = LLMConfig(
            api_key="test-key",
            max_tokens=5000,  # Too high
            timeout_seconds=200,  # Too high
            daily_request_limit=-1  # Invalid
        )
        
        # Validation should fix these values
        assert config.max_tokens == 500  # Should be clamped
        assert config.timeout_seconds == 30  # Should be clamped
        assert config.daily_request_limit == 100  # Should be fixed


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 