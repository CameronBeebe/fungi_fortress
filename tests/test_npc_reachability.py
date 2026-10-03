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
    from fungi_fortress.map_generation import generate_map, generate_mycelial_network
    from fungi_fortress.world_seed import grow_world
    from fungi_fortress.config_manager import LLMConfig
    from fungi_fortress.utils import a_star
    from fungi_fortress.constants import MAP_WIDTH, MAP_HEIGHT
    from fungi_fortress.tiles import ENTITY_REGISTRY
    from fungi_fortress.characters import Dwarf
    
    # Test with several different seeds
    test_seeds = [42, 123, 456, 789, 2024]
    
    for seed_value in test_seeds:
        random.seed(seed_value)
        
        # Simulate the actual startup sequence from app.py
        llm_config = LLMConfig()
        game_state = GameState(llm_config=llm_config)
        
        # Regenerate map (as app.py does)
        map_width, map_height = MAP_WIDTH, MAP_HEIGHT
        initial_map, nexus_site, magic_fungi = generate_map(
            map_width, map_height, game_state.depth, game_state.mission
        )
        game_state.map = initial_map
        game_state.main_map = initial_map
        game_state.nexus_site = nexus_site
        game_state.magic_fungi_locations = magic_fungi
        
        # Generate mycelial network
        if nexus_site:
            game_state.mycelial_network = generate_mycelial_network(
                initial_map, nexus_site, magic_fungi if magic_fungi else []
            )
            game_state.network_distances = game_state.calculate_network_distances()
        else:
            game_state.mycelial_network = {}
            game_state.network_distances = {}
        
        # Find spawn point and spawn dwarf (as app.py does)
        spawn_x, spawn_y = None, None
        grass_entity = ENTITY_REGISTRY.get("grass")
        if grass_entity:
            for y_coord in range(len(game_state.map)):
                for x_coord in range(len(game_state.map[0])):
                    if game_state.map[y_coord][x_coord].entity == grass_entity:
                        spawn_x, spawn_y = x_coord, y_coord
                        break
                if spawn_x is not None:
                    break
        
        if spawn_x is None:
            spawn_x, spawn_y = map_width // 2, map_height // 2
        
        game_state.dwarves = [Dwarf(spawn_x, spawn_y, 0)]
        game_state.cursor_x, game_state.cursor_y = spawn_x, spawn_y
        
        # Grow world (spawns NPCs including Oracle)
        world_note = grow_world(game_state)
        
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
    from fungi_fortress.map_generation import generate_map, generate_mycelial_network
    from fungi_fortress.world_seed import grow_world
    from fungi_fortress.config_manager import LLMConfig
    from fungi_fortress.constants import MAP_WIDTH, MAP_HEIGHT
    from fungi_fortress.tiles import ENTITY_REGISTRY
    from fungi_fortress.characters import Dwarf, Oracle
    
    random.seed(42)
    
    # Simulate startup
    llm_config = LLMConfig()
    game_state = GameState(llm_config=llm_config)
    
    # Regenerate map
    map_width, map_height = MAP_WIDTH, MAP_HEIGHT
    initial_map, nexus_site, magic_fungi = generate_map(
        map_width, map_height, game_state.depth, game_state.mission
    )
    game_state.map = initial_map
    game_state.main_map = initial_map
    game_state.nexus_site = nexus_site
    game_state.magic_fungi_locations = magic_fungi
    
    if nexus_site:
        game_state.mycelial_network = generate_mycelial_network(
            initial_map, nexus_site, magic_fungi if magic_fungi else []
        )
        game_state.network_distances = game_state.calculate_network_distances()
    
    # Spawn dwarf
    spawn_x, spawn_y = None, None
    grass_entity = ENTITY_REGISTRY.get("grass")
    if grass_entity:
        for y_coord in range(len(game_state.map)):
            for x_coord in range(len(game_state.map[0])):
                if game_state.map[y_coord][x_coord].entity == grass_entity:
                    spawn_x, spawn_y = x_coord, y_coord
                    break
            if spawn_x is not None:
                break
    
    if spawn_x is None:
        spawn_x, spawn_y = map_width // 2, map_height // 2
    
    game_state.dwarves = [Dwarf(spawn_x, spawn_y, 0)]
    
    # Grow world
    grow_world(game_state)
    
    # Check for Oracle presence
    oracle_npcs = [npc for npc in game_state.characters if isinstance(npc, Oracle)]
    assert len(oracle_npcs) > 0, \
        "No Oracle NPC found after startup (expected at least one Oracle instance)"
    
    print(f"✓ Oracle '{oracle_npcs[0].name}' present at ({oracle_npcs[0].x}, {oracle_npcs[0].y})")


if __name__ == "__main__":
    test_npcs_reachable_from_dwarf()
    test_oracle_specifically_present()
    print("\n✓✓ All NPC reachability tests passed!")
