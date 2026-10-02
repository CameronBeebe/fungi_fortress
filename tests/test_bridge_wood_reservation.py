"""Test bridge building wood reservation system."""
import pytest
from fungi_fortress.characters import Dwarf, Task
from fungi_fortress.tiles import Tile, ENTITY_REGISTRY
from fungi_fortress.game_state import GameState
from fungi_fortress.game_logic import GameLogic, BRIDGE_WOOD_COST
from fungi_fortress.task_manager import TaskManager
from fungi_fortress.config_manager import LLMConfig


class MockGameState:
    """Minimal game state for testing bridge wood reservation."""
    
    def __init__(self, map_data, starting_wood=10):
        """Create mock game state with given map.
        
        Args:
            map_data: 2D list of entity names ('grass', 'water', etc.)
            starting_wood: Initial wood in inventory
        """
        self.task_manager = TaskManager()
        self.tick = 0
        self.depth = 0
        self.paused = False
        self.debug_log = []
        
        # Build map using real entities from registry
        self.map = []
        for y, row in enumerate(map_data):
            map_row = []
            for x, entity_name in enumerate(row):
                entity = ENTITY_REGISTRY.get(entity_name.lower().replace(' ', '_'))
                if entity:
                    map_row.append(Tile(entity, x, y))
                else:
                    from fungi_fortress.entities import GameEntity
                    entity = GameEntity(entity_name, '.', 1, walkable=True)
                    map_row.append(Tile(entity, x, y))
            self.map.append(map_row)
        
        # Mock inventory
        from fungi_fortress.inventory import Inventory
        self.inventory = Inventory(starting_resources={"wood": starting_wood, "stone": 0, "food": 0, "gold": 0, "crystals": 0, "fungi": 0, "magic_fungi": 0})
        
        # Bridge wood reservations
        self.bridge_wood_reservations = {}
        
        # Dwarves
        self.dwarves = [Dwarf(0, 0, 0)]
    
    def get_tile(self, x, y):
        """Get tile at coordinates."""
        if 0 <= y < len(self.map) and 0 <= x < len(self.map[0]):
            return self.map[y][x]
        return None
    
    def add_debug_message(self, msg):
        """Add a debug message."""
        self.debug_log.append(msg)
    
    # Wood reservation methods (copied from real GameState)
    def get_reserved_wood(self):
        """Returns the total amount of wood reserved for pending bridge tasks."""
        return sum(self.bridge_wood_reservations.values())
    
    def get_available_wood(self):
        """Returns wood available after accounting for reservations."""
        total_wood = self.inventory.resources.get("wood", 0)
        reserved = self.get_reserved_wood()
        return total_wood - reserved
    
    def reserve_bridge_wood(self, bridge_pos, amount):
        """Reserves wood for a bridge at the given position."""
        if self.get_available_wood() >= amount:
            self.bridge_wood_reservations[bridge_pos] = amount
            return True
        return False
    
    def release_bridge_wood(self, bridge_pos):
        """Releases the wood reservation for a bridge at the given position."""
        if bridge_pos in self.bridge_wood_reservations:
            del self.bridge_wood_reservations[bridge_pos]


def test_queue_refused_when_unaffordable():
    """Test that bridge cannot be queued when wood is insufficient."""
    # Map: Grass | Water | Grass, with only 0 wood
    game = MockGameState([
        ['grass', 'water', 'grass']
    ], starting_wood=0)
    
    bridge_pos = (1, 0)
    
    # Try to reserve wood for bridge (should fail)
    result = game.reserve_bridge_wood(bridge_pos, BRIDGE_WOOD_COST)
    
    assert result is False, "Should not be able to reserve wood when none available"
    assert game.get_reserved_wood() == 0, "No wood should be reserved"
    assert len(game.bridge_wood_reservations) == 0, "No reservations should exist"


def test_queue_succeeds_with_sufficient_wood():
    """Test that bridge can be queued when wood is sufficient."""
    game = MockGameState([
        ['grass', 'water', 'grass']
    ], starting_wood=5)
    
    bridge_pos = (1, 0)
    
    # Reserve wood for bridge (should succeed)
    result = game.reserve_bridge_wood(bridge_pos, BRIDGE_WOOD_COST)
    
    assert result is True, "Should be able to reserve wood when available"
    assert game.get_reserved_wood() == BRIDGE_WOOD_COST, f"Should have {BRIDGE_WOOD_COST} wood reserved"
    assert game.get_available_wood() == 5 - BRIDGE_WOOD_COST, "Available wood should be reduced by reservation"


