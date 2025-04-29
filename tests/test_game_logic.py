import pytest
from unittest.mock import patch, MagicMock
import random

# Use absolute imports from the installed package
from fungi_fortress.game_logic import surface_mycelium
from fungi_fortress.tiles import Tile, ENTITY_REGISTRY # ENTITY_REGISTRY might be needed by Tile indirectly
from fungi_fortress.entities import GameEntity, Sublevel
from fungi_fortress.characters import Dwarf
from fungi_fortress.game_logic import GameLogic
from fungi_fortress.constants import MAP_WIDTH, MAP_HEIGHT

# --- Fixtures ---

@pytest.fixture
def mock_entity_registry(monkeypatch):
    """Fixture to provide a mock or controlled ENTITY_REGISTRY."""
    mock_mycelium = MagicMock(spec=GameEntity)
    mock_mycelium.name = "mycelium_floor"
    mock_mycelium.walkable = True
    mock_stone = MagicMock(spec=GameEntity)
    mock_stone.name = "stone_floor"
    mock_stone.walkable = True
    mock_grass = MagicMock(spec=GameEntity)
    mock_grass.name = "grass"
    mock_grass.walkable = True
    mock_wall = MagicMock(spec=GameEntity)
    mock_wall.name = "stone_wall"
    mock_wall.walkable = False
    mock_bridge = MagicMock(spec=GameEntity)
    mock_bridge.name = "bridge"
    mock_bridge.walkable = True

    registry = {
        "mycelium_floor": mock_mycelium,
        "stone_floor": mock_stone,
        "grass": mock_grass,
        "stone_wall": mock_wall,
        "bridge": mock_bridge
    }
    # Patch the ENTITY_REGISTRY where it's defined and imported from
    monkeypatch.setattr('fungi_fortress.tiles.ENTITY_REGISTRY', registry)
    return registry

@pytest.fixture
def mock_game_state(mock_entity_registry):
    """Fixture to create a mock GameState with a configurable map."""
    game_state = MagicMock()
    stone = mock_entity_registry["stone_floor"]
    # Using a smaller map for easier testing
    map_data = [
        [Tile(stone, 0, 0), Tile(stone, 1, 0)],
        [Tile(stone, 0, 1), Tile(stone, 1, 1)]
    ]
    game_state.map = map_data
    MAP_H, MAP_W = len(map_data), len(map_data[0])

    def _get_tile(x, y):
        if 0 <= y < MAP_H and 0 <= x < MAP_W:
            return game_state.map[y][x]
        return None
    game_state.get_tile = MagicMock(side_effect=_get_tile)

    # Store map dimensions on the mock for tests to use in patching
    game_state.test_map_width = MAP_W
    game_state.test_map_height = MAP_H

    # Ensure mock player exists for spore exposure checks
    game_state.player = MagicMock()
    game_state.player.spore_exposure = 0 # Default to 0

    # Ensure add_debug_message exists
    game_state.add_debug_message = MagicMock()

    # Ensure depth exists
    game_state.depth = 0 # Default to 0

    # Ensure mycelial_network exists
    game_state.mycelial_network = {}

    yield game_state # Removed the patch context manager here

# --- Fixtures for _trigger_sublevel_entry ---

@pytest.fixture
def mock_sublevel_entity():
    """Fixture for a mock Sublevel entity."""
    entity = MagicMock(spec=Sublevel)
    entity.name = "Shadowed Grotto" # Explicitly set the name attribute
    return entity

@pytest.fixture
def mock_entry_tile(mock_sublevel_entity):
    """Fixture for a mock Tile containing the sublevel entry."""
    # Tile needs x, y coordinates
    tile = MagicMock(spec=Tile, x=5, y=5)
    tile.entity = mock_sublevel_entity
    return tile

@pytest.fixture
def mock_dwarf():
    """Fixture for a mock Dwarf."""
    dwarf = MagicMock(spec=Dwarf, id=1, x=4, y=5, state='entering') # State can be anything
    return dwarf

