import heapq
from typing import List, Tuple, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .tiles import Tile # Import Tile for type hinting
    # If GameState or other types are needed for hints, import them here too.
    # from .game_state import GameState

MapGrid = List[List['Tile']] # Use forward reference as string

def wrap_text(text: str, width: int) -> List[str]:
    """Wraps a given string to fit within a specified width.

    Splits the text into words and recombines them into lines, ensuring
    no line exceeds the given width. Handles existing whitespace.

    Args:
        text (str): The input string to wrap.
        width (int): The maximum allowed width for each line.

    Returns:
        List[str]: A list of strings, where each string is a line of the wrapped text.
    """
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        # Check if the word itself is too long
        if len(word) > width:
            # Simple handling: put the long word on its own line
            # More complex handling could break the word
            if current_line: # Add the previous line first if it exists
                lines.append(current_line)
            lines.append(word)
            current_line = ""
            continue # Move to the next word
            
        # Check if adding the word (with a preceding space if needed) fits
        if not current_line: # First word on the line
            if len(word) <= width:
                current_line = word
            else: # Should not happen due to the check above, but defensively
                 lines.append("") # Should we add an empty line?
                 current_line = word
        elif len(current_line) + len(word) + 1 <= width: # +1 for the space
            current_line += " " + word # Add space BEFORE word
        else:
            # Word doesn't fit, finalize the current line and start a new one
            lines.append(current_line)
            current_line = word # Start new line with the current word

    # Add the last line if it's not empty
    if current_line:
        lines.append(current_line)
    return lines

def a_star(map_grid: MapGrid, start: Tuple[int, int], goal: Tuple[int, int], adjacent: bool = False) -> Optional[List[Tuple[int, int]]]:
    """Finds the shortest path between two points on the map using A*.

    Considers tile walkability. Uses Manhattan distance as the heuristic.

    Args:
        map_grid: The 2D list representing the map, containing Tile objects.
                  Expected to have a `walkable` property on each tile.
        start (Tuple[int, int]): The starting coordinates (x, y).
        goal (Tuple[int, int]): The target coordinates (x, y).
        adjacent (bool, optional): If True, the algorithm finds the shortest path to
                                 a walkable tile directly adjacent to the goal,
                                 rather than the goal tile itself. Defaults to False.

    Returns:
        Optional[List[Tuple[int, int]]]: A list of (x, y) tuples representing the path
                                        from start (exclusive) to the end point (inclusive).
                                        Returns an empty list if start == goal (and not adjacent).
                                        Returns None if no path is found.
    """
    def heuristic(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    # Handle trivial cases first
    if not (0 <= start[0] < len(map_grid[0]) and 0 <= start[1] < len(map_grid)):
        return None # Start is out of bounds
    if not map_grid[start[1]][start[0]].walkable:
         return None # Start is not walkable
         
    if adjacent:
        # Check if start is already a valid adjacent destination
        start_dist_to_goal = abs(start[0] - goal[0]) + abs(start[1] - goal[1])
        if start_dist_to_goal == 1 and map_grid[start[1]][start[0]].walkable: 
             # Path consists only of the start node itself, as it's adjacent and walkable
             # The definition asks for path from start (exclusive) to end (inclusive)
             # but in this edge case, the only "step" is staying put, effectively.
             # Returning the start seems most logical if the goal is non-walkable adjacent target.
             return [start]
    elif start == goal:
        return []  # No movement needed if start is the goal (and not adjacent mode)

    open_set = [(0, start)]
    came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, goal)}

    width, height = len(map_grid[0]), len(map_grid)
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    while open_set:
        current = heapq.heappop(open_set)[1]
        if adjacent:
            # Check if current is adjacent to goal and walkable
            dist = abs(current[0] - goal[0]) + abs(current[1] - goal[1])
            if dist == 1 and map_grid[current[1]][current[0]].walkable:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                return path[::-1]
        elif current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            return path[::-1]

        for dx, dy in directions:
            neighbor = (current[0] + dx, current[1] + dy)
            if (0 <= neighbor[0] < width and 0 <= neighbor[1] < height and 
                map_grid[neighbor[1]][neighbor[0]].walkable):
                tentative_g_score = g_score[current] + 1
                if tentative_g_score < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    # Use heuristic to goal even for adjacent, to prioritize closer tiles
                    f_score[neighbor] = tentative_g_score + heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))
    return None

# Comments:
# - Updated a_star to support adjacent=True, finding the nearest walkable tile next to goal.
# - Removed redundant checks; now unified for all pathing needs.
# - Kept heuristic simple and effective for both direct and adjacent pathing.