def test_multiple_bridges_reservation():
    """Test that multiple bridges reserve wood correctly."""
    game = MockGameState([
        ['grass', 'water', 'water', 'water', 'grass']
    ], starting_wood=3)
    
    # Reserve wood for first bridge
    assert game.reserve_bridge_wood((1, 0), BRIDGE_WOOD_COST) is True
    assert game.get_reserved_wood() == 1
    assert game.get_available_wood() == 2
    
    # Reserve wood for second bridge
    assert game.reserve_bridge_wood((2, 0), BRIDGE_WOOD_COST) is True
    assert game.get_reserved_wood() == 2
    assert game.get_available_wood() == 1
    
    # Reserve wood for third bridge
    assert game.reserve_bridge_wood((3, 0), BRIDGE_WOOD_COST) is True
    assert game.get_reserved_wood() == 3
    assert game.get_available_wood() == 0
    
    # Try to reserve for fourth bridge (should fail)
    assert game.reserve_bridge_wood((4, 0), BRIDGE_WOOD_COST) is False
    assert game.get_reserved_wood() == 3, "Should still have 3 reserved"
    assert len(game.bridge_wood_reservations) == 3, "Should have exactly 3 reservations"


def test_reservation_released_on_completion():
    """Test that wood reservation is released when bridge completes successfully."""
    game = MockGameState([
        ['grass', 'water', 'grass']
    ], starting_wood=5)
    
    bridge_pos = (1, 0)
    
    # Reserve wood
    game.reserve_bridge_wood(bridge_pos, BRIDGE_WOOD_COST)
    assert game.get_reserved_wood() == BRIDGE_WOOD_COST
    
    # Simulate successful completion
    game.release_bridge_wood(bridge_pos)
    
    assert game.get_reserved_wood() == 0, "Reservation should be released"
    assert bridge_pos not in game.bridge_wood_reservations, "Bridge pos should not be in reservations"


def test_reservation_released_on_failure():
    """Test that wood reservation is released when bridge fails."""
    game = MockGameState([
        ['grass', 'water', 'grass']
    ], starting_wood=5)
    
    bridge_pos = (1, 0)
    
    # Reserve wood
    game.reserve_bridge_wood(bridge_pos, BRIDGE_WOOD_COST)
    assert game.get_reserved_wood() == BRIDGE_WOOD_COST
    
    # Simulate failure
    game.release_bridge_wood(bridge_pos)
    
    assert game.get_reserved_wood() == 0, "Reservation should be released on failure"
    assert bridge_pos not in game.bridge_wood_reservations


def test_dependent_segments_cancelled_on_failure():
    """Test that dependent bridge segments are cancelled when a bridge fails."""
    # Map: Grass | Water | Water | Grass
    # If bridge at (1,0) fails, bridge at (2,0) becomes unreachable
    game = MockGameState([
        ['grass', 'water', 'water', 'grass']
    ], starting_wood=5)
    
    dwarf = game.dwarves[0]
    dwarf.x, dwarf.y = 0, 0
    
    # Add tasks for both bridges
    task1 = Task(0, 0, "build_bridge", 1, 0)  # First bridge
    task2 = Task(1, 0, "build_bridge", 2, 0)  # Second bridge (depends on first)
    
    game.task_manager.add_task(task1)
    game.task_manager.add_task(task2)
    game.reserve_bridge_wood((1, 0), BRIDGE_WOOD_COST)
    game.reserve_bridge_wood((2, 0), BRIDGE_WOOD_COST)
    
    # Create game logic and simulate first bridge failure
    logic = GameLogic(game)
    logic._handle_bridge_failure((1, 0), "test failure")
    
    # Check that dependent task's reservation is released
    assert (2, 0) not in game.bridge_wood_reservations, "Dependent bridge reservation should be released"
    
    # The second bridge task should be cancelled because it's unreachable without the first
    remaining_tasks = [t for t in game.task_manager.tasks if (t.resource_x, t.resource_y) == (2, 0)]
    assert len(remaining_tasks) == 0, "Dependent task at (2,0) should be cancelled"
    
    # Check debug message
    assert "Cancelled" in " ".join(game.debug_log), "Should report cancelled dependent"


