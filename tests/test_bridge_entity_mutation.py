"""Test that bridge_stand doesn't mutate shared entities or cross separate water."""
import pytest
from fungi_fortress.characters import Dwarf, Task
from fungi_fortress.tiles import Tile, ENTITY_REGISTRY
from fungi_fortress.input_handler import bridge_stand


class MockTaskManager:
    def __init__(self):
        self.tasks = []


class MockGameState:
    def __init__(self, map_data):
        """Create mock game state with given map.
        
        Args:
            map_data: 2D list of entity names ('grass', 'water', etc.)
        """
        self.task_manager = MockTaskManager()
        
        # Build map using real entities from registry
        self.map = []
        for y, row in enumerate(map_data):
            map_row = []
            for x, entity_name in enumerate(row):
                entity = ENTITY_REGISTRY.get(entity_name.lower().replace(' ', '_'))
                if entity:
                    map_row.append(Tile(entity, x, y))
                else:
                    # Fallback for test
                    from fungi_fortress.entities import GameEntity
                    entity = GameEntity(entity_name, '.', 1, walkable=True)
                    map_row.append(Tile(entity, x, y))
            self.map.append(map_row)


def test_bridge_stand_does_not_mutate_shared_water_entity():
    """Bridge planning must not mutate the shared water entity in ENTITY_REGISTRY.
    
    Bug: All water tiles share the same GameEntity from ENTITY_REGISTRY.
    Setting tile.entity.walkable = True makes ALL water walkable, not just planned bridges.
    
    Fix: a_star() now accepts extra_walkable set instead of mutating entities.
    """
    # Get the shared water entity
    water_entity = ENTITY_REGISTRY.get("water")
    assert water_entity is not None
    assert water_entity.walkable is False, "Water should start non-walkable"
    
    # Create map: Grass | Water | Grass
    game = MockGameState([
        ['grass', 'water', 'grass']
    ])
    
    dwarf = Dwarf(0, 0, 0)
    
    # Plan a bridge at (1, 0)
    game.task_manager.tasks.append(Task(1, 0, "build_bridge", 1, 0))
    
    # Call bridge_stand
    stand = bridge_stand(game, dwarf, 2, 0)
    
    # Verify: Water entity in registry must still be non-walkable
    assert water_entity.walkable is False, "Shared water entity was mutated!"
    
    # Verify: Path should be found through the planned bridge
    assert stand == (1, 0), "Should find path through planned bridge"


def test_bridge_stand_separate_water_bodies_not_crossable():
    """Bridge on one water body must not let path cross a separate water body.
    
    Map layout:
    G W G W G  (G=grass, W=water)
    
    Dwarf at (0,0), wants to reach (4,0).
    Plan bridge at (1,0).
    Must NOT be able to cross the separate water at (3,0).
    """
    water_entity = ENTITY_REGISTRY.get("water")
    assert water_entity.walkable is False
    
    # Create map with two separate water bodies
    game = MockGameState([
        ['grass', 'water', 'grass', 'water', 'grass']
    ])
    
    dwarf = Dwarf(0, 0, 0)
    
    # Plan bridge only at (1, 0) - NOT at (3, 0)
    game.task_manager.tasks.append(Task(1, 0, "build_bridge", 1, 0))
    
    # Try to reach (4, 0) - should fail because water at (3,0) blocks it
    stand = bridge_stand(game, dwarf, 4, 0)
    
    # Verify: Cannot reach across unplanned water
    assert stand is None, "Should NOT be able to cross unplanned water at (3,0)"
    
    # Verify: Water entity still non-walkable
    assert water_entity.walkable is False, "Shared water entity was mutated!"
    
    # Now plan bridge at (3, 0) too
    game.task_manager.tasks.append(Task(3, 0, "build_bridge", 3, 0))
    
    # Should now find path
    stand = bridge_stand(game, dwarf, 4, 0)
    assert stand == (3, 0), "Should find path through both planned bridges"
    
    # Still verify entity not mutated
    assert water_entity.walkable is False
