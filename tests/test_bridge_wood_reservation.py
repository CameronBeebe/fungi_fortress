"""Test bridge building wood reservation system."""
import pytest
from fungi_fortress.characters import Dwarf, Task
from fungi_fortress.tiles import Tile, ENTITY_REGISTRY
from fungi_fortress.game_state import GameState
from fungi_fortress.game_logic import GameLogic, BRIDGE_WOOD_COST
from fungi_fortress.task_manager import TaskManager
from fungi_fortress.config_manager import LLMConfig
from fungi_fortress.inventory import Inventory


@pytest.fixture(autouse=True)
def reset_test_state():
    """Reset any shared state before each test."""
    yield
    # Cleanup after test if needed


def test_reservation_computed_from_queued_tasks():
    """Test that reserved wood is computed from actual queued tasks."""
    # Create a minimal real GameState
    llm_config = LLMConfig()
    game = GameState(llm_config)
    
    # Set wood to 10
    game.inventory.resources["wood"] = 10
    
    # No tasks, no reservation
    assert game.get_reserved_wood() == 0
    assert game.get_available_wood() == 10
    
    # Add a bridge task
    task1 = Task(0, 0, "build_bridge", 1, 0)
    game.task_manager.add_task(task1)
    
    assert game.get_reserved_wood() == BRIDGE_WOOD_COST
    assert game.get_available_wood() == 10 - BRIDGE_WOOD_COST
    
    # Add another bridge task
    task2 = Task(0, 0, "build_bridge", 2, 0)
    game.task_manager.add_task(task2)
    
    assert game.get_reserved_wood() == 2 * BRIDGE_WOOD_COST
    assert game.get_available_wood() == 10 - 2 * BRIDGE_WOOD_COST


def test_reservation_released_when_task_removed():
    """Test that reservation is released automatically when task is removed."""
    llm_config = LLMConfig()
    game = GameState(llm_config)
    game.inventory.resources["wood"] = 10
    
    # Add two bridge tasks
    task1 = Task(0, 0, "build_bridge", 1, 0)
    task2 = Task(0, 0, "build_bridge", 2, 0)
    game.task_manager.add_task(task1)
    game.task_manager.add_task(task2)
    
    assert game.get_reserved_wood() == 2 * BRIDGE_WOOD_COST
    
    # Remove one task (simulating player cancel or task system drop)
    game.task_manager.remove_task(task1)
    
    # Reservation should be automatically released
    assert game.get_reserved_wood() == 1 * BRIDGE_WOOD_COST
    assert game.get_available_wood() == 10 - BRIDGE_WOOD_COST


def test_reservation_includes_assigned_tasks():
    """Test that wood reserved includes tasks assigned to dwarves."""
    llm_config = LLMConfig()
    game = GameState(llm_config)
    game.inventory.resources["wood"] = 10
    
    # Add a task to queue
    task1 = Task(0, 0, "build_bridge", 1, 0)
    game.task_manager.add_task(task1)
    
    # Assign a different task to a dwarf
    task2 = Task(0, 0, "build_bridge", 2, 0)
    if game.dwarves:
        game.dwarves[0].task = task2
    
    # Should count both queued and assigned
    expected = BRIDGE_WOOD_COST  # task1 in queue
    if game.dwarves:
        expected += BRIDGE_WOOD_COST  # task2 assigned to dwarf
    
    assert game.get_reserved_wood() == expected


def test_non_bridge_tasks_dont_reserve_wood():
    """Test that non-bridge tasks don't affect wood reservation."""
    llm_config = LLMConfig()
    game = GameState(llm_config)
    game.inventory.resources["wood"] = 10
    
    # Add non-bridge tasks
    game.task_manager.add_task(Task(0, 0, "mine", 1, 0))
    game.task_manager.add_task(Task(0, 0, "chop", 2, 0))
    
    # Should not reserve any wood
    assert game.get_reserved_wood() == 0
    assert game.get_available_wood() == 10


