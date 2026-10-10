"""Tests for the unified LLM client."""

import pytest
from unittest.mock import Mock, patch

from fungi_fortress import llm_client
from fungi_fortress.llm_client import (
    LLMClient,
    MockLLMProvider,
    AuthenticationError,
    RateLimitError,
    TimeoutError as LLMTimeoutError,
    ConnectionError as LLMConnectionError,
    BadResponseError,
)
from fungi_fortress.config_manager import LLMConfig


class TestMockProvider:
    """Tests for the mock LLM provider."""
    
    def test_mock_greeting(self):
        """Test mock provider responds to greetings."""
        provider = MockLLMProvider()
        messages = [{"role": "user", "content": "Hello Oracle!"}]
        response = provider.chat(messages, max_tokens=100)
        
        assert "Greetings, seeker" in response
        assert "mycelial network" in response
    
    def test_mock_quest_query(self):
        """Test mock provider responds to quest queries."""
        provider = MockLLMProvider()
        messages = [{"role": "user", "content": "Tell me about my quest"}]
        response = provider.chat(messages, max_tokens=100)
        
        assert "path" in response.lower()
        assert "forest" in response.lower() or "groves" in response.lower()
    
    def test_mock_fungi_query(self):
        """Test mock provider responds to fungi queries."""
        provider = MockLLMProvider()
        messages = [{"role": "user", "content": "Where can I find magic fungi?"}]
        response = provider.chat(messages, max_tokens=100)
        
        assert "fungi" in response.lower()
        assert "magic" in response.lower() or "memories" in response.lower()
    
    def test_mock_streaming(self):
        """Test mock provider streaming."""
        provider = MockLLMProvider()
        messages = [{"role": "user", "content": "Help me"}]
        chunks = list(provider.chat_stream(messages, max_tokens=100))
        
        # Should yield multiple chunks
        assert len(chunks) > 1
        
        # Chunks should be strings
        assert all(isinstance(chunk, str) for chunk in chunks)
        
        # Reassembled response should be complete
        full_response = "".join(chunks)
        assert "network" in full_response.lower()
    
    def test_mock_deterministic(self):
        """Test mock provider is deterministic."""
        provider = MockLLMProvider()
        messages = [{"role": "user", "content": "Hello"}]
        
        response1 = provider.chat(messages, max_tokens=100)
        response2 = provider.chat(messages, max_tokens=100)
        
        assert response1 == response2
    
    def test_mock_default_response(self):
        """Test mock provider default response for unknown queries."""
        provider = MockLLMProvider()
        messages = [{"role": "user", "content": "xyzabc random nonsense"}]
        response = provider.chat(messages, max_tokens=100)
        
        assert "spores whisper" in response.lower() or "obscured" in response.lower()


class TestLLMClient:
    """Tests for the unified LLM client."""
    
    def test_client_with_no_config_uses_mock(self):
        """Test client with no API key uses mock provider."""
        config = LLMConfig()  # No API key
        client = LLMClient(config)
        assert client.is_mock()
    
    def test_client_with_invalid_key_uses_mock(self):
        """Test client with invalid API key uses mock provider."""
        config = LLMConfig(
            model_name="test-model",
            api_key="YOUR_API_KEY_HERE",
        )
        client = LLMClient(config)
        
        assert client.is_mock()
    
    def test_client_force_mock(self):
        """Test forcing mock provider even with valid config."""
        config = LLMConfig(
            model_name="test-model",
            api_key="real-looking-key",
        )
        client = LLMClient(config, use_mock=True)
        
        assert client.is_mock()
    
    def test_mock_client_chat(self):
        """Test mock client chat method."""
        client = LLMClient(LLMConfig(), use_mock=True)
        messages = [{"role": "user", "content": "Hello"}]
        
        response = client.chat(messages)
        
        assert isinstance(response, str)
        assert len(response) > 0
    
    def test_mock_client_chat_stream(self):
        """Test mock client streaming."""
        client = LLMClient(LLMConfig(), use_mock=True)
        messages = [{"role": "user", "content": "Hello"}]
        
        chunks = list(client.chat_stream(messages))
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)
    
    def test_client_with_valid_config_not_mock(self):
        """Test client with valid config is not mock."""
        config = LLMConfig(
            model_name="test-model",
            api_key="xai-real-key",
        )
        client = LLMClient(config)
        
        # Should not be mock (would try to use real API)
        assert not client.is_mock()
    
    @patch('fungi_fortress.llm_client.openai.OpenAI')
    def test_xai_provider_init_with_config(self, mock_openai_class):
        """Test that XAI provider builds OpenAI client correctly."""
        config = LLMConfig(
            model_name="test-model",
            api_key="test-key",
            max_retries=3,
            timeout_seconds=45
        )
        
        client = LLMClient(config)
        
        # Verify OpenAI client was created with correct parameters
        mock_openai_class.assert_called_once_with(
            api_key="test-key",
            base_url="https://api.x.ai/v1",
            timeout=45,
            max_retries=3
        )


