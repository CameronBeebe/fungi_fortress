#!/usr/bin/env python3
"""Test that all NPCs are placed correctly on walkable tiles after startup."""

import pytest
import random
from unittest.mock import MagicMock, patch


def test_npcs_on_walkable_tiles():
    """Test that all NPCs are on walkable tiles of the final map.
    
    This regression test ensures that NPCs are placed on habitable terrain after
    the final map is generated (not on walls/water/unwalkable tiles).
    
    Tests multiple random seeds to catch intermittent placement failures.
    """
    from fungi_fortress.game_state import GameState
    from fungi_fortress.app import initialize_new_game
    from fungi_fortress.config_manager import LLMConfig
    
    # Test with several different seeds
    test_seeds = [42, 123, 456, 789, 2024]
    
    for seed_value in test_seeds:
        random.seed(seed_value)
        
        # Use the real startup sequence from app.py
        llm_config = LLMConfig()
        game_state = GameState(llm_config=llm_config)
        initialize_new_game(game_state)  # Canonical new-game setup
        
        # Verify all NPCs are on walkable tiles
        assert len(game_state.characters) > 0, \
            f"Seed {seed_value}: No NPCs spawned (expected Oracle and others)"
        
        for npc in game_state.characters:
            # Check that NPC is on a walkable tile of the final map
            tile = game_state.get_tile(npc.x, npc.y)
            assert tile is not None, \
                f"Seed {seed_value}: NPC '{npc.name}' at ({npc.x}, {npc.y}) is out of bounds"
            assert tile.walkable, \
                f"Seed {seed_value}: NPC '{npc.name}' at ({npc.x}, {npc.y}) is on unwalkable tile '{tile.entity.name}'"
            
        print(f"✓ Seed {seed_value}: All {len(game_state.characters)} NPCs are on walkable tiles")
    
    print(f"\n✓ All {len(test_seeds)} seeds passed: NPCs consistently placed on walkable tiles")


def test_npcs_spread_across_map():
    """Test that NPCs are spread across the map, not clustered in one corner.
    
    Ensures NPCs don't consistently end up in the same quadrant across all seeds.
    """
    from fungi_fortress.game_state import GameState
    from fungi_fortress.app import initialize_new_game
    from fungi_fortress.config_manager import LLMConfig
    from fungi_fortress.constants import MAP_WIDTH, MAP_HEIGHT
    
    # Test with several different seeds
    test_seeds = [42, 123, 456, 789, 2024, 111, 222, 333]
    
    seeds_with_clustering = 0
    
    for seed_value in test_seeds:
        random.seed(seed_value)
        
        llm_config = LLMConfig()
        game_state = GameState(llm_config=llm_config)
        initialize_new_game(game_state)
        
        if len(game_state.characters) < 2:
            continue  # Skip if not enough NPCs to check distribution
        
        # Check which quadrants NPCs are in
        mid_x, mid_y = MAP_WIDTH // 2, MAP_HEIGHT // 2
        quadrants = {
            'top_left': 0,
            'top_right': 0,
            'bottom_left': 0,
            'bottom_right': 0,
        }
        
        for npc in game_state.characters:
            if npc.x < mid_x and npc.y < mid_y:
                quadrants['top_left'] += 1
            elif npc.x >= mid_x and npc.y < mid_y:
                quadrants['top_right'] += 1
            elif npc.x < mid_x and npc.y >= mid_y:
                quadrants['bottom_left'] += 1
            else:
                quadrants['bottom_right'] += 1
        
        # Check if NPCs are all in the same quadrant
        max_in_one_quadrant = max(quadrants.values())
        total_npcs = len(game_state.characters)
        
        if max_in_one_quadrant == total_npcs:
            seeds_with_clustering += 1
            print(f"  Seed {seed_value}: All {total_npcs} NPCs in one quadrant: {quadrants}")
        else:
            print(f"✓ Seed {seed_value}: NPCs spread across quadrants: {quadrants}")
    
    # NPCs should not cluster in the same quadrant for ALL seeds
    # Allow some clustering due to random chance, but not systematic
    assert seeds_with_clustering < len(test_seeds) // 2, \
        f"NPCs clustered in one quadrant for {seeds_with_clustering}/{len(test_seeds)} seeds (should be < {len(test_seeds)//2})"
    
    print(f"\n✓ Distribution test passed: NPCs spread across map ({seeds_with_clustering}/{len(test_seeds)} seeds had clustering)")


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
    test_npcs_on_walkable_tiles()
    test_npcs_spread_across_map()
    test_oracle_specifically_present()
    print("\n✓✓ All NPC placement tests passed!")
