#!/usr/bin/env python3
"""
Security tests for Fungi Fortress LLM integration.

These tests ensure that:
1. No API keys are exposed in source files
2. Environment variable loading works correctly
3. No API keys leak into logs or debug output
4. API keys are never shown in repr
"""

import pytest
import os
from unittest.mock import patch
import sys
import re

# Add the parent directory to the path to import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fungi_fortress.config_manager import LLMConfig


class TestAPIKeySecurity:
    """Test that API keys are never exposed in files or logs."""
    
    def test_no_api_keys_in_source_files(self):
        """Scan source files for accidentally committed API keys."""
        source_files = [
            "fungi_fortress/config_manager.py",
            "fungi_fortress/app.py",
            "fungi_fortress/game_state.py",
            "fungi_fortress/llm_interface.py"
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


class TestEnvironmentVariableLoading:
    """Test that environment variable loading works correctly and securely."""
    
    def test_from_env_with_xai_api_key_present(self):
        """Test XAI API key loading from environment when present."""
        test_key = "xai-test-key-12345"
        with patch.dict(os.environ, {'XAI_API_KEY': test_key}, clear=True):
            config = LLMConfig.from_env()
            assert config.api_key == test_key
            assert config.is_real_api_key_present
    
    def test_from_env_with_xai_api_key_missing(self):
        """Test behavior when XAI_API_KEY environment variable is missing."""
        with patch.dict(os.environ, {}, clear=True):
            config = LLMConfig.from_env()
            assert config.api_key is None
            assert not config.is_real_api_key_present
    
    def test_api_key_not_in_repr(self):
        """Test that API keys are never shown in repr to prevent log leaks."""
        test_api_key = "xai-secret-key-should-not-appear-in-repr"
        config = LLMConfig(api_key=test_api_key)
        
        repr_str = repr(config)
        assert test_api_key not in repr_str, f"API key found in repr: {repr_str}"
        # Verify repr doesn't include api_key field (it's redacted with repr=False)
        assert "api_key" not in repr_str or "***" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
