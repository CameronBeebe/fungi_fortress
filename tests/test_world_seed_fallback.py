"""Test world seed fallback with placeholder key."""

import pytest
from fungi_fortress.world_seed import grow_world
from fungi_fortress.config_manager import LLMConfig
from fungi_fortress.game_state import GameState


def test_grow_world_placeholder_key_uses_fallback():
    """Test that grow_world falls back to prepared grove with placeholder key without raising."""
    # Create game with placeholder key (should use mock/fallback)
    config = LLMConfig(api_key="YOUR_API_KEY_HERE")
    game = GameState(llm_config=config)
    
    # Should not raise, should return fallback message
    result = grow_world(game, complete=None)
    
    # Should indicate fallback was used
    assert "prepared grove" in result.lower()
    # Game should have the prepared seed applied
    assert game.world_title is not None
    assert game.mission is not None
