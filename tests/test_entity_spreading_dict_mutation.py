"""Test for dictionary mutation bug fix during entity spreading."""
import pytest
from unittest.mock import Mock, patch
from fungi_fortress.game_logic import GameLogic
from fungi_fortress.game_state import GameState
from fungi_fortress.characters import Dwarf, Oracle
from fungi_fortress.tiles import Tile, ENTITY_REGISTRY


def test_entity_spreading_no_dict_mutation():
    """
    Regression test for: "dictionary changed size during iteration" bug.
    
    Bug: In GameLogic.update(), when spreading stacked entities, the code
    iterated over occupied_positions.items() while simultaneously adding
    new entries to occupied_positions inside the loop. This caused a
    RuntimeError: dictionary changed size during iteration.
    
    Scenario: Multiple entities occupy the same position, triggering the
    spreading logic which tries to move them to adjacent walkable tiles.
    If those tiles are also occupied, the dict is mutated during iteration.
    
    Fix: Iterate over list(occupied_positions.items()) to create a snapshot.
    """
    # Create a minimal game state
    llm_config = Mock()
    game_state = GameState(llm_config=llm_config)
    game_logic = GameLogic(game_state)
    
    # Create a small walkable map (5x5 grass)
    grass = ENTITY_REGISTRY.get("grass")
    game_state.map = [[Tile(grass, x, y) for x in range(5)] for y in range(5)]
    
    # Place multiple entities at the same position to trigger spreading
    # This simulates what happens after Oracle dialog when dwarf moves
    dwarf1 = Dwarf(2, 2, 0)
    dwarf2 = Dwarf(2, 2, 1)  # Stacked at same position
    oracle = Oracle("Test Oracle", 2, 2)  # Also stacked
    
    game_state.dwarves = [dwarf1, dwarf2]
    game_state.characters = [oracle]
    game_state.animals = []
    
    # Mock out other game logic that we don't want to test
    with patch.object(game_logic, '_update_dwarf'):
        with patch('fungi_fortress.dwarf_mind.assign_work'):
            with patch('fungi_fortress.world_judge.note_arrivals'):
                with patch('fungi_fortress.game_logic.surface_mycelium'):
                    # This should not raise "dictionary changed size during iteration"
                    try:
                        game_logic.update()
                        success = True
                    except RuntimeError as e:
                        if "dictionary changed size during iteration" in str(e):
                            pytest.fail(f"Dictionary mutation bug not fixed: {e}")
                        raise
    
    # Verify entities were spread out (not all at same position anymore)
    positions = set()
    for entity in [dwarf1, dwarf2, oracle]:
        positions.add((entity.x, entity.y))
    
    # At least one entity should have been moved to a different position
    assert len(positions) > 1, "Entities should be spread out, not all at same position"


def test_entity_spreading_with_limited_space():
    """
    Test entity spreading when there's limited space available.
    
    This is an edge case where multiple entities are stacked but there
    aren't enough adjacent walkable tiles to spread them all out.
    """
    llm_config = Mock()
    game_state = GameState(llm_config=llm_config)
    game_logic = GameLogic(game_state)
    
    # Create a map with a small walkable area (3x3 with walls around)
    grass = ENTITY_REGISTRY.get("grass")
    wall = ENTITY_REGISTRY.get("stone_wall")
    
    game_state.map = [
        [Tile(wall, x, 0) for x in range(5)],
        [Tile(wall, 0, 1), Tile(grass, 1, 1), Tile(grass, 2, 1), Tile(grass, 3, 1), Tile(wall, 4, 1)],
        [Tile(wall, 0, 2), Tile(grass, 1, 2), Tile(grass, 2, 2), Tile(grass, 3, 2), Tile(wall, 4, 2)],
        [Tile(wall, 0, 3), Tile(grass, 1, 3), Tile(grass, 2, 3), Tile(grass, 3, 3), Tile(wall, 4, 3)],
        [Tile(wall, x, 4) for x in range(5)],
    ]
    
    # Stack many entities at center
    dwarves = [Dwarf(2, 2, i) for i in range(5)]
    game_state.dwarves = dwarves
    game_state.characters = []
    game_state.animals = []
    
    with patch.object(game_logic, '_update_dwarf'):
        with patch('fungi_fortress.dwarf_mind.assign_work'):
            with patch('fungi_fortress.world_judge.note_arrivals'):
                with patch('fungi_fortress.game_logic.surface_mycelium'):
                    # Should not crash even with limited space
                    game_logic.update()
    
    # Some spreading should have occurred
    positions = [(d.x, d.y) for d in dwarves]
    unique_positions = set(positions)
    assert len(unique_positions) >= 2, "At least some entities should have spread out"
