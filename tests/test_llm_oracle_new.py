"""Tests for Oracle LLM integration with unified client."""

import pytest
from unittest.mock import Mock

from fungi_fortress import llm_client, llm_oracle
from fungi_fortress.llm_client import LLMClient
from fungi_fortress.world_seed import NpcReply


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
    """Tests for non-streaming Oracle queries with structured output."""
    
    def test_query_oracle_mock_returns_npc_reply(self):
        """Test querying Oracle with mock provider returns NpcReply."""
        client = LLMClient(use_mock=True)
        
        reply = llm_oracle.query_oracle(
            client=client,
            oracle_name="Test Oracle",
            player_query="Hello",
            game_context={"tick": 100, "depth": 1},
            history=[],
        )
        
        assert reply is not None
        assert isinstance(reply, NpcReply)
        assert isinstance(reply.narrative, str)
        assert len(reply.narrative) > 0
        # Mock should give greeting response
        assert "greet" in reply.narrative.lower() or "mycelial" in reply.narrative.lower()
        assert isinstance(reply.actions, list)
    
    def test_query_oracle_different_queries(self):
        """Test Oracle gives appropriate responses to different queries."""
        client = LLMClient(use_mock=True)
        game_context = {"tick": 100, "depth": 1}
        
        # Test quest query
        quest_reply = llm_oracle.query_oracle(
            client=client,
            oracle_name="Test Oracle",
            player_query="What is my quest?",
            game_context=game_context,
            history=[],
        )
        assert quest_reply is not None
        assert "path" in quest_reply.narrative.lower() or "quest" in quest_reply.narrative.lower()
        
        # Test fungi query
        fungi_reply = llm_oracle.query_oracle(
            client=client,
            oracle_name="Test Oracle",
            player_query="Tell me about the fungi",
            game_context=game_context,
            history=[],
        )
        assert fungi_reply is not None
        assert "fungi" in fungi_reply.narrative.lower()
    
    def test_query_oracle_with_max_tokens(self):
        """Test querying Oracle with max_tokens parameter."""
        client = LLMClient(use_mock=True)
        
        reply = llm_oracle.query_oracle(
            client=client,
            oracle_name="Test Oracle",
            player_query="Hello",
            game_context={"tick": 100, "depth": 1},
            history=[],
            max_tokens=50,
        )
        
        # Should still work (mock doesn't enforce token limits strictly)
        assert reply is not None
        assert isinstance(reply, NpcReply)
        assert len(reply.narrative) > 0


class TestOracleQueryStreaming:
    """Tests for streaming Oracle queries."""
    
    def test_query_oracle_streaming_mock(self):
        """Test streaming query with mock provider."""
        client = LLMClient(use_mock=True)
        
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
        client = LLMClient(use_mock=True)
        
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
        client = LLMClient(use_mock=True)
        game_context = {"tick": 100, "depth": 1}
        history = []
        
        # First query
        reply1 = llm_oracle.query_oracle(
            client=client,
            oracle_name="Test Oracle",
            player_query="Hello Oracle",
            game_context=game_context,
            history=history,
        )
        
        assert reply1 is not None
        history.append({"player": "Hello Oracle", "oracle": reply1.narrative})
        
        # Second query with history
        reply2 = llm_oracle.query_oracle(
            client=client,
            oracle_name="Test Oracle",
            player_query="What is my quest?",
            game_context=game_context,
            history=history,
        )
        
        assert reply2 is not None
        assert reply1.narrative != reply2.narrative  # Different queries should get different responses
        
        history.append({"player": "What is my quest?", "oracle": reply2.narrative})
        
        # Third query with more history
        reply3 = llm_oracle.query_oracle(
            client=client,
            oracle_name="Test Oracle",
            player_query="Help me find fungi",
            game_context=game_context,
            history=history,
        )
        
        assert reply3 is not None
        assert isinstance(reply3.narrative, str)
        assert len(reply3.narrative) > 0
    
    def test_oracle_mock_indicator(self):
        """Test that code can detect when using mock provider."""
        client = LLMClient(use_mock=True)
        
        # Client should indicate it's using mock
        assert client.is_mock()
        
        # This allows game to show "offline mode" indicator


class TestTypedLLMContract:
    """Tests for typed LLM contract (core contracts only)."""
    
    def test_npc_reply_schema_has_required_fields(self):
        """Test NpcReply schema has required fields and typed actions."""
        # Valid minimal reply
        reply = NpcReply(narrative="Test", actions=[])
        assert reply.narrative == "Test"
        assert reply.actions == []
        
        # Valid reply with add_message action
        from fungi_fortress.world_seed import AddMessageAction
        reply_with_action = NpcReply(
            narrative="The Oracle speaks",
            actions=[AddMessageAction(action_type="add_message", text="A message")]
        )
        assert len(reply_with_action.actions) == 1
        assert reply_with_action.actions[0].text == "A message"
    
    def test_npc_reply_actions_are_typed(self):
        """Test that NpcReply actions have proper typed fields, not empty object details."""
        from fungi_fortress.world_seed import SpawnCharacterAction
        
        # Spawn action with typed fields
        spawn_action = SpawnCharacterAction(
            action_type="spawn_character",
            type="Oracle",
            name="Mystic",
            x=10,
            y=20
        )
        
        reply = NpcReply(
            narrative="A figure appears",
            actions=[spawn_action]
        )
        
        # Verify action has actual typed fields, not empty 'details' object
        assert reply.actions[0].type == "Oracle"
        assert reply.actions[0].name == "Mystic"
        assert reply.actions[0].x == 10
        assert reply.actions[0].y == 20
    
    def test_mock_provider_returns_valid_npc_reply(self):
        """Test mock provider returns valid NpcReply that parses correctly."""
        client = LLMClient(use_mock=True)
        
        reply = llm_oracle.query_oracle(
            client=client,
            oracle_name="Test Oracle",
            player_query="Hello",
            game_context={"tick": 0, "depth": 1},
            history=[],
        )
        
        # Mock must return valid NpcReply
        assert reply is not None
        assert isinstance(reply, NpcReply)
        assert isinstance(reply.narrative, str)
        assert len(reply.narrative) > 0
        assert isinstance(reply.actions, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
