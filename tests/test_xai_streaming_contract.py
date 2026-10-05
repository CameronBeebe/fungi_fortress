"""Test that chat_stream passes correct params to OpenAI client."""
from unittest.mock import Mock, MagicMock
from fungi_fortress.config_manager import LLMConfig
from fungi_fortress.llm_client import XAIProvider

def test_xai_provider_chat_stream_contract():
    """Test that chat_stream passes model/max_tokens/reasoning_effort/stream to client."""
    config = LLMConfig(
        api_key="test-key",
        model_name="test-model",
        max_tokens=750,
        reasoning_effort="medium",
        temperature=0.5
    )
    
    # Mock the OpenAI client that gets created in __init__
    mock_client = MagicMock()
    mock_stream = MagicMock()
    mock_client.chat.completions.create.return_value = mock_stream
    
    # Mock stream to return chunks
    mock_chunk = Mock()
    mock_chunk.choices = [Mock()]
    mock_chunk.choices[0].delta = Mock()
    mock_chunk.choices[0].delta.content = "test"
    mock_stream.__iter__ = Mock(return_value=iter([mock_chunk]))
    
    provider = XAIProvider(config)
    provider.client = mock_client  # Replace with our mock
    
    messages = [{"role": "user", "content": "test"}]
    list(provider.chat_stream(messages))  # Consume iterator
    
    # Verify the contract: model, max_tokens, reasoning_effort, stream all passed
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == "test-model"
    assert call_kwargs["max_tokens"] == 750
    assert call_kwargs["reasoning_effort"] == "medium"
    assert call_kwargs["stream"] is True
    assert call_kwargs["temperature"] == 0.5

if __name__ == "__main__":
    test_xai_provider_chat_stream_contract()
    print("✓ chat_stream contract test passed")
