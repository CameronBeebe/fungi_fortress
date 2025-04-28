import pytest
import random
from fungi_fortress.map_generation import generate_map, create_empty_map
from fungi_fortress.tiles import Tile, ENTITY_REGISTRY
from fungi_fortress.constants import MAP_WIDTH, MAP_HEIGHT

# Re-seed random for more predictable (but not identical) tests across runs
random.seed(12345)

# --- Test create_empty_map ---
def test_create_empty_map_dimensions():
    width, height = 10, 15
    grid = create_empty_map(width, height)
    assert len(grid) == height
    assert all(len(row) == width for row in grid)

def test_create_empty_map_default_tile():
    grid = create_empty_map(5, 5, default_entity_name="stone_floor")
    stone_floor_entity = ENTITY_REGISTRY["stone_floor"]
    assert all(tile.entity == stone_floor_entity for row in grid for tile in row)

def test_create_empty_map_custom_tile():
    grid = create_empty_map(5, 5, default_entity_name="grass")
    grass_entity = ENTITY_REGISTRY["grass"]
    assert all(tile.entity == grass_entity for row in grid for tile in row)

def test_create_empty_map_invalid_tile():
    with pytest.raises(ValueError):
        create_empty_map(5, 5, default_entity_name="non_existent_tile")

# --- Test generate_map --- 

# Helper to check map structure and types
def check_map_structure(map_grid, width, height):
    assert isinstance(map_grid, list)
    assert len(map_grid) == height
    assert all(isinstance(row, list) for row in map_grid)
    assert all(len(row) == width for row in map_grid)
    assert all(isinstance(tile, Tile) for row in map_grid for tile in row)

@pytest.mark.parametrize("depth, sub_level", [
    (0, None),        # Surface
    (1, None),        # Underground level 1
    (5, None),        # Underground level 5
    (1, "shadowed_grotto"), # Known sub-level
    (1, "mycelial_nexus_core"), # Known sub-level
    (1, "unknown_sublevel") # Unknown sub-level (should default)
])
def test_generate_map_return_structure(depth, sub_level):
    """Test the return type and structure for various generation parameters."""
    map_grid, nexus_site, magic_fungi_locs = generate_map(MAP_WIDTH, MAP_HEIGHT, depth, {}, sub_level)
    
    check_map_structure(map_grid, MAP_WIDTH, MAP_HEIGHT)
    
    assert nexus_site is None or (isinstance(nexus_site, tuple) and len(nexus_site) == 2 and all(isinstance(i, int) for i in nexus_site))
    
    assert isinstance(magic_fungi_locs, list)
    assert all(isinstance(loc, tuple) and len(loc) == 2 and all(isinstance(i, int) for i in loc) for loc in magic_fungi_locs)

def test_generate_map_surface_contains_expected_tiles():
    """Check if surface map contains grass, trees, water (probabilistic)."""
    map_grid, _, _ = generate_map(MAP_WIDTH, MAP_HEIGHT, 0, {}, None)
    contains_grass = any(t.entity.name == "Grass" for row in map_grid for t in row)
    contains_trees = any(t.entity.name == "Tree" for row in map_grid for t in row)
    contains_water = any(t.entity.name == "Water" for row in map_grid for t in row)
    # These are probabilistic, but should likely be true for default constants
    assert contains_grass
    assert contains_trees
    assert contains_water

def test_generate_map_underground_contains_expected_tiles():
    """Check if underground map contains stone floor/walls (probabilistic)."""
    map_grid, _, _ = generate_map(MAP_WIDTH, MAP_HEIGHT, 1, {}, None)
    contains_floor = any(t.entity.name == "Stone Floor" for row in map_grid for t in row)
    contains_wall = any(t.entity.name == "Stone Wall" for row in map_grid for t in row)
    # Should always contain floor and walls
    assert contains_floor
    assert contains_wall

def test_generate_map_nexus_site_validity():
    """If a nexus site is returned, check if the tile is suitable."""
    # Run multiple times as placement isn't guaranteed
    for _ in range(10): 
        map_grid, nexus_site, _ = generate_map(MAP_WIDTH, MAP_HEIGHT, 1, {}, None)
        if nexus_site:
            nx, ny = nexus_site
            assert 0 <= nx < MAP_WIDTH
            assert 0 <= ny < MAP_HEIGHT
            nexus_tile = map_grid[ny][nx]
            # Nexus site should ideally be walkable and buildable (e.g., stone floor)
            assert nexus_tile.walkable is True 
            assert nexus_tile.buildable is True
            return # Found a valid site, test passes
    # If loop finishes without finding a nexus site, that might be okay, 
    # but maybe worth logging or a weaker assertion depending on requirements.
    # For now, we assume it should find one sometimes.

def test_generate_map_magic_fungi_locations_validity():
    """Check if magic fungi locations actually contain magic fungi."""
    magic_fungi_entity = ENTITY_REGISTRY["magic_fungi"]
    # Test across different depths/sublevels where it might appear
    for depth, sub_level in [(1, None), (5, None), (1, "shadowed_grotto"), (1, "mycelial_nexus_core")]:
         map_grid, _, magic_fungi_locs = generate_map(MAP_WIDTH, MAP_HEIGHT, depth, {}, sub_level)
         if magic_fungi_locs:
             for x, y in magic_fungi_locs:
                 assert 0 <= x < MAP_WIDTH
                 assert 0 <= y < MAP_HEIGHT
                 assert map_grid[y][x].entity == magic_fungi_entity

# More tests could involve: 
# - Mocking `noise.pnoise2` to test specific noise values result in specific tiles.
# - Testing cellular automata logic more directly (requires extracting it or complex setup).
# - Testing properties of specific sub-levels (e.g., does grotto always have water?). 