import pytest
from unittest.mock import patch, MagicMock, call
import random

# Import necessary components from magic.py
from fungi_fortress.magic import fungal_bloom_effect, SpellDefinition, ENTITY_REGISTRY as MAGIC_ENTITY_REGISTRY
from fungi_fortress.tiles import Tile, GameEntity # Tile needed for type hints and creation
# GameState, Dwarf, Animal, NPC needed for type hints and mock creation
from fungi_fortress.game_state import GameState
from fungi_fortress.characters import Dwarf, Animal, NPC

# --- Mock Entities ---

@pytest.fixture
def mock_entities():
    """Provides mock GameEntity objects for testing."""
    entities = {}
    for name, walkable in [
        ("fungi", True), ("magic_fungi", True), ("grass", True),
        ("stone_floor", True), ("mycelium_floor", True),
        ("water", False), ("stone_wall", False), ("tree", False) # Add other entities if needed
    ]:
        # Create mock without spec, but ensure required attributes exist
        mock_entity = MagicMock()
        mock_entity.name = name
        mock_entity.walkable = walkable
        entities[name] = mock_entity
    return entities

@pytest.fixture
def mock_entity_registry(monkeypatch, mock_entities):
    """Fixture to patch the ENTITY_REGISTRY within the magic module."""
    # Patch the entire ENTITY_REGISTRY dict *where it's used* in the magic module
    monkeypatch.setattr('fungi_fortress.magic.ENTITY_REGISTRY', mock_entities)
    # This replaces the original dict with our mock dict for the test duration
    return mock_entities


# --- Mock GameState ---

@pytest.fixture
def mock_tile():
    """Creates a single mock Tile."""
    tile = MagicMock(spec=Tile)
    tile.x = 5
    tile.y = 5
    tile.entity = None # Start with no entity
    tile.walkable = True # Assume walkable unless entity makes it not
    tile.pulse_ticks = 0
    tile.set_color_override = MagicMock()
    # Add other attributes if needed by effects
    return tile

@pytest.fixture
def mock_game_state(mock_entity_registry): # Depends on registry fixture
    """Creates a mock GameState object configured for magic tests."""
    game = MagicMock(spec=GameState)

    # Map setup
    game.map = {} # Use a dict for sparse map representation in tests {(x, y): Tile}
    def _get_tile(x, y):
        return game.map.get((x, y))
    game.get_tile = MagicMock(side_effect=_get_tile)

    # Debugging
    game.add_debug_message = MagicMock()

    # Mycelial Network related attributes
    game.mycelial_network = {} # {(x, y): [(nx, ny), ...]}
    game.nexus_site = None # (x, y) or None
    game.network_distances = {} # {(x, y): distance}
    game.calculate_network_distances = MagicMock(return_value={}) # Mock the calculation

    # Other relevant attributes
    game.magic_fungi_locations = []
    game.dwarves = []
    game.animals = []
    game.characters = [] # For NPCs

    # Player (if needed by specific effects)
    game.player = MagicMock()

    return game


# --- Tests for fungal_bloom_effect ---

def test_fungal_bloom_converts_grass_to_fungi(mock_game_state, mock_entity_registry, mock_tile):
    """Test grass converts to fungi with favorable random chance."""
    grass = mock_entity_registry["grass"]
    fungi = mock_entity_registry["fungi"]
    mock_tile.entity = grass
    mock_game_state.map[(mock_tile.x, mock_tile.y)] = mock_tile

    # Ensure random check passes (random.random() < 0.3)
    with patch('random.random', return_value=0.1):
        fungal_bloom_effect(mock_tile, mock_game_state)

    assert mock_tile.entity == fungi
    mock_game_state.add_debug_message.assert_called_with(f"Fungal Bloom: Created fungi at ({mock_tile.x}, {mock_tile.y})")

def test_fungal_bloom_converts_stone_floor_to_fungi(mock_game_state, mock_entity_registry, mock_tile):
    """Test stone floor converts to fungi with favorable random chance."""
    stone_floor = mock_entity_registry["stone_floor"]
    fungi = mock_entity_registry["fungi"]
    mock_tile.entity = stone_floor
    mock_game_state.map[(mock_tile.x, mock_tile.y)] = mock_tile

    with patch('random.random', return_value=0.1):
        fungal_bloom_effect(mock_tile, mock_game_state)

    assert mock_tile.entity == fungi

