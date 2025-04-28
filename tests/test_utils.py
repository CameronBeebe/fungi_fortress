import pytest
from fungi_fortress.utils import wrap_text, a_star

# --- Tests for wrap_text --- 

def test_wrap_text_simple():
    text = "This is a simple test case."
    width = 10
    expected = ["This is a", "simple", "test case."]
    assert wrap_text(text, width) == expected

def test_wrap_text_long_word():
    text = "A verylongwordthatcannotbreak should be on its own line."
    width = 15
    expected = ["A", "verylongwordthatcannotbreak", "should be on", "its own line."]
    assert wrap_text(text, width) == expected

def test_wrap_text_exact_width():
    text = "Line one Line two"
    width = 8
    expected = ["Line one", "Line two"]
    assert wrap_text(text, width) == expected

def test_wrap_text_empty_string():
    assert wrap_text("", 10) == []

def test_wrap_text_small_width():
    text = "Word one"
    width = 3
    # Current behavior: words longer than width get their own line, unbroken.
    expected = ["Word", "one"]
    assert wrap_text(text, width) == expected

def test_wrap_text_with_newlines():
    # Note: Current implementation treats existing newlines as spaces.
    text = "First line.\nSecond line."
    width = 15
    expected = ["First line.", "Second line."] # Assumes split() handles \n implicitly
    # Let's adjust the test based on actual split() behavior
    assert wrap_text(text, width) == ["First line.", "Second line."]


# --- Tests for a_star --- 

# Helper class to mock Tiles for pathfinding tests
class MockTile:
    def __init__(self, walkable: bool):
        self.walkable = walkable

# Simple grid fixture
@pytest.fixture
def simple_grid():
    # 5x5 grid, W=Wall, .=Floor
    #  01234
    # 0 .....
    # 1 .W.W.
    # 2 .W...
    # 3 .WW..
    # 4 .....
    grid = [
        [MockTile(True), MockTile(True), MockTile(True), MockTile(True), MockTile(True)],
        [MockTile(True), MockTile(False), MockTile(True), MockTile(False), MockTile(True)],
        [MockTile(True), MockTile(False), MockTile(True), MockTile(True), MockTile(True)],
        [MockTile(True), MockTile(False), MockTile(False), MockTile(True), MockTile(True)],
        [MockTile(True), MockTile(True), MockTile(True), MockTile(True), MockTile(True)]
    ]
    return grid

def test_a_star_simple_path(simple_grid):
    start = (0, 0)
    goal = (4, 4)
    path = a_star(simple_grid, start, goal)
    assert path is not None
    # One possible shortest path (many exist)
    expected_path = [(0,1), (0,2), (0,3), (0,4), (1,4), (2,4), (3,4), (4,4)] 
    # Alternative: [(1,0), (2,0), (2,1), (2,2), (3,2), (4,2), (4,3), (4,4)] - Let's check length and end point
    assert path[-1] == goal
    assert len(path) == 8 # Known shortest path length for this grid

def test_a_star_no_path(simple_grid):
    start = (0, 0)
    goal = (1, 1) # Blocked by wall
    path = a_star(simple_grid, start, goal)
    assert path is None

def test_a_star_start_equals_goal(simple_grid):
    start = (0, 0)
    goal = (0, 0)
    path = a_star(simple_grid, start, goal)
    assert path == []

def test_a_star_adjacent_path(simple_grid):
    start = (0, 0)
    goal = (1, 1) # The goal is a wall
    # Find path to a walkable square next to the goal (e.g., (0,1), (2,1))
    path = a_star(simple_grid, start, goal, adjacent=True)
    assert path is not None
    assert path[-1] in [(0, 1), (2, 1), (1, 0), (1, 2)] # Possible adjacent destinations
    assert simple_grid[path[-1][1]][path[-1][0]].walkable is True
    # Check path length to one potential adjacent spot (0,1)
    if path[-1] == (0,1):
        assert len(path) == 1

def test_a_star_adjacent_start_next_to_goal(simple_grid):
    start = (0, 1)
    goal = (1, 1) # Wall
    path = a_star(simple_grid, start, goal, adjacent=True)
    assert path == [(0, 1)] # Already adjacent and walkable

def test_a_star_adjacent_start_equals_goal(simple_grid):
    start = (0,0)
    goal = (0,0)
    path = a_star(simple_grid, start, goal, adjacent=True)
    # Should find adjacent square if possible, path length depends on grid
    assert path is not None
    assert path[-1] in [(1,0), (0,1)]
    assert len(path) == 1

def test_a_star_adjacent_no_walkable_neighbor(simple_grid):
    # Goal surrounded by walls (modify grid slightly)
    # Goal is (1, 1)
    # Adjacent tiles are (0, 1), (2, 1), (1, 0), (1, 2)
    # Modify the grid using grid[y][x]
    simple_grid[1][0] = MockTile(False) # Wall at (0, 1) 
    simple_grid[1][2] = MockTile(False) # Wall at (2, 1)
    simple_grid[0][1] = MockTile(False) # Wall at (1, 0)
    simple_grid[2][1] = MockTile(False) # Wall at (1, 2)
    start = (0, 0)
    goal = (1, 1) # Wall, now surrounded by walls
    path = a_star(simple_grid, start, goal, adjacent=True)
    assert path is None # Cannot reach any walkable adjacent tile 