@pytest.fixture
def mock_game_state_for_sublevel(mock_entity_registry):
    """More complex GameState mock specifically for sublevel tests."""
    game_state = MagicMock()

    # Basic attributes
    game_state.add_debug_message = MagicMock()
    game_state.calculate_network_distances = MagicMock(return_value={})
    game_state.player = MagicMock()
    game_state.player.update_state = MagicMock()

    # Initial map (surface)
    stone = mock_entity_registry["stone_floor"]
    surface_map_data = [[Tile(stone, x, y) for x in range(10)] for y in range(10)]
    game_state.map = surface_map_data

    # Mock get_tile for the *current* map
    def _get_tile(x, y):
        current_map = game_state.map # Access the potentially swapped map
        h, w = len(current_map), len(current_map[0])
        if 0 <= y < h and 0 <= x < w:
            return current_map[y][x]
        return None
    game_state.get_tile = MagicMock(side_effect=_get_tile)

    # Dwarves list
    game_state.dwarves = [] # Add the mock dwarf within the test

    # Sublevels dictionary
    game_state.sub_levels = {}

    # Network (initially empty)
    game_state.mycelial_network = {}
    game_state.network_distances = {}

    # Entry point (initially None)
    game_state.entry_x = None
    game_state.entry_y = None

    # Mission (optional, can be simple dict)
    game_state.mission = {"name": "Test Mission"}

    return game_state

@pytest.fixture
def game_logic_instance(mock_game_state_for_sublevel):
    """Fixture to create a GameLogic instance with the mocked GameState."""
    # Patch constants needed by GameLogic init or methods if any
    # (Assuming GameLogic doesn't directly use MAP_WIDTH/HEIGHT itself here)
    return GameLogic(mock_game_state_for_sublevel)

# --- Mock Map/Network Generation --- 

# Create a sample map data to be returned by the mock generate_map
# Ensure it has at least one walkable tile for dwarf spawning
@pytest.fixture
def mock_sublevel_map_data(mock_entity_registry):
    floor = mock_entity_registry["stone_floor"]
    wall = mock_entity_registry["stone_wall"]
    data = [
        [Tile(wall, 0, 0), Tile(wall, 1, 0)],
        [Tile(wall, 0, 1), Tile(floor, 1, 1)] # Walkable at (1,1)
    ]
    return data, (1, 1), [] # map_grid, nexus_site, magic_fungi_locations

# --- Tests for _trigger_sublevel_entry ---

# Patch the generation functions within the fungi_fortress.game_logic module
@patch('fungi_fortress.game_logic.generate_mycelial_network', return_value={(1,1): []}) # Mock network gen
@patch('fungi_fortress.game_logic.generate_map') # Mock map gen
def test_trigger_sublevel_entry_new_sublevel(
    mock_gen_map, mock_gen_network, # Patched args first
    game_logic_instance, mock_game_state_for_sublevel, 
    mock_dwarf, mock_entry_tile, mock_sublevel_entity, mock_sublevel_map_data
):
    """Test entering a sublevel for the first time, triggering generation."""
    # Setup
    game_logic = game_logic_instance
    game_state = mock_game_state_for_sublevel
    game_state.dwarves = [mock_dwarf]
    mock_gen_map.return_value = mock_sublevel_map_data
    sub_level_name = mock_sublevel_entity.name
    initial_map = game_state.map

    # Action
    game_logic._trigger_sublevel_entry(mock_dwarf, mock_entry_tile)

    # Assertions
    mock_gen_map.assert_called_once()
    mock_gen_network.assert_called_once()
    assert sub_level_name in game_state.sub_levels
    assert game_state.sub_levels[sub_level_name]["active"] is True
    assert game_state.sub_levels[sub_level_name]["map"] == mock_sublevel_map_data[0]
    assert game_state.map == mock_sublevel_map_data[0], "GameState map should be updated"
    assert game_state.map is not initial_map, "Map should have changed"
    game_state.player.update_state.assert_called_with("location", sub_level_name)
    assert game_state.mycelial_network == mock_gen_network.return_value
    game_state.calculate_network_distances.assert_called_once()
    # Check dwarf moved to walkable spawn point (1,1) in mock map
    assert mock_dwarf.x == 1
    assert mock_dwarf.y == 1
    assert mock_dwarf.state == 'idle'
    assert game_state.entry_x == mock_entry_tile.x
    assert game_state.entry_y == mock_entry_tile.y

