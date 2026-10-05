"""Tests for Oracle LLM integration with unified client."""

import pytest
from unittest.mock import Mock

from fungi_fortress import llm_client, llm_oracle
from fungi_fortress.llm_client import LLMClient
from fungi_fortress.config_manager import LLMConfig


class TestOracleMessageBuilding:
    """Tests for Oracle message construction."""
    
    def test_build_basic_messages(self):
        """Test building basic Oracle messages."""
        messages = llm_oracle.build_oracle_messages(
            oracle_name="Test Oracle",
            player_query="What is my destiny?",
            game_context={"tick": 100, "depth": 1},
            history=[],
        )
        
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        
        # System message should mention Oracle's role
        assert "Test Oracle" in messages[0]["content"]
        assert "wise" in messages[0]["content"].lower()
        
        # User message should include query
        assert "What is my destiny?" in messages[1]["content"]
        assert "Tick: 100" in messages[1]["content"]
        assert "Depth: 1" in messages[1]["content"]
    
    def test_build_messages_with_mission(self):
        """Test messages include mission context."""
        messages = llm_oracle.build_oracle_messages(
            oracle_name="Test Oracle",
            player_query="Help me",
            game_context={
                "tick": 200,
                "depth": 2,
                "mission": {"description": "Gather 10 fungi"}
            },
            history=[],
        )
        
        user_content = messages[1]["content"]
        assert "Mission: Gather 10 fungi" in user_content
    
    def test_build_messages_with_resources(self):
        """Test messages include resource context."""
        messages = llm_oracle.build_oracle_messages(
            oracle_name="Test Oracle",
            player_query="Help me",
            game_context={
                "tick": 200,
                "depth": 2,
                "resources": {"gold": 50, "fungi": 3}
            },
            history=[],
        )
        
        user_content = messages[1]["content"]
        assert "Resources:" in user_content
        assert "gold" in user_content
        assert "fungi" in user_content
    
    def test_build_messages_with_history(self):
        """Test messages include conversation history (already trimmed by caller)."""
        # Pass only last 3 exchanges (trimming is done by caller in llm_interface.py)
        history = [
            {"player": "What now?", "oracle": "Seek the grove"},
            {"player": "Where?", "oracle": "To the east"},
            {"player": "Thanks", "oracle": "Go with wisdom"},
        ]
        
        messages = llm_oracle.build_oracle_messages(
            oracle_name="Test Oracle",
            player_query="Continue",
            game_context={"tick": 100, "depth": 1},
            history=history,
        )
        
        user_content = messages[1]["content"]
        
        # Should include all provided exchanges
        assert "Seek the grove" in user_content
        assert "Where?" in user_content
        assert "Go with wisdom" in user_content


class TestOracleQueryNonStreaming:
    """Tests for non-streaming Oracle queries."""
    
    def test_query_oracle_mock(self):
        """Test querying Oracle with mock provider."""
        client = LLMClient(LLMConfig(), use_mock=True)
        
        response = llm_oracle.query_oracle(
            client=client,
            oracle_name="Test Oracle",
            player_query="Hello",
            game_context={"tick": 100, "depth": 1},
            history=[],
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        # Mock should give greeting response
        assert "greet" in response.lower() or "mycelial" in response.lower()
    
    def test_query_oracle_different_queries(self):
        """Test Oracle gives appropriate responses to different queries."""
        client = LLMClient(LLMConfig(), use_mock=True)
        game_context = {"tick": 100, "depth": 1}
        
        # Test quest query
        quest_response = llm_oracle.query_oracle(
            client=client,
            oracle_name="Test Oracle",
            player_query="What is my quest?",
            game_context=game_context,
            history=[],
        )
        assert "path" in quest_response.lower() or "quest" in quest_response.lower()
        
        # Test fungi query
        fungi_response = llm_oracle.query_oracle(
            client=client,
            oracle_name="Test Oracle",
            player_query="Tell me about the fungi",
            game_context=game_context,
            history=[],
        )
        assert "fungi" in fungi_response.lower()
    
    def test_query_oracle_with_max_tokens(self):
        """Test querying Oracle with max_tokens parameter."""
        client = LLMClient(LLMConfig(), use_mock=True)
        
        response = llm_oracle.query_oracle(
            client=client,
            oracle_name="Test Oracle",
            player_query="Hello",
            game_context={"tick": 100, "depth": 1},
            history=[],
            max_tokens=50,
        )
        
        # Should still work (mock doesn't enforce token limits strictly)
        assert isinstance(response, str)
        assert len(response) > 0


class TestOracleQueryStreaming:
    """Tests for streaming Oracle queries."""
    
    def test_query_oracle_streaming_mock(self):
        """Test streaming query with mock provider."""
        client = LLMClient(LLMConfig(), use_mock=True)
        
        chunks = list(llm_oracle.query_oracle_streaming(
            client=client,
            oracle_name="Test Oracle",
            player_query="Hello",
            game_context={"tick": 100, "depth": 1},
            history=[],
        ))
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)
        
        # Reassemble response
        full_response = "".join(chunks)
        assert len(full_response) > 0
        assert "greet" in full_response.lower() or "mycelial" in full_response.lower()
    
    def test_streaming_multiple_chunks(self):
        """Test streaming yields multiple chunks."""
        client = LLMClient(LLMConfig(), use_mock=True)
        
        chunks = list(llm_oracle.query_oracle_streaming(
            client=client,
            oracle_name="Test Oracle",
            player_query="Tell me a long story",
            game_context={"tick": 100, "depth": 1},
            history=[],
        ))
        
        # Mock provider should yield multiple chunks
        assert len(chunks) > 1
    
    def test_streaming_with_error(self):
        """Test streaming handles errors gracefully."""
        # Create a mock client that raises an error
        mock_client = Mock(spec=LLMClient)
        mock_client.is_mock.return_value = False
        mock_client.chat_stream.side_effect = llm_client.TimeoutError("Test timeout")
        
        with pytest.raises(llm_client.TimeoutError):
            list(llm_oracle.query_oracle_streaming(
                client=mock_client,
                oracle_name="Test Oracle",
                player_query="Hello",
                game_context={"tick": 100, "depth": 1},
                history=[],
            ))


class TestOracleIntegration:
    """Integration tests for Oracle functionality."""
    
    def test_oracle_conversation_flow(self):
        """Test a full Oracle conversation with history."""
        client = LLMClient(LLMConfig(), use_mock=True)
        game_context = {"tick": 100, "depth": 1}
        history = []
        
        # First query
        response1 = llm_oracle.query_oracle(
            client=client,
            oracle_name="Test Oracle",
            player_query="Hello Oracle",
            game_context=game_context,
            history=history,
        )
        
        history.append({"player": "Hello Oracle", "oracle": response1})
        
        # Second query with history
        response2 = llm_oracle.query_oracle(
            client=client,
            oracle_name="Test Oracle",
            player_query="What is my quest?",
            game_context=game_context,
            history=history,
        )
        
        assert response1 != response2  # Different queries should get different responses
        
        history.append({"player": "What is my quest?", "oracle": response2})
        
        # Third query with more history
        response3 = llm_oracle.query_oracle(
            client=client,
            oracle_name="Test Oracle",
            player_query="Help me find fungi",
            game_context=game_context,
            history=history,
        )
        
        assert isinstance(response3, str)
        assert len(response3) > 0
    
    def test_oracle_mock_indicator(self):
        """Test that code can detect when using mock provider."""
        client = LLMClient(LLMConfig(), use_mock=True)
        
        # Client should indicate it's using mock
        assert client.is_mock()
        
        # This allows game to show "offline mode" indicator


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
