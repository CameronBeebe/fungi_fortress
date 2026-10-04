"""Test configuration and fixtures for fungi_fortress tests.

This module provides pytest configuration and shared fixtures to ensure
test isolation from the developer's real environment.
"""

import pytest


@pytest.fixture(autouse=True)
def isolate_from_real_env(monkeypatch):
    """Remove real environment variables and config paths to prevent live API calls.
    
    This autouse fixture ensures tests never see the developer's real API keys
    or make live API calls, even when XAI_API_KEY or other credentials are
    exported in the developer's shell.
    
    Applied automatically to all tests.
    """
    # Remove API keys that config_manager and other modules read
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    
    # Remove any FUNGI_* environment overrides that might affect LLM config
    monkeypatch.delenv("FUNGI_LOG_DIR", raising=False)