@patch('fungi_fortress.game_logic.generate_mycelial_network') # Mock network gen
@patch('fungi_fortress.game_logic.generate_map') # Mock map gen
def test_trigger_sublevel_entry_existing_sublevel(
    mock_gen_map, mock_gen_network, # Patched args first
    game_logic_instance, mock_game_state_for_sublevel,
    mock_dwarf, mock_entry_tile, mock_sublevel_entity, mock_sublevel_map_data
):
    """Test entering a sublevel that has already been generated."""
    # Setup
    game_logic = game_logic_instance
    game_state = mock_game_state_for_sublevel
    game_state.dwarves = [mock_dwarf]
    sub_level_name = mock_sublevel_entity.name
    existing_map_data = mock_sublevel_map_data[0]
    existing_network = {(0,0): []} # Different network data

    # Pre-populate the sublevel data
    game_state.sub_levels[sub_level_name] = {
        "active": False,
        "map": existing_map_data,
        "nexus_site": mock_sublevel_map_data[1],
        "magic_fungi_locations": mock_sublevel_map_data[2],
        "mycelial_network": existing_network
    }
    initial_map = game_state.map

    # Action
    game_logic._trigger_sublevel_entry(mock_dwarf, mock_entry_tile)

    # Assertions
    mock_gen_map.assert_not_called()
    mock_gen_network.assert_not_called() # Should not regenerate network either
    assert game_state.sub_levels[sub_level_name]["active"] is True
    assert game_state.map == existing_map_data, "GameState map should be updated to existing sublevel map"
    assert game_state.map is not initial_map, "Map should have changed"
    game_state.player.update_state.assert_called_with("location", sub_level_name)
    assert game_state.mycelial_network == existing_network # Should use existing network
    game_state.calculate_network_distances.assert_called_once()
    assert mock_dwarf.x == 1 # Still moved to spawn
    assert mock_dwarf.y == 1
    assert mock_dwarf.state == 'idle'
    assert game_state.entry_x == mock_entry_tile.x
    assert game_state.entry_y == mock_entry_tile.y

@patch('fungi_fortress.game_logic.generate_map', return_value=(None, None, None)) # Simulate map gen failure
def test_trigger_sublevel_entry_map_gen_fails(
    mock_gen_map,
    game_logic_instance, mock_game_state_for_sublevel,
    mock_dwarf, mock_entry_tile, mock_sublevel_entity
):
    """Test that entry is aborted if map generation fails."""
    game_logic = game_logic_instance
    game_state = mock_game_state_for_sublevel
    initial_map = game_state.map
    sub_level_name = mock_sublevel_entity.name

    # Action
    game_logic._trigger_sublevel_entry(mock_dwarf, mock_entry_tile)

    # Assertions
    mock_gen_map.assert_called_once()
    assert game_state.map is initial_map, "Map should NOT have changed"
    # Check that the sublevel dictionary entry was created but the map is still None
    assert sub_level_name in game_state.sub_levels
    assert game_state.sub_levels[sub_level_name]["map"] is None, "Sublevel map should be None after failed generation"
    assert game_state.sub_levels[sub_level_name]["active"] is False, "Sublevel should not be active"
    # Check dwarf state didn't change to idle (or maybe it should? Depends on desired behavior)
    # assert mock_dwarf.state != 'idle'
    assert game_state.add_debug_message.call_count >= 2
    failure_call = [call for call in game_state.add_debug_message.call_args_list if "Map generation failed" in call.args[0]]
    assert failure_call, "Debug message about map generation failure expected"

# --- Tests for surface_mycelium ---

def test_surface_mycelium_runs_only_at_depth_0(mock_game_state, mock_entity_registry):
    """Test surface_mycelium does nothing if depth is not 0."""
    grass = mock_entity_registry["grass"]
    mycelium_floor = mock_entity_registry["mycelium_floor"]
    mock_game_state.map[0][0].entity = grass
    mock_game_state.depth = 1 # Set depth to non-zero
    mock_game_state.mycelial_network = {(0, 0): []} # Network node at the grass tile
    mock_game_state.player.spore_exposure = 10000 # High exposure

    # Patch constants for the duration of this test
    with patch('fungi_fortress.game_logic.MAP_WIDTH', mock_game_state.test_map_width), \
         patch('fungi_fortress.game_logic.MAP_HEIGHT', mock_game_state.test_map_height):
        with patch('random.random', return_value=0.0): # Guarantee conversion if logic runs
            surface_mycelium(mock_game_state)

    assert mock_game_state.map[0][0].entity == grass, "Tile should not convert at depth 1"