def test_input_handler_b_key_refuses_unaffordable_bridge():
    """Test that pressing 'b' with insufficient wood shows proper message."""
    from fungi_fortress.input_handler import InputHandler
    
    llm_config = LLMConfig()
    game = GameState(llm_config)
    
    # Set up a simple map with water
    grass = ENTITY_REGISTRY.get("grass")
    water = ENTITY_REGISTRY.get("water")
    game.map = [
        [Tile(grass, 0, 0), Tile(water, 1, 0), Tile(grass, 2, 0)]
    ]
    
    # Set wood to 0 (can't afford any bridges)
    game.inventory.resources["wood"] = 0
    
    # Position dwarf and cursor
    dwarf = game.dwarves[0] if game.dwarves else Dwarf(0, 0, 0)
    if not game.dwarves:
        game.dwarves = [dwarf]
    dwarf.x, dwarf.y = 0, 0
    game.cursor_x, game.cursor_y = 1, 0  # Cursor on water
    
    # Create input handler and press 'b'
    handler = InputHandler(game)
    handler.handle_input(ord('b'))
    
    # Should not queue the task
    bridge_tasks = [t for t in game.task_manager.tasks if t.type == "build_bridge"]
    assert len(bridge_tasks) == 0, "Should not queue bridge with no wood"
    
    # Should show message about insufficient wood
    debug_messages = " ".join(game.debug_log)
    assert "cannot queue bridge" in debug_messages.lower(), "Should show 'cannot queue bridge' message"
    assert "need" in debug_messages.lower() and "wood" in debug_messages.lower(), "Should explain wood needed"


def test_input_handler_b_key_queues_affordable_bridge():
    """Test that pressing 'b' with sufficient wood queues the bridge."""
    from fungi_fortress.input_handler import InputHandler
    
    llm_config = LLMConfig()
    game = GameState(llm_config)
    
    # Set up a simple map with water
    grass = ENTITY_REGISTRY.get("grass")
    water = ENTITY_REGISTRY.get("water")
    game.map = [
        [Tile(grass, 0, 0), Tile(water, 1, 0), Tile(grass, 2, 0)]
    ]
    
    # Set wood to 5 (can afford bridges)
    game.inventory.resources["wood"] = 5
    
    # Position dwarf and cursor
    dwarf = game.dwarves[0] if game.dwarves else Dwarf(0, 0, 0)
    if not game.dwarves:
        game.dwarves = [dwarf]
    dwarf.x, dwarf.y = 0, 0
    game.cursor_x, game.cursor_y = 1, 0  # Cursor on water
    
    # Create input handler and press 'b'
    handler = InputHandler(game)
    handler.handle_input(ord('b'))
    
    # Should queue the task
    bridge_tasks = [t for t in game.task_manager.tasks if t.type == "build_bridge"]
    assert len(bridge_tasks) == 1, "Should queue one bridge task"
    
    # Should reserve wood
    assert game.get_reserved_wood() == BRIDGE_WOOD_COST, f"Should reserve {BRIDGE_WOOD_COST} wood"
    assert game.get_available_wood() == 5 - BRIDGE_WOOD_COST, "Available wood should be reduced"



