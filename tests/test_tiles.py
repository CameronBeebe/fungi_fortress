import pytest
from fungi_fortress.tiles import Tile, ENTITY_REGISTRY
from fungi_fortress.entities import GameEntity # Need base class for type checks

# Get some sample entities from the registry for testing
sample_walkable_entity = ENTITY_REGISTRY["grass"]
sample_nonwalkable_entity = ENTITY_REGISTRY["stone_wall"]
sample_buildable_entity = ENTITY_REGISTRY["stone_floor"]
sample_nonbuildable_entity = ENTITY_REGISTRY["water"]

def test_tile_initialization():
    """Test initializing a Tile with a valid entity."""
    tile = Tile(entity=sample_walkable_entity, x=5, y=10)
    assert tile.entity == sample_walkable_entity
    assert tile.x == 5
    assert tile.y == 10
    assert tile.designated is False
    assert tile.highlight_ticks == 0
    assert tile.flash_ticks == 0
    assert tile.pulse_ticks == 0
    assert tile._color_override is None

def test_tile_initialization_invalid_entity():
    """Test that Tile initialization raises TypeError for non-GameEntity."""
    with pytest.raises(TypeError):
        Tile(entity="not an entity", x=1, y=1) # type: ignore

def test_tile_properties_delegation():
    """Test that Tile properties correctly delegate to the entity."""
    tile_walkable = Tile(entity=sample_walkable_entity, x=1, y=1)
    tile_nonwalkable = Tile(entity=sample_nonwalkable_entity, x=1, y=1)
    tile_buildable = Tile(entity=sample_buildable_entity, x=1, y=1)
    tile_nonbuildable = Tile(entity=sample_nonbuildable_entity, x=1, y=1)
    
    assert tile_walkable.name == sample_walkable_entity.name
    assert tile_walkable.char == sample_walkable_entity.char
    assert tile_walkable.walkable is True
    assert tile_walkable.buildable is True # Grass is buildable
    assert tile_walkable.color == sample_walkable_entity.color
    
    assert tile_nonwalkable.walkable is False
    assert tile_nonwalkable.buildable is False # Stone wall is not buildable
    assert tile_nonwalkable.color == sample_nonwalkable_entity.color

    assert tile_buildable.buildable is True
    assert tile_nonbuildable.buildable is False

def test_tile_color_override():
    """Test setting and getting the color override."""
    tile = Tile(entity=sample_walkable_entity, x=1, y=1)
    original_color = tile.color
    override_color = 99 # Assuming 99 is a valid color pair index
    
    assert tile.color == original_color
    
    # Set override
    tile.set_color_override(override_color)
    assert tile._color_override == override_color
    assert tile.color == override_color # Property should return override
    
    # Clear override
    tile.set_color_override(None)
    assert tile._color_override is None
    assert tile.color == original_color # Property should return original

def test_tile_str_representation():
    """Test the string representation of the Tile."""
    tile = Tile(entity=sample_walkable_entity, x=1, y=1)
    assert str(tile) == sample_walkable_entity.name

# Note: Testing the Tile.interact() method would require mocking GameState
# and potentially the interaction logic functions, which is more complex
# and suitable for integration testing or specific interaction tests. 