class TestErrorMapping:
    """Tests for typed error mapping."""
    
    @patch('openai.OpenAI')
    def test_authentication_error(self, mock_openai_class):
        """Test authentication error mapping."""
        import openai as openai_lib
        
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = openai_lib.AuthenticationError(
            "Invalid API key",
            response=Mock(status_code=401),
            body=None
        )
        
        config = LLMConfig(
            model_name="test-model",
            api_key="invalid-key",
        )
        client = LLMClient(config)
        
        with pytest.raises(AuthenticationError):
            client.chat([{"role": "user", "content": "test"}])
    
    @patch('openai.OpenAI')
    def test_rate_limit_error(self, mock_openai_class):
        """Test rate limit error mapping."""
        import openai as openai_lib
        
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = openai_lib.RateLimitError(
            "Rate limit exceeded",
            response=Mock(status_code=429),
            body=None
        )
        
        config = LLMConfig(
            model_name="test-model",
            api_key="test-key",
        )
        client = LLMClient(config)
        
        with pytest.raises(RateLimitError):
            client.chat([{"role": "user", "content": "test"}])
    
    @patch('openai.OpenAI')
    def test_timeout_error(self, mock_openai_class):
        """Test timeout error mapping."""
        import openai as openai_lib
        
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = openai_lib.APITimeoutError(
            request=Mock()
        )
        
        config = LLMConfig(
            model_name="test-model",
            api_key="test-key",
        )
        client = LLMClient(config)
        
        with pytest.raises(LLMTimeoutError):
            client.chat([{"role": "user", "content": "test"}])
    
    @patch('openai.OpenAI')
    def test_connection_error(self, mock_openai_class):
        """Test connection error mapping."""
        import openai as openai_lib
        
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = openai_lib.APIConnectionError(
            request=Mock()
        )
        
        config = LLMConfig(
            model_name="test-model",
            api_key="test-key",
        )
        client = LLMClient(config)
        
        with pytest.raises(LLMConnectionError):
            client.chat([{"role": "user", "content": "test"}])


class TestClientFactory:
    """Tests for creating clients from config."""
    
    def test_create_client_with_no_key(self):
        """Test creates mock client with no API key."""
        config = LLMConfig(model_name="test-model")
        client = LLMClient(config)
        assert client.is_mock()
    
    def test_create_client_with_placeholder_key(self):
        """Test creates mock client with placeholder key."""
        config = LLMConfig(model_name="test-model", api_key="YOUR_API_KEY_HERE")
        client = LLMClient(config)
        assert client.is_mock()
    
    def test_create_client_with_xai_key(self):
        """Test creates XAI client with valid key."""
        config = LLMConfig(model_name="test-model", api_key="xai-test-key")
        client = LLMClient(config)
        assert not client.is_mock()


class TestUserMessages:
    """Tests for user-facing error messages."""
    
    def test_auth_error_message(self):
        """Test authentication error has user-friendly message."""
        error = AuthenticationError("Internal details")
        assert "Authentication failed" in error.user_message()
    
    def test_rate_limit_message(self):
        """Test rate limit error has user-friendly message."""
        error = RateLimitError("Internal details")
        assert "overwhelmed" in error.user_message() or "wait" in error.user_message().lower()
    
    def test_timeout_message(self):
        """Test timeout error has user-friendly message."""
        error = LLMTimeoutError("Internal details")
        assert "silence" in error.user_message().lower() or "faded" in error.user_message().lower()
    
    def test_connection_message(self):
        """Test connection error has user-friendly message."""
        error = LLMConnectionError("Internal details")
        assert "connection" in error.user_message().lower()
    
    def test_bad_response_message(self):
        """Test bad response error has user-friendly message."""
        error = BadResponseError("Internal details")
        assert "unclear" in error.user_message().lower() or "words" in error.user_message().lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