def test_dependent_segments_cancelled_on_failure():
    """Test that dependent bridge segments are cancelled when a bridge fails."""
    # Use real GameState with simple map
    llm_config = LLMConfig()
    game = GameState(llm_config)
    game.inventory.resources["wood"] = 5
    
    # Create a simple map: Grass | Water | Water | Grass
    from fungi_fortress.entities import GameEntity
    grass = ENTITY_REGISTRY.get("grass")
    water = ENTITY_REGISTRY.get("water")
    game.map = [
        [Tile(grass, 0, 0), Tile(water, 1, 0), Tile(water, 2, 0), Tile(grass, 3, 0)]
    ]
    
    dwarf = game.dwarves[0] if game.dwarves else Dwarf(0, 0, 0)
    if not game.dwarves:
        game.dwarves = [dwarf]
    dwarf.x, dwarf.y = 0, 0
    
    # Add tasks for both bridges
    task1 = Task(0, 0, "build_bridge", 1, 0)  # First bridge
    task2 = Task(1, 0, "build_bridge", 2, 0)  # Second bridge (depends on first)
    
    game.task_manager.add_task(task1)
    game.task_manager.add_task(task2)
    
    assert game.get_reserved_wood() == 2 * BRIDGE_WOOD_COST
    
    # Create game logic and simulate first bridge failure
    logic = GameLogic(game)
    logic._handle_bridge_failure((1, 0), "test failure")
    
    # The second bridge task should be cancelled because it's unreachable without the first
    remaining_tasks = [t for t in game.task_manager.tasks if (t.resource_x, t.resource_y) == (2, 0)]
    assert len(remaining_tasks) == 0, "Dependent task at (2,0) should be cancelled"
    
    # Reservation should be released automatically
    assert game.get_reserved_wood() < 2 * BRIDGE_WOOD_COST, "Some reservations should be released"
    
    # Check debug message
    assert "Cancelled" in " ".join(game.debug_log), "Should report cancelled dependent"


def test_independent_bridges_not_cancelled():
    """Test that independent (reachable) bridges are not cancelled when one fails."""
    llm_config = LLMConfig()
    game = GameState(llm_config)
    game.inventory.resources["wood"] = 5
    
    # Map with two rows to allow independent paths
    grass = ENTITY_REGISTRY.get("grass")
    water = ENTITY_REGISTRY.get("water")
    game.map = [
        [Tile(grass, 0, 0), Tile(water, 1, 0), Tile(grass, 2, 0), Tile(grass, 3, 0), Tile(grass, 4, 0)],
        [Tile(grass, 0, 1), Tile(grass, 1, 1), Tile(grass, 2, 1), Tile(water, 3, 1), Tile(grass, 4, 1)]
    ]
    
    dwarf = game.dwarves[0] if game.dwarves else Dwarf(0, 0, 0)
    if not game.dwarves:
        game.dwarves = [dwarf]
    dwarf.x, dwarf.y = 0, 0
    
    # Add tasks for both bridges (at different locations with independent paths)
    task1 = Task(0, 0, "build_bridge", 1, 0)  # First bridge at (1,0)
    task2 = Task(2, 1, "build_bridge", 3, 1)  # Second bridge at (3,1) - reachable via grass path
    
    game.task_manager.add_task(task1)
    game.task_manager.add_task(task2)
    
    # Create game logic and simulate first bridge failure
    logic = GameLogic(game)
    logic._handle_bridge_failure((1, 0), "test failure")
    
    # Check that the second bridge task still exists
    remaining_task_positions = [(t.resource_x, t.resource_y) for t in game.task_manager.tasks]
    assert (3, 1) in remaining_task_positions, f"Independent task at (3,1) should remain. Got: {remaining_task_positions}"


def test_bridge_completion_with_game_logic():
    """Integration test: bridge completes successfully."""
    llm_config = LLMConfig()
    game = GameState(llm_config)
    game.inventory.resources["wood"] = 5
    
    # Simple map
    grass = ENTITY_REGISTRY.get("grass")
    water = ENTITY_REGISTRY.get("water")
    game.map = [
        [Tile(grass, 0, 0), Tile(water, 1, 0), Tile(grass, 2, 0)]
    ]
    
    dwarf = game.dwarves[0] if game.dwarves else Dwarf(0, 0, 0)
    if not game.dwarves:
        game.dwarves = [dwarf]
    dwarf.x, dwarf.y = 0, 0
    bridge_pos = (1, 0)
    
    # Add task to queue
    task = Task(0, 0, "build_bridge", 1, 0)
    game.task_manager.add_task(task)
    initial_reserved = game.get_reserved_wood()
    
    # Assign task to dwarf and complete it
    game.task_manager.remove_task(task)
    dwarf.task = task
    dwarf.state = "building_bridge"
    
    # Complete the bridge
    logic = GameLogic(game)
    tile_dwarf_is_on = game.get_tile(0, 0)
    logic._complete_build_bridge(dwarf, tile_dwarf_is_on)
    
    # Check results
    assert game.inventory.resources["wood"] == 5 - BRIDGE_WOOD_COST, "Wood should be deducted"
    assert game.get_tile(1, 0).entity.name == "Bridge", "Bridge should be built"
    
    # Clear dwarf task (as would happen in real game)
    dwarf.task = None
    
    # Reservation should be released
    assert game.get_reserved_wood() == 0, "Reservation should be released"


