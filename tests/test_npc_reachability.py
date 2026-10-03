#!/usr/bin/env python3
"""Test that all NPCs (including Oracle) are placed on walkable, reachable tiles after startup."""

import pytest
import random
from unittest.mock import MagicMock, patch


def test_npcs_reachable_from_dwarf():
    """Test that all NPCs are on walkable tiles reachable from the dwarf.
    
    This regression test ensures that the Oracle and other NPCs are not stranded
    on unwalkable tiles or cut off from the player after map generation.
    
    Tests multiple random seeds to catch intermittent placement failures.
    """
    from fungi_fortress.game_state import GameState
    from fungi_fortress.app import initialize_new_game
    from fungi_fortress.config_manager import LLMConfig
    from fungi_fortress.utils import a_star
    
    # Test with several different seeds
    test_seeds = [42, 123, 456, 789, 2024]
    
    for seed_value in test_seeds:
        random.seed(seed_value)
        
        # Use the real startup sequence from app.py
        llm_config = LLMConfig()
        game_state = GameState(llm_config=llm_config)
        initialize_new_game(game_state)  # Canonical new-game setup
        
        # Now verify all NPCs are reachable
        dwarf_pos = (game_state.dwarves[0].x, game_state.dwarves[0].y)
        
        assert len(game_state.characters) > 0, \
            f"Seed {seed_value}: No NPCs spawned (expected Oracle and others)"
        
        for npc in game_state.characters:
            npc_pos = (npc.x, npc.y)
            
            # Check that NPC is on a walkable tile
            tile = game_state.get_tile(npc.x, npc.y)
            assert tile is not None, \
                f"Seed {seed_value}: NPC '{npc.name}' at ({npc.x}, {npc.y}) is out of bounds"
            assert tile.walkable, \
                f"Seed {seed_value}: NPC '{npc.name}' at ({npc.x}, {npc.y}) is on unwalkable tile '{tile.entity.name}'"
            
            # Check that NPC is reachable from dwarf via pathfinding
            path = a_star(game_state.map, dwarf_pos, npc_pos)
            assert path is not None, \
                f"Seed {seed_value}: NPC '{npc.name}' at ({npc.x}, {npc.y}) is not reachable from dwarf at {dwarf_pos}"
            
        print(f"✓ Seed {seed_value}: All {len(game_state.characters)} NPCs are walkable and reachable")
    
    print(f"\n✓ All {len(test_seeds)} seeds passed: NPCs consistently placed on reachable tiles")


def test_oracle_specifically_present():
    """Test that an Oracle NPC is present after startup."""
    from fungi_fortress.game_state import GameState
    from fungi_fortress.app import initialize_new_game
    from fungi_fortress.config_manager import LLMConfig
    from fungi_fortress.characters import Oracle
    
    random.seed(42)
    
    # Use the real startup sequence
    llm_config = LLMConfig()
    game_state = GameState(llm_config=llm_config)
    initialize_new_game(game_state)
    
    # Check for Oracle presence
    oracle_npcs = [npc for npc in game_state.characters if isinstance(npc, Oracle)]
    assert len(oracle_npcs) > 0, \
        "No Oracle NPC found after startup (expected at least one Oracle instance)"
    
    oracle = oracle_npcs[0]
    # Verify Oracle preserves seed data
    assert hasattr(oracle, 'data'), "Oracle missing 'data' attribute"
    assert oracle.data.get('seed_id'), "Oracle missing 'seed_id' in data"
    assert oracle.data.get('kind') == 'revealed', "Oracle 'kind' should be 'revealed'"
    assert oracle.data.get('motive'), "Oracle missing 'motive' in data"
    
    print(f"✓ Oracle '{oracle.name}' present at ({oracle.x}, {oracle.y})")
    print(f"  Data preserved: seed_id={oracle.data.get('seed_id')}, kind={oracle.data.get('kind')}, motive='{oracle.data.get('motive')[:50]}...'")



if __name__ == "__main__":
    test_npcs_reachable_from_dwarf()
    test_oracle_specifically_present()
    print("\n✓✓ All NPC reachability tests passed!")