def test_independent_bridges_not_cancelled():
    """Test that independent (reachable) bridges are not cancelled when one fails."""
    # Map with two rows to allow independent paths
    # Row 0: Grass | Water | Grass | Grass | Grass
    # Row 1: Grass | Grass | Grass | Water | Grass
    # Dwarf at (0,0), bridge1 at (1,0), bridge2 at (3,1) - can reach via (0,0)->(0,1)->(3,1)
    game = MockGameState([
        ['grass', 'water', 'grass', 'grass', 'grass'],
        ['grass', 'grass', 'grass', 'water', 'grass']
    ], starting_wood=5)
    
    dwarf = game.dwarves[0]
    dwarf.x, dwarf.y = 0, 0
    
    # Add tasks for both bridges (at different locations with independent paths)
    task1 = Task(0, 0, "build_bridge", 1, 0)  # First bridge at (1,0)
    task2 = Task(2, 1, "build_bridge", 3, 1)  # Second bridge at (3,1) - reachable via grass path
    
    game.task_manager.add_task(task1)
    game.task_manager.add_task(task2)
    game.reserve_bridge_wood((1, 0), BRIDGE_WOOD_COST)
    game.reserve_bridge_wood((3, 1), BRIDGE_WOOD_COST)
    
    # Create game logic and simulate first bridge failure
    logic = GameLogic(game)
    logic._handle_bridge_failure((1, 0), "test failure")
    
    # Check that the second bridge task and reservation still exist
    remaining_task_positions = [(t.resource_x, t.resource_y) for t in game.task_manager.tasks]
    assert (3, 1) in remaining_task_positions, f"Independent task at (3,1) should remain. Got: {remaining_task_positions}"
    assert (3, 1) in game.bridge_wood_reservations, "Second bridge reservation should remain"


def test_bridge_completion_with_game_logic():
    """Integration test: bridge completes successfully and releases reservation."""
    game = MockGameState([
        ['grass', 'water', 'grass']
    ], starting_wood=5)
    
    dwarf = game.dwarves[0]
    dwarf.x, dwarf.y = 0, 0
    bridge_pos = (1, 0)
    
    # Reserve wood
    game.reserve_bridge_wood(bridge_pos, BRIDGE_WOOD_COST)
    initial_reserved = game.get_reserved_wood()
    
    # Create a bridge task for the dwarf
    dwarf.task = Task(0, 0, "build_bridge", 1, 0)
    dwarf.state = "building_bridge"
    
    # Create game logic and complete the bridge
    logic = GameLogic(game)
    tile_dwarf_is_on = game.get_tile(0, 0)
    
    # Complete the bridge
    logic._complete_build_bridge(dwarf, tile_dwarf_is_on)
    
    # Check results
    assert game.get_reserved_wood() == 0, "Reservation should be released"
    assert game.inventory.resources["wood"] == 5 - BRIDGE_WOOD_COST, "Wood should be deducted"
    assert game.get_tile(1, 0).entity.name == "Bridge", "Bridge should be built"


def test_bridge_failure_insufficient_wood():
    """Integration test: bridge fails when wood runs out, and dependent segments are cancelled."""
    # Start with just enough wood for one bridge
    game = MockGameState([
        ['grass', 'water', 'water', 'grass']
    ], starting_wood=1)
    
    dwarf = game.dwarves[0]
    dwarf.x, dwarf.y = 0, 0
    
    # Reserve wood for two bridges (simulating what would happen when they're queued)
    game.reserve_bridge_wood((1, 0), BRIDGE_WOOD_COST)
    game.reserve_bridge_wood((2, 0), BRIDGE_WOOD_COST)
    
    task1 = Task(0, 0, "build_bridge", 1, 0)
    task2 = Task(1, 0, "build_bridge", 2, 0)
    game.task_manager.add_task(task1)
    game.task_manager.add_task(task2)
    
    # Simulate dwarf working on first bridge
    # Remove task1 from queue (as would happen when assigned)
    game.task_manager.remove_task(task1)
    dwarf.task = task1
    
    # Build first bridge successfully
    logic = GameLogic(game)
    logic._complete_build_bridge(dwarf, game.get_tile(0, 0))
    
    # Verify first bridge was built and wood deducted
    assert game.get_tile(1, 0).entity.name == "Bridge", "First bridge should be built"
    assert game.inventory.resources["wood"] == 0, "Wood should be spent"
    
    # Now try to build second bridge (wood runs out)
    # Remove task2 from queue (as would happen when assigned)
    game.task_manager.remove_task(task2)
    dwarf.task = task2
    dwarf.x, dwarf.y = 1, 0  # Dwarf moves to stand on the first bridge
    
    # Building second bridge should fail
    logic._complete_build_bridge(dwarf, game.get_tile(1, 0))
    
    # Second bridge should not be built
    assert game.get_tile(2, 0).entity.name == "Water", "Second bridge should not be built"
    
    # Should report insufficient wood
    assert "insufficient wood" in " ".join(game.debug_log).lower(), "Should report insufficient wood"
    
    # All reservations should be released
    assert game.get_reserved_wood() == 0, "All reservations should be released"