def test_bridge_failure_insufficient_wood():
    """Integration test: bridge fails when wood runs out."""
    llm_config = LLMConfig()
    game = GameState(llm_config)
    game.inventory.resources["wood"] = 1
    
    # Simple map
    grass = ENTITY_REGISTRY.get("grass")
    water = ENTITY_REGISTRY.get("water")
    game.map = [
        [Tile(grass, 0, 0), Tile(water, 1, 0), Tile(water, 2, 0), Tile(grass, 3, 0)]
    ]
    
    dwarf = game.dwarves[0] if game.dwarves else Dwarf(0, 0, 0)
    if not game.dwarves:
        game.dwarves = [dwarf]
    dwarf.x, dwarf.y = 0, 0
    
    # Queue two bridges
    task1 = Task(0, 0, "build_bridge", 1, 0)
    task2 = Task(1, 0, "build_bridge", 2, 0)
    game.task_manager.add_task(task1)
    game.task_manager.add_task(task2)
    
    # Build first bridge successfully
    game.task_manager.remove_task(task1)
    dwarf.task = task1
    logic = GameLogic(game)
    logic._complete_build_bridge(dwarf, game.get_tile(0, 0))
    
    # Verify first bridge was built and wood deducted
    assert game.get_tile(1, 0).entity.name == "Bridge", "First bridge should be built"
    assert game.inventory.resources["wood"] == 0, "Wood should be spent"
    
    # Clear task (as would happen in real game)
    dwarf.task = None
    
    # Now try to build second bridge (wood runs out)
    game.task_manager.remove_task(task2)
    dwarf.task = task2
    dwarf.x, dwarf.y = 1, 0  # Dwarf moves to stand on the first bridge
    
    # Building second bridge should fail
    logic._complete_build_bridge(dwarf, game.get_tile(1, 0))
    
    # Second bridge should not be built
    assert game.get_tile(2, 0).entity.name == "Water", "Second bridge should not be built"
    
    # Should report insufficient wood
    assert "insufficient wood" in " ".join(game.debug_log).lower(), "Should report insufficient wood"


def test_assigned_task_cancelled_when_unreachable():
    """Test that bridge tasks assigned to dwarves are also cancelled when they become unreachable."""
    llm_config = LLMConfig()
    game = GameState(llm_config)
    game.inventory.resources["wood"] = 5
    
    # Simple map: Grass | Water | Water | Grass
    grass = ENTITY_REGISTRY.get("grass")
    water = ENTITY_REGISTRY.get("water")
    game.map = [
        [Tile(grass, 0, 0), Tile(water, 1, 0), Tile(water, 2, 0), Tile(grass, 3, 0)]
    ]
    
    dwarf = game.dwarves[0] if game.dwarves else Dwarf(0, 0, 0)
    if not game.dwarves:
        game.dwarves = [dwarf]
    dwarf.x, dwarf.y = 0, 0
    
    # Assign second bridge to dwarf (task2 depends on task1)
    task2 = Task(1, 0, "build_bridge", 2, 0)
    dwarf.task = task2
    
    # Task should reserve wood
    assert game.get_reserved_wood() == BRIDGE_WOOD_COST
    
    # Simulate first bridge (1,0) failure - this makes the second bridge (2,0) unreachable
    logic = GameLogic(game)
    logic._handle_bridge_failure((1, 0), "test failure")
    
    # Assigned task should be cancelled
    assert dwarf.task is None, "Dwarf's assigned task should be cleared"
    assert dwarf.state == "idle", "Dwarf should be idle after task cancellation"
    
    # Reservation should be released
    assert game.get_reserved_wood() == 0, "All reservations should be released"