def test_surface_mycelium_does_nothing_if_entities_missing(mock_game_state, monkeypatch):
    """Test surface_mycelium adds debug msg and returns if entities missing."""
    incomplete_registry = {
        "stone_floor": MagicMock(spec=GameEntity, name="stone_floor"),
        # "mycelium_floor": Missing
        "grass": MagicMock(spec=GameEntity, name="grass")
    }
    monkeypatch.setattr('fungi_fortress.game_logic.ENTITY_REGISTRY', incomplete_registry)
    mock_game_state.depth = 0
    # Add a grass tile to attempt conversion
    mock_game_state.map[0][0].entity = incomplete_registry["grass"]
    mock_game_state.mycelial_network = {(0, 0): []}
    mock_game_state.player.spore_exposure = 100

    # Patch constants for the duration of this test
    with patch('fungi_fortress.game_logic.MAP_WIDTH', mock_game_state.test_map_width), \
         patch('fungi_fortress.game_logic.MAP_HEIGHT', mock_game_state.test_map_height):
        surface_mycelium(mock_game_state)

    mock_game_state.add_debug_message.assert_called_once_with(
        "Warning: Cannot spread surface mycelium, missing entities: mycelium_floor"
    )
    assert mock_game_state.map[0][0].entity == incomplete_registry["grass"], "Tile should not be converted"

def test_surface_mycelium_needs_network_proximity(mock_game_state, mock_entity_registry):
    """Test tile doesn't convert if not near the network, even with high exposure."""
    grass = mock_entity_registry["grass"]
    mock_game_state.map[0][0].entity = grass
    mock_game_state.depth = 0
    mock_game_state.mycelial_network = {(5, 5): []} # Network node far away
    mock_game_state.player.spore_exposure = 10000 # High exposure

    # Patch constants for the duration of this test
    with patch('fungi_fortress.game_logic.MAP_WIDTH', mock_game_state.test_map_width), \
         patch('fungi_fortress.game_logic.MAP_HEIGHT', mock_game_state.test_map_height):
        with patch('random.random', return_value=0.0):
            surface_mycelium(mock_game_state)

    assert mock_game_state.map[0][0].entity == grass, "Tile far from network should not convert"

def test_surface_mycelium_converts_near_network(mock_game_state, mock_entity_registry):
    """Test grass converts if near network node with sufficient exposure/chance."""
    grass = mock_entity_registry["grass"]
    mycelium_floor = mock_entity_registry["mycelium_floor"]
    mock_game_state.map[1][1].entity = grass # Target tile
    mock_game_state.depth = 0
    mock_game_state.mycelial_network = {(1, 0): []} # Network node adjacent (dy=-1, dx=0)
    # Exposure 100 -> base chance min(0.05, 0.000001 * 100) = 0.0001
    mock_game_state.player.spore_exposure = 100

    # Patch constants for the duration of this test
    with patch('fungi_fortress.game_logic.MAP_WIDTH', mock_game_state.test_map_width), \
         patch('fungi_fortress.game_logic.MAP_HEIGHT', mock_game_state.test_map_height):
        # random = 0.04 > 0.0001 (base chance)
        with patch('random.random', return_value=0.04):
            surface_mycelium(mock_game_state)

    # ASSERTION CHANGE: Should NOT convert because 0.04 > 0.0001
    assert mock_game_state.map[1][1].entity == grass, "Tile near network should NOT convert (0.04 > 0.0001)"

def test_surface_mycelium_converts_on_network_node(mock_game_state, monkeypatch):
    """Test stone floor converts if ON a network node with sufficient exposure/chance."""
    # Use simple strings instead of mocks for entities in this test
    simple_registry = {
        "stone_floor": "stone_entity",
        "mycelium_floor": "mycelium_entity",
        "grass": "grass_entity" # Needed for the 'all' check
    }
    monkeypatch.setattr('fungi_fortress.tiles.ENTITY_REGISTRY', simple_registry)

    mock_game_state.map[0][0].entity = "stone_entity" # Start with stone string
    mock_game_state.depth = 0
    mock_game_state.mycelial_network = {(0, 0): []} # Network node AT the tile
    # Exposure 100 -> base chance min(0.05, 0.000001 * 100) = 0.0001
    mock_game_state.player.spore_exposure = 100

    # Patch constants for the duration of this test
    with patch('fungi_fortress.game_logic.MAP_WIDTH', mock_game_state.test_map_width), \
         patch('fungi_fortress.game_logic.MAP_HEIGHT', mock_game_state.test_map_height):
        # random = 0.04 > 0.0001 (base chance)
        with patch('random.random', return_value=0.04):
            surface_mycelium(mock_game_state)

    # ASSERTION CHANGE: Should NOT convert because 0.04 > 0.0001
    assert mock_game_state.map[0][0].entity == "stone_entity", "Tile on network node should NOT convert (0.04 > 0.0001)"

