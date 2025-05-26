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

def a_star_for_illumination(map_grid: MapGrid, start: Tuple[int, int], goal: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
    """Finds the shortest path for illumination, treating water as walkable.

    Args:
        map_grid: The 2D list representing the map, containing Tile objects.
                  Expected to have a `walkable` property on each tile.
        start (Tuple[int, int]): The starting coordinates (x, y).
        goal (Tuple[int, int]): The target coordinates (x, y).

    Returns:
        Optional[List[Tuple[int, int]]]: A list of (x, y) tuples representing the path
                                        from start (exclusive) to the end point (inclusive).
                                        Returns an empty list if start == goal.
                                        Returns None if no path is found.
    """
    def heuristic(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    if not (0 <= start[0] < len(map_grid[0]) and 0 <= start[1] < len(map_grid)):
        return None
    # For illumination, start tile doesn't strictly need to be walkable by characters
    # if not map_grid[start[1]][start[0]].walkable:
    #     return None

    if start == goal:
        return []

    open_set = [(0, start)]
    came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, goal)}

    width, height = len(map_grid[0]), len(map_grid)
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    while open_set:
        current = heapq.heappop(open_set)[1]
        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            return path[::-1]

        for dx, dy in directions:
            neighbor = (current[0] + dx, current[1] + dy)
            if 0 <= neighbor[0] < width and 0 <= neighbor[1] < height:
                tile = map_grid[neighbor[1]][neighbor[0]]
                # MODIFICATION: Allow pathing over water for illumination
                if tile.walkable or (tile.entity and tile.entity.name == "Water"):
                    tentative_g_score = g_score[current] + 1
                    if tentative_g_score < g_score.get(neighbor, float('inf')):
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g_score
                        f_score[neighbor] = tentative_g_score + heuristic(neighbor, goal)
                        heapq.heappush(open_set, (f_score[neighbor], neighbor))
    return None

def find_path_on_network(network_graph: Dict[Tuple[int, int], List[Tuple[int, int]]],
                           start_node: Tuple[int, int],
                           end_node: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
    """Finds the shortest path between two nodes in a network graph using BFS.

    Args:
        network_graph: The adjacency list representation of the network.
        start_node: The starting node coordinates (x, y).
        end_node: The target node coordinates (x, y).

    Returns:
        A list of (x, y) tuples representing the path from start_node to end_node (inclusive).
        Returns None if no path is found or if start/end nodes are not in the graph.
    """
    if start_node not in network_graph or end_node not in network_graph:
        return None # Start or end node doesn't exist in the network

    if start_node == end_node:
        return [start_node] # Path to self is just the node itself

    queue: List[Tuple[Tuple[int, int], List[Tuple[int, int]]]] = [(start_node, [start_node])] # (current_node, path_so_far)
    visited: Set[Tuple[int, int]] = {start_node}

    while queue:
        current, path = queue.pop(0)

        for neighbor in network_graph.get(current, []):
            if neighbor == end_node:
                return path + [neighbor] # Path found
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
    
    return None # No path found

def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
    """Generates coordinates for a line between two points using Bresenham's algorithm."""
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    while True:
        points.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
    return points

# Comments:
# - Updated a_star to support adjacent=True, finding the nearest walkable tile next to goal.
# - Removed redundant checks; now unified for all pathing needs.
# - Kept heuristic simple and effective for both direct and adjacent pathing.