def test_fungal_bloom_does_not_convert_grass_if_random_fails(mock_game_state, mock_entity_registry, mock_tile):
    """Test grass does not convert if random check fails."""
    grass = mock_entity_registry["grass"]
    mock_tile.entity = grass
    mock_game_state.map[(mock_tile.x, mock_tile.y)] = mock_tile

    # Ensure random check fails (random.random() >= 0.3)
    with patch('random.random', return_value=0.5):
        fungal_bloom_effect(mock_tile, mock_game_state)

    assert mock_tile.entity == grass # Should remain grass
    mock_game_state.add_debug_message.assert_not_called()

def test_fungal_bloom_converts_fungi_to_magic_fungi_near_water(mock_game_state, mock_entity_registry, mock_tile):
    """Test fungi converts to magic fungi near water with favorable random chance."""
    fungi = mock_entity_registry["fungi"]
    magic_fungi = mock_entity_registry["magic_fungi"]
    water = mock_entity_registry["water"]

    mock_tile.entity = fungi
    mock_game_state.map[(mock_tile.x, mock_tile.y)] = mock_tile

    # Place water nearby
    water_tile = MagicMock(spec=Tile, entity=water, x=mock_tile.x + 1, y=mock_tile.y)
    mock_game_state.map[(water_tile.x, water_tile.y)] = water_tile

    # Ensure random check passes (random.random() < 0.4)
    with patch('random.random', return_value=0.2):
        fungal_bloom_effect(mock_tile, mock_game_state)

    assert mock_tile.entity == magic_fungi
    assert (mock_tile.x, mock_tile.y) in mock_game_state.magic_fungi_locations
    mock_game_state.add_debug_message.assert_called_with(f"Fungal Bloom: Created magic fungi at ({mock_tile.x}, {mock_tile.y})")

def test_fungal_bloom_does_not_convert_fungi_if_no_nearby_water(mock_game_state, mock_entity_registry, mock_tile):
    """Test fungi does not convert to magic fungi if no water is nearby."""
    fungi = mock_entity_registry["fungi"]
    mock_tile.entity = fungi
    mock_game_state.map[(mock_tile.x, mock_tile.y)] = mock_tile

    # Ensure no water nearby (only the target tile exists in the mock map)
    with patch('random.random', return_value=0.2): # Random would pass if water was present
        fungal_bloom_effect(mock_tile, mock_game_state)

    assert mock_tile.entity == fungi # Should remain normal fungi

def test_fungal_bloom_does_not_convert_fungi_near_water_if_random_fails(mock_game_state, mock_entity_registry, mock_tile):
    """Test fungi does not convert near water if random check fails."""
    fungi = mock_entity_registry["fungi"]
    magic_fungi = mock_entity_registry["magic_fungi"]
    water = mock_entity_registry["water"]

    mock_tile.entity = fungi
    mock_game_state.map[(mock_tile.x, mock_tile.y)] = mock_tile

    # Place water nearby
    water_tile = MagicMock(spec=Tile, entity=water, x=mock_tile.x + 1, y=mock_tile.y)
    mock_game_state.map[(water_tile.x, water_tile.y)] = water_tile

    # Ensure random check fails (random.random() >= 0.4)
    with patch('random.random', return_value=0.5):
        fungal_bloom_effect(mock_tile, mock_game_state)

    assert mock_tile.entity == fungi # Should remain normal fungi

def test_fungal_bloom_does_not_convert_occupied_tile(mock_game_state, mock_entity_registry, mock_tile):
    """Test grass/floor does not convert to fungi if occupied by a dwarf."""
    grass = mock_entity_registry["grass"]
    fungi = mock_entity_registry["fungi"]
    mock_tile.entity = grass
    mock_game_state.map[(mock_tile.x, mock_tile.y)] = mock_tile

    # Add a dwarf at the tile location
    mock_dwarf = MagicMock(spec=Dwarf, x=mock_tile.x, y=mock_tile.y, alive=True)
    mock_game_state.dwarves.append(mock_dwarf)

    with patch('random.random', return_value=0.1): # Random check would normally pass
        fungal_bloom_effect(mock_tile, mock_game_state)

    assert mock_tile.entity == grass # Should remain grass because of the dwarf
    mock_game_state.add_debug_message.assert_not_called() # No conversion message


# TODO: Add tests for network enhancement logic within fungal_bloom_effect
# - Test adding a new node near existing network
# - Test connecting to existing nodes
# - Test recalculation call
# - Test visual effects (pulse, color)
# - Test logic when tile is not walkable
# - Test logic when random check for network enhancement fails
# - Test logic when no nearby nodes exist
# - Test logic when mycelial_network is initially empty or None

# Remove the placeholder test
# def test_example_magic_functionality():
#     # TODO: Replace with actual tests for magic functions/classes
#     # Example:
#     # assert cast_spell(some_spell, caster, target) == expected_effect
#     assert True 