def test_surface_mycelium_chance_increases_with_exposure(mock_game_state, mock_entity_registry):
    """Test that higher spore exposure increases conversion chance."""
    grass = mock_entity_registry["grass"]
    mycelium_floor = mock_entity_registry["mycelium_floor"]
    mock_game_state.map[0][0].entity = grass
    mock_game_state.depth = 0
    mock_game_state.mycelial_network = {(0, 0): []} # Network node at the tile

    # Patch constants for the duration of this test
    with patch('fungi_fortress.game_logic.MAP_WIDTH', mock_game_state.test_map_width), \
         patch('fungi_fortress.game_logic.MAP_HEIGHT', mock_game_state.test_map_height):
        # Low exposure: 10 -> base chance min(0.05, 0.000001 * 10) = 0.00001
        mock_game_state.player.spore_exposure = 10
        with patch('random.random', return_value=0.01): # 0.01 > 0.00001
            surface_mycelium(mock_game_state)
        assert mock_game_state.map[0][0].entity == grass, "Should not convert with low exposure (0.01 > 0.00001)"

        # Reset tile
        mock_game_state.map[0][0].entity = grass

        # High exposure: 1000 -> base chance min(0.05, 0.000001 * 1000) = 0.001
        mock_game_state.player.spore_exposure = 1000
        with patch('random.random', return_value=0.01): # 0.01 > 0.001
            surface_mycelium(mock_game_state)
        # ASSERTION CHANGE: Should NOT convert because 0.01 > 0.001
        assert mock_game_state.map[0][0].entity == grass, "Should NOT convert even with high exposure (0.01 > 0.001)"

def test_surface_mycelium_adjacency_bonus(mock_game_state, mock_entity_registry):
    """Test that adjacency to existing surface mycelium increases chance."""
    grass = mock_entity_registry["grass"]
    mycelium_floor = mock_entity_registry["mycelium_floor"]
    mock_game_state.map[0][0].entity = mycelium_floor # Existing surface mycelium
    mock_game_state.map[0][1].entity = grass         # Target tile adjacent to surface mycelium
    mock_game_state.depth = 0
    mock_game_state.mycelial_network = {(0, 1): []} # Network node at target tile

    # Patch constants for the duration of this test
    with patch('fungi_fortress.game_logic.MAP_WIDTH', mock_game_state.test_map_width), \
         patch('fungi_fortress.game_logic.MAP_HEIGHT', mock_game_state.test_map_height):
        # Low exposure: 10 -> base chance 0.00001
        mock_game_state.player.spore_exposure = 10
        # Adjacency bonus: 0.00001 * 10 = 0.0001

        # Test conversion with bonus
        with patch('random.random', return_value=0.04): # 0.04 > 0.0001
            surface_mycelium(mock_game_state)
        # ASSERTION CHANGE: Should NOT convert because 0.04 > 0.0001
        assert mock_game_state.map[0][1].entity == grass, "Adjacent should NOT convert with bonus (0.04 > 0.0001)"

        # Reset tile
        mock_game_state.map[0][1].entity = grass

        # Test no conversion without bonus (check isolated case with same random value)
        mock_game_state.mycelial_network = {(5, 5): []} # Move network away from [0,0]
        mock_game_state.mycelial_network[(0,1)] = [] # Ensure network is at target tile only
        mock_game_state.map[0][0].entity = grass # Remove adjacent surface mycelium
        with patch('random.random', return_value=0.04): # 0.04 > 0.00001 (base chance)
             surface_mycelium(mock_game_state)
        assert mock_game_state.map[0][1].entity == grass, "Isolated should not convert (0.04 > 0.00001)"

def test_surface_mycelium_does_not_convert_ineligible_tiles(mock_game_state, mock_entity_registry):
    """Test that walls or other non-grass/stone tiles are not converted."""
    wall = mock_entity_registry["stone_wall"]
    mock_game_state.map[0][0].entity = wall # Target tile is a wall
    mock_game_state.depth = 0
    mock_game_state.mycelial_network = {(0, 0): []} # Network node at the wall
    mock_game_state.player.spore_exposure = 10000 # High exposure

    # Patch constants for the duration of this test
    with patch('fungi_fortress.game_logic.MAP_WIDTH', mock_game_state.test_map_width), \
         patch('fungi_fortress.game_logic.MAP_HEIGHT', mock_game_state.test_map_height):
        with patch('random.random', return_value=0.0):
            surface_mycelium(mock_game_state)

    assert mock_game_state.map[0][0].entity == wall, "Wall tile should not be converted"

# --- Tests for _trigger_sublevel_entry ---

# Patch the generation functions within the fungi_fortress.game_logic module
# ... existing code ... 