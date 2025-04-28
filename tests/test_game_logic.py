import pytest
from unittest.mock import patch, MagicMock
import random

# Use absolute imports from the installed package
from fungi_fortress.game_logic import expose_to_spores
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
    # Patch the ENTITY_REGISTRY within the fungi_fortress.game_logic module
    monkeypatch.setattr('fungi_fortress.game_logic.ENTITY_REGISTRY', registry)
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

    # Patch constants within the fungi_fortress.game_logic module
    with patch('fungi_fortress.game_logic.MAP_WIDTH', MAP_W), \
         patch('fungi_fortress.game_logic.MAP_HEIGHT', MAP_H):
        yield game_state

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

# --- Tests for expose_to_spores ---

def test_expose_to_spores_converts_eligible_tiles(mock_game_state, mock_entity_registry):
    """Test that stone floor and grass are converted with guaranteed random."""
    stone = mock_entity_registry["stone_floor"]
    grass = mock_entity_registry["grass"]
    mycelium = mock_entity_registry["mycelium_floor"]
    wall = mock_entity_registry["stone_wall"]

    # Setup map: stone, grass
    mock_game_state.map[0][0].entity = stone
    mock_game_state.map[0][1].entity = grass
    mock_game_state.map[1][0].entity = wall # Should not convert

    with patch('random.random', return_value=0.0):
        expose_to_spores(mock_game_state, intensity=10) # Intensity 10 -> base 0.1, adjacent 0.5

    assert mock_game_state.map[0][0].entity == mycelium, "Stone floor should convert"
    assert mock_game_state.map[0][1].entity == mycelium, "Grass should convert"
    assert mock_game_state.map[1][0].entity == wall, "Wall should not convert"

def test_expose_to_spores_adjacent_converts(mock_game_state, mock_entity_registry):
    """Test adjacent tile converts when random < adjacent_chance."""
    stone = mock_entity_registry["stone_floor"]
    mycelium = mock_entity_registry["mycelium_floor"]
    mock_game_state.map[0][0].entity = mycelium
    mock_game_state.map[1][0].entity = stone # Target tile (adjacent)

    # Intensity 1 -> base 0.01, adjacent 0.05
    # Random value 0.04 < 0.05
    with patch('random.random', return_value=0.04):
        expose_to_spores(mock_game_state, intensity=1)

    assert mock_game_state.map[1][0].entity == mycelium, "Adjacent tile should convert (0.04 < 0.05)"

def test_expose_to_spores_adjacent_does_not_convert(mock_game_state, mock_entity_registry):
    """Test adjacent tile does not convert when random > adjacent_chance."""
    stone = mock_entity_registry["stone_floor"]
    mycelium = mock_entity_registry["mycelium_floor"]
    mock_game_state.map[0][0].entity = mycelium
    mock_game_state.map[1][0].entity = stone # Target tile (adjacent)

    # Intensity 1 -> base 0.01, adjacent 0.05
    # Random value 0.06 > 0.05
    with patch('random.random', return_value=0.06):
        expose_to_spores(mock_game_state, intensity=1)

    assert mock_game_state.map[1][0].entity == stone, "Adjacent tile should NOT convert (0.06 > 0.05)"

def test_expose_to_spores_isolated_converts(mock_game_state, mock_entity_registry):
    """Test isolated tile converts when random < base_chance."""
    stone = mock_entity_registry["stone_floor"]
    mycelium = mock_entity_registry["mycelium_floor"]
    # No adjacent mycelium
    mock_game_state.map[0][0].entity = stone # Target tile (isolated)

    # Intensity 10 -> base 0.1, adjacent 0.5
    # Random value 0.09 < 0.1
    with patch('random.random', return_value=0.09):
        expose_to_spores(mock_game_state, intensity=10)

    assert mock_game_state.map[0][0].entity == mycelium, "Isolated tile should convert (0.09 < 0.1)"

def test_expose_to_spores_isolated_does_not_convert(mock_game_state, mock_entity_registry):
    """Test isolated tile does not convert when random > base_chance."""
    stone = mock_entity_registry["stone_floor"]
    # No adjacent mycelium
    mock_game_state.map[0][0].entity = stone # Target tile (isolated)

    # Intensity 10 -> base 0.1, adjacent 0.5
    # Random value 0.11 > 0.1
    with patch('random.random', return_value=0.11):
        expose_to_spores(mock_game_state, intensity=10)

    assert mock_game_state.map[0][0].entity == stone, "Isolated tile should NOT convert (0.11 > 0.1)"

def test_expose_to_spores_no_conversion_if_random_high(mock_game_state, mock_entity_registry):
    """Test that tiles don't convert if random number is too high."""
    stone_start = mock_entity_registry["stone_floor"]
    mock_game_state.map[1][1].entity = stone_start

    with patch('random.random', return_value=0.99):
        expose_to_spores(mock_game_state, intensity=10)

    assert mock_game_state.map[1][1].entity == stone_start, "Tile should not convert if random is high"

def test_expose_to_spores_intensity_effect(mock_game_state, mock_entity_registry):
    """Test that higher intensity increases conversion probability."""
    stone = mock_entity_registry["stone_floor"]
    mycelium = mock_entity_registry["mycelium_floor"]
    mock_game_state.map[0][0].entity = stone

    mock_random = MagicMock(return_value=0.05)

    with patch('random.random', mock_random):
        expose_to_spores(mock_game_state, intensity=1) # Chance 0.01
    assert mock_game_state.map[0][0].entity == stone, "Should not convert with intensity 1 (0.05 > 0.01)"

    mock_game_state.map[0][0].entity = stone
    mock_random.reset_mock()
    mock_random.return_value = 0.05

    with patch('random.random', mock_random):
        expose_to_spores(mock_game_state, intensity=10) # Chance 0.10
    assert mock_game_state.map[0][0].entity == mycelium, "Should convert with intensity 10 (0.05 < 0.1)"

def test_expose_to_spores_missing_entity_raises_error(mock_game_state, monkeypatch):
    """Test that ImportError is raised if essential entities are missing."""
    incomplete_registry = {
        "stone_floor": MagicMock(spec=GameEntity, name="stone_floor"),
        "grass": MagicMock(spec=GameEntity, name="grass"),
        "bridge": MagicMock(spec=GameEntity, name="bridge")
    }
    # Patch the registry within the fungi_fortress.game_logic module
    monkeypatch.setattr('fungi_fortress.game_logic.ENTITY_REGISTRY', incomplete_registry)

    with pytest.raises(ImportError, match="Essential floor/terrain entities not found"):
        expose_to_spores(mock_game_state, intensity=1)

# Simplified mock_game_state fixture using a 2x2 map for easier testing
# Updated patches and tests to use the 2x2 dimension

# Optional: Test edge cases like empty map or map boundaries if needed
# def test_expose_to_spores_empty_map(mock_game_state): ...
# def test_expose_to_spores_map_edges(mock_game_state): ...
# These might be implicitly covered if the loops handle boundaries correctly.

# Remove the original placeholder test if it still exists
# def test_example_game_logic_functionality(): ... 

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