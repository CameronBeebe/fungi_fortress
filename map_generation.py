# map_generation.py
"""Handles the procedural generation of game maps and related features.

Includes functions for generating the main game map based on depth and themes,
creating specific sub-levels, and generating the mycelial network graph used
for spell effects and potentially pathfinding.
"""
import random
import noise
import copy # Import copy module
from typing import List, Tuple, TYPE_CHECKING, Dict

# Update constants import to relative
from .constants import MAP_WIDTH, MAP_HEIGHT, ROCK_THRESHOLD, TREE_DENSITY, WATER_LEVEL, GRASS_LEVEL, FUNGI_DENSITY, MAGIC_FUNGI_DENSITY, MYCELIUM_THRESHOLD

# Use relative imports for sibling modules
from .tiles import Tile, ENTITY_REGISTRY
from .entities import GameEntity, ResourceNode # Updated to include ResourceNode

if TYPE_CHECKING:
    from .game_state import GameState # Use relative import for type hint

MapGrid = List[List[Tile]]

def create_empty_map(width: int, height: int, default_entity_name: str = "stone_floor") -> MapGrid:
    """Creates a map grid filled entirely with a specified default entity.

    Args:
        width (int): The desired width of the map.
        height (int): The desired height of the map.
        default_entity_name (str): The key in `ENTITY_REGISTRY` for the entity to fill the map with.
                                   Defaults to "stone_floor".

    Returns:
        MapGrid: A list of lists of `Tile` objects representing the map.

    Raises:
        ValueError: If `default_entity_name` is not found in `ENTITY_REGISTRY`.
    """
    if default_entity_name not in ENTITY_REGISTRY:
        raise ValueError(f"Default entity '{default_entity_name}' not found in ENTITY_REGISTRY")
    default_entity = ENTITY_REGISTRY[default_entity_name]
    return [[Tile(default_entity, x, y) for x in range(width)] for y in range(height)]

def generate_map(width: int, height: int, depth: int, mission: dict, sub_level: str | None = None) -> Tuple[MapGrid, Tuple[int, int] | None, List[Tuple[int, int]]]:
    """Generates a playable map grid with terrain, features, and points of interest.

    The generation logic varies significantly based on the `depth` and `sub_level` type:
    - `depth == 0`: Generates a surface map with grass, stone, a river, fords, trees, and fungi.
                   Uses cellular automata for initial stone placement.
    - `depth > 0`: Generates underground cave levels using cellular automata, with increasing
                   chances of water features and potential sub-level entrances (e.g., Grotto).
    - `sub_level`: If provided, generates a specific sub-level layout (e.g., "shadowed_grotto",
                     "mycelial_nexus_core"). Falls back to a simple cave if type is unknown.

    Also designates a `nexus_site` (a suitable location for building the Mycelial Nexus)
    and identifies locations of `magic_fungi`.

    Args:
        width (int): The width of the map to generate.
        height (int): The height of the map to generate.
        depth (int): The current game depth (0 for surface, >0 for underground).
                     Affects terrain generation parameters.
        mission (dict): The current mission dictionary (currently unused in generation logic,
                      but passed for potential future use).
        sub_level (str | None): If generating a sub-level, specifies its type (e.g., "shadowed_grotto").
                                Defaults to None for main level generation.

    Returns:
        Tuple[MapGrid, Tuple[int, int] | None, List[Tuple[int, int]]]: A tuple containing:
            - map_grid (MapGrid): The generated list of lists of `Tile` objects.
            - nexus_site (Tuple[int, int] | None): Coordinates (x, y) designated for building the nexus.
                                                   None if generation fails to place one.
            - magic_fungi_locations (List[Tuple[int, int]]): List of coordinates (x, y) where magic fungi were placed.
    """
    map_grid = create_empty_map(width, height, default_entity_name="grass" if depth == 0 else "stone_floor")
    nexus_site = None
    magic_fungi_locations = []
    scale = 10.0 + depth * 2.0 # Increase scale with depth for potentially larger features
    octaves = 4 + depth // 2   # More detail deeper down
    persistence = 0.5
    lacunarity = 2.0
    seed = random.randint(0, 100) + depth # Vary seed with depth

    # Reference entities from the registry
    grass = ENTITY_REGISTRY["grass"]
    stone_wall = ENTITY_REGISTRY["stone_wall"]
    stone_floor = ENTITY_REGISTRY["stone_floor"]
    water = ENTITY_REGISTRY["water"]
    tree = ENTITY_REGISTRY["tree"]
    fungi = ENTITY_REGISTRY["fungi"]
    magic_fungi_entity = ENTITY_REGISTRY["magic_fungi"]
    mycelium_floor = ENTITY_REGISTRY["mycelium_floor"]
    mycelium_wall = ENTITY_REGISTRY["mycelium_wall"]

    # Specific entity for Shadowed Grotto entry
    grotto_entry = ENTITY_REGISTRY.get("Shadowed Grotto")

    # --- Sub-level specific generation ---
    if sub_level:
        if sub_level == "shadowed_grotto":
            # Create a beautiful grotto with pools and minerals
            # First, create a central chamber
            center_x, center_y = width // 2, height // 2
            chamber_radius = min(width, height) // 3
            
            # Create the main chamber
            for y in range(height):
                for x in range(width):
                    distance = ((x - center_x)**2 + (y - center_y)**2)**0.5
                    if distance < chamber_radius:
                        map_grid[y][x] = Tile(stone_floor, x, y)
                    else:
                        map_grid[y][x] = Tile(stone_wall, x, y)
            
            # Create shimmering pools
            num_pools = random.randint(3, 5)
            for _ in range(num_pools):
                pool_x = random.randint(center_x - chamber_radius + 2, center_x + chamber_radius - 2)
                pool_y = random.randint(center_y - chamber_radius + 2, center_y + chamber_radius - 2)
                pool_size = random.randint(2, 3)
                
                for dy in range(-pool_size, pool_size + 1):
                    for dx in range(-pool_size, pool_size + 1):
                        nx, ny = pool_x + dx, pool_y + dy
                        if 0 <= nx < width and 0 <= ny < height:
                            distance = (dx*dx + dy*dy)**0.5
                            if distance <= pool_size:
                                map_grid[ny][nx] = Tile(water, nx, ny)
                                # Add some mineral deposits around the pool
                                if random.random() < 0.3:
                                    for mineral_dy in range(-1, 2):
                                        for mineral_dx in range(-1, 2):
                                            mineral_x, mineral_y = nx + mineral_dx, ny + mineral_dy
                                            if 0 <= mineral_x < width and 0 <= mineral_y < height:
                                                if map_grid[mineral_y][mineral_x].entity == stone_floor:
                                                    # Add special mineral tiles (you'll need to define these in your entity registry)
                                                    map_grid[mineral_y][mineral_x] = Tile(ENTITY_REGISTRY.get("mineral_deposit", stone_floor), mineral_x, mineral_y)
            
            # Add special fungi around the pools
            for y in range(height):
                for x in range(width):
                    if map_grid[y][x].entity == stone_floor:
                        # Check for nearby water
                        has_nearby_water = any(map_grid[ny][nx].entity == water 
                                            for ny in range(max(0, y-1), min(height, y+2))
                                            for nx in range(max(0, x-1), min(width, x+2)))
                        
                        if has_nearby_water:
                            if random.random() < FUNGI_DENSITY * 3:  # Even higher chance in grotto
                                map_grid[y][x] = Tile(fungi, x, y)
                                # Assign random color for fungi (pink/maroon/magenta/purple shades)
                                fungi_color = random.choice([200, 201, 202, 203])
                                map_grid[y][x].set_color_override(fungi_color)
                            elif random.random() < MAGIC_FUNGI_DENSITY * 3:  # Even higher chance for magic fungi
                                map_grid[y][x] = Tile(magic_fungi_entity, x, y)
                                magic_fungi_locations.append((x, y))
            
            # Add exit point
            exit_x, exit_y = width // 2, 0
            map_grid[exit_y][exit_x] = Tile(stone_floor, exit_x, exit_y)
        elif sub_level == "mycelial_nexus_core": # Example for a Nexus Core sub-level
             # Generate organic mycelial structure using cellular automata
             initial_wall_chance = 0.25 # Initial density of walls
             automata_steps = 5        # Number of simulation steps
             birth_limit = 4           # A floor becomes a wall if >= birth_limit neighbours are walls
             survival_limit = 3        # A wall stays a wall if >= survival_limit neighbours are walls

             # Initialize with random walls/floors
             for y in range(height):
                 for x in range(width):
                     if random.random() < initial_wall_chance:
                         map_grid[y][x] = Tile(mycelium_wall, x, y)
                     else:
                         map_grid[y][x] = Tile(mycelium_floor, x, y)

             # Run automata steps
             for _ in range(automata_steps):
                 new_grid = copy.deepcopy(map_grid) # Work on a copy
                 for y in range(height):
                     for x in range(width):
                         wall_neighbors = 0
                         for dy in range(-1, 2):
                             for dx in range(-1, 2):
                                 if dx == 0 and dy == 0: continue # Skip self
                                 nx, ny = x + dx, y + dy
                                 # Check bounds and count walls (including boundary as wall)
                                 if 0 <= nx < width and 0 <= ny < height:
                                     if map_grid[ny][nx].entity == mycelium_wall:
                                         wall_neighbors += 1
                                 else:
                                     wall_neighbors += 1 # Treat borders as walls

                         # Apply CA rules
                         if map_grid[y][x].entity == mycelium_floor:
                             if wall_neighbors >= birth_limit:
                                 new_grid[y][x] = Tile(mycelium_wall, x, y)
                             else:
                                 new_grid[y][x] = Tile(mycelium_floor, x, y) # Already floor, stays floor
                         else: # It's a mycelium_wall
                             if wall_neighbors >= survival_limit:
                                 new_grid[y][x] = Tile(mycelium_wall, x, y) # Stays wall
                             else:
                                 new_grid[y][x] = Tile(mycelium_floor, x, y) # Dies -> becomes floor

                 map_grid = new_grid # Update map_grid for the next iteration

             # Ensure borders are walls for a contained feel
             for y in range(height):
                 for x in range(width):
                     if x == 0 or x == width - 1 or y == 0 or y == height - 1:
                          map_grid[y][x] = Tile(mycelium_wall, x, y)

             # Add magic fungi in open floor areas
             for y in range(1, height - 1):
                 for x in range(1, width - 1):
                      # Place on mycelium floor, potentially preferring larger open areas (check neighbours?)
                      if map_grid[y][x].entity == mycelium_floor and random.random() < MAGIC_FUNGI_DENSITY * 1.5: # Slightly adjusted density
                          map_grid[y][x] = Tile(magic_fungi_entity, x, y)
                          magic_fungi_locations.append((x, y))
        # Add other sub-level generation types here...
        else:
            # Default sub-level: simple cave
            for y in range(height):
                for x in range(width):
                    if random.random() < 0.45:
                        map_grid[y][x] = Tile(stone_wall, x, y)
                    else:
                        map_grid[y][x] = Tile(stone_floor, x, y)

    # --- Main level generation (Depth >= 0) ---
    else:
        # Generate initial stone walls using cellular automata
        if depth == 0:  # Surface level
            # First pass: random stone walls
            for y in range(height):
                for x in range(width):
                    if random.random() < 0.4:  # Initial stone density
                        map_grid[y][x] = Tile(stone_wall, x, y)
            
            # Cellular automata passes
            for _ in range(4):  # Number of smoothing passes
                # Create a deep copy to modify, preserving Tile objects
                new_grid = copy.deepcopy(map_grid)
                for y in range(height):
                    for x in range(width):
                        # Count adjacent stone walls
                        stone_count = 0
                        for dy in range(-1, 2):
                            for dx in range(-1, 2):
                                if dx == 0 and dy == 0:
                                    continue
                                nx, ny = x + dx, y + dy
                                if 0 <= nx < width and 0 <= ny < height:
                                    if map_grid[ny][nx].entity == stone_wall:
                                        stone_count += 1
                        
                        # Apply rules
                        if map_grid[y][x].entity == stone_wall:
                            new_grid[y][x] = Tile(stone_wall, x, y) if stone_count >= 4 else Tile(grass, x, y)
                        else:
                            new_grid[y][x] = Tile(stone_wall, x, y) if stone_count >= 5 else Tile(grass, x, y)
                
                map_grid = new_grid

            # Generate river
            river_width = 3  # Width of the river
            river_y = height // 2  # River runs horizontally through middle
            for x in range(width):
                for dy in range(-river_width//2, river_width//2 + 1):
                    y = river_y + dy
                    if 0 <= y < height:
                        map_grid[y][x] = Tile(water, x, y)
                        # Add some variation to river width
                        if random.random() < 0.3:
                            if 0 <= y-1 < height:
                                map_grid[y-1][x] = Tile(water, x, y-1)
                            if 0 <= y+1 < height:
                                map_grid[y+1][x] = Tile(water, x, y+1)

            # --- Create Shallow Fords ---
            # TODO: Define "shallow_water" in entities.py and ensure it's walkable
            shallow_water = ENTITY_REGISTRY.get("shallow_water", water) # Fallback to water if not defined yet
            num_fords = random.randint(1, 2)
            ford_xs = random.sample(range(width // 4, 3 * width // 4), num_fords) # Avoid edges

            for ford_x in ford_xs:
                for y in range(height):
                    if map_grid[y][ford_x].entity == water:
                        map_grid[y][ford_x] = Tile(shallow_water, ford_x, y)
            # --- End Ford Creation ---

            # Place trees and fungi
            for y in range(height):
                for x in range(width):
                    if map_grid[y][x].entity == grass:
                        # Place trees away from water
                        if not any(map_grid[ny][nx].entity == water 
                                 for ny in range(max(0, y-2), min(height, y+3))
                                 for nx in range(max(0, x-2), min(width, x+3))):
                            if random.random() < TREE_DENSITY:
                                map_grid[y][x] = Tile(tree, x, y)
                        
                        # Place fungi near water
                        if any(map_grid[ny][nx].entity == water 
                             for ny in range(max(0, y-1), min(height, y+2))
                             for nx in range(max(0, x-1), min(width, x+2))):
                            if random.random() < FUNGI_DENSITY * 2:  # Higher chance near water
                                map_grid[y][x] = Tile(fungi, x, y)
                                # Assign random color for fungi (pink/maroon/magenta/purple shades)
                                fungi_color = random.choice([200, 201, 202, 203])
                                map_grid[y][x].set_color_override(fungi_color)
                            elif random.random() < MAGIC_FUNGI_DENSITY * 2:  # Higher chance for magic fungi near water
                                map_grid[y][x] = Tile(magic_fungi_entity, x, y)
                                magic_fungi_locations.append((x, y))

        else:  # Underground levels
            # Generate stone walls using cellular automata
            for y in range(height):
                for x in range(width):
                    if random.random() < 0.45:  # Initial stone density
                        map_grid[y][x] = Tile(stone_wall, x, y)
            
            # Cellular automata passes
            for _ in range(4):  # Number of smoothing passes
                # Create a deep copy to modify, preserving Tile objects
                new_grid = copy.deepcopy(map_grid)
                for y in range(height):
                    for x in range(width):
                        # Count adjacent stone walls
                        stone_count = 0
                        for dy in range(-1, 2):
                            for dx in range(-1, 2):
                                if dx == 0 and dy == 0:
                                    continue
                                nx, ny = x + dx, y + dy
                                if 0 <= nx < width and 0 <= ny < height:
                                    if map_grid[ny][nx].entity == stone_wall:
                                        stone_count += 1
                        
                        # Apply rules
                        if map_grid[y][x].entity == stone_wall:
                            new_grid[y][x] = Tile(stone_wall, x, y) if stone_count >= 4 else Tile(stone_floor, x, y)
                        else:
                            new_grid[y][x] = Tile(stone_wall, x, y) if stone_count >= 5 else Tile(stone_floor, x, y)
                
                map_grid = new_grid

            # Generate water features in lower levels
            if depth >= 1:  # Start generating water from first underground level
                # Generate small ponds and streams
                for y in range(height):
                    for x in range(width):
                        if map_grid[y][x].entity == stone_floor:
                            # Create small ponds (very rare)
                            if random.random() < 0.002:  # 0.2% chance for pond
                                # Create a more natural-looking pond
                                pond_size = random.randint(1, 2)
                                center_x, center_y = x, y
                                for dy in range(-pond_size, pond_size + 1):
                                    for dx in range(-pond_size, pond_size + 1):
                                        nx, ny = center_x + dx, center_y + dy
                                        if 0 <= nx < width and 0 <= ny < height:
                                            # Use distance from center to create a more natural shape
                                            distance = (dx*dx + dy*dy)**0.5
                                            if distance <= pond_size and random.random() < 0.8:
                                                map_grid[ny][nx] = Tile(water, nx, ny)
                            # Create tiny streams (very rare)
                            elif random.random() < 0.001:  # 0.1% chance for stream start
                                stream_length = random.randint(3, 6)  # Even shorter streams
                                stream_x, stream_y = x, y
                                direction = random.choice([(1,0), (-1,0), (0,1), (0,-1)])  # Pick initial direction
                                for _ in range(stream_length):
                                    if 0 <= stream_x < width and 0 <= stream_y < height:
                                        map_grid[stream_y][stream_x] = Tile(water, stream_x, stream_y)
                                        # 80% chance to continue in same direction, 20% to change
                                        if random.random() < 0.8:
                                            stream_x += direction[0]
                                            stream_y += direction[1]
                                        else:
                                            direction = random.choice([(1,0), (-1,0), (0,1), (0,-1)])
                                            stream_x += direction[0]
                                            stream_y += direction[1]

            # Place fungi and magic fungi near water
            for y in range(height):
                for x in range(width):
                    if map_grid[y][x].entity == stone_floor:
                        # Check for nearby water
                        has_nearby_water = any(map_grid[ny][nx].entity == water 
                                            for ny in range(max(0, y-1), min(height, y+2))
                                            for nx in range(max(0, x-1), min(width, x+2)))
                        
                        if has_nearby_water:
                            if random.random() < FUNGI_DENSITY * 2:  # Higher chance near water
                                map_grid[y][x] = Tile(fungi, x, y)
                                # Assign random color for fungi (pink/maroon/magenta/purple shades)
                                fungi_color = random.choice([200, 201, 202, 203])
                                map_grid[y][x].set_color_override(fungi_color)
                            elif random.random() < MAGIC_FUNGI_DENSITY * 2:  # Higher chance for magic fungi near water
                                map_grid[y][x] = Tile(magic_fungi_entity, x, y)
                                magic_fungi_locations.append((x, y))

            # Place Grotto entry in lower levels only
            if depth >= 1 and grotto_entry and random.random() < 0.2:  # 20% chance to place grotto in underground levels
                # Find a suitable location
                valid_locations = []
                for y in range(1, height-1):
                    for x in range(1, width-1):
                        if map_grid[y][x].entity == stone_floor:
                            valid_locations.append((x, y))
                
                if valid_locations:
                    x, y = random.choice(valid_locations)
                    map_grid[y][x].entity = grotto_entry

        # --- Designate a Nexus build site ---
        # Define valid floor types for nexus sites
        valid_floor_types = {
            0: [grass],  # Surface level uses grass
            1: [stone_floor, mycelium_floor],  # Underground levels can use stone or mycelium
        }
        target_floors = valid_floor_types.get(depth, [stone_floor, mycelium_floor])  # Default to underground floors

        # Find all valid tiles for nexus placement
        valid_tiles = []
        for y in range(height):
            for x in range(width):
                if map_grid[y][x].entity in target_floors:
                    valid_tiles.append((x, y))

        # Place nexus site if we found valid tiles
        if valid_tiles:
            nx, ny = random.choice(valid_tiles)
            nexus_site = (nx, ny)
            # Clear a small area around the site
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    cx, cy = nx + dx, ny + dy
                    if 0 <= cx < width and 0 <= cy < height:
                        if not map_grid[cy][cx].walkable:
                            map_grid[cy][cx] = Tile(target_floors[0], cx, cy)  # Use first valid floor type
        else:
            # Fallback: Place in center if no valid tiles found
            nx, ny = width // 2, height // 2
            nexus_site = (nx, ny)
            map_grid[ny][nx] = Tile(target_floors[0], nx, ny)
            print(f"Warning: No valid tiles found for Nexus site at depth {depth}, using center")

    return map_grid, nexus_site, magic_fungi_locations

def generate_mycelial_network(map_grid: MapGrid, nexus_site: Tuple[int, int], magic_fungi_locations: List[Tuple[int, int]]) -> Dict[Tuple[int, int], List[Tuple[int, int]]]:
    """
    Generates a graph representing the mycelial network for a given map.

    The network connects the `nexus_site` to `magic_fungi_locations` via
    intermediate nodes placed on walkable tiles. Node placement probability
    is influenced by proximity to water, fungi, and the nexus.
    Connections are formed using a randomized spanning tree approach starting
    from the nexus to create organic-looking branches.

    Args:
        map_grid (MapGrid): The map grid for which to generate the network.
        nexus_site (Tuple[int, int]): The coordinates of the nexus site (root node).
        magic_fungi_locations (List[Tuple[int, int]]): Coordinates of magic fungi (leaf nodes).

    Returns:
        Dict[Tuple[int, int], List[Tuple[int, int]]]: An adjacency list representation
            of the network graph. Keys are node coordinates (x, y), and values are
            lists of connected node coordinates. Returns empty if no nexus site is provided.
    """
    network: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
    width = len(map_grid[0]) if map_grid else 0
    height = len(map_grid) if width > 0 else 0
    
    if not nexus_site or not height or not width:
        return network
    
    # Add the nexus as root node
    network[nexus_site] = []
    
    # Start BFS from nexus to find reachable nodes
    potential_nodes: List[Tuple[int, int]] = [] # Nodes part of the main map structure (fungi, etc.)
    
    # Potential nodes include magic fungi locations and tiles adjacent to fungi/magic fungi
    for y in range(height):
        for x in range(width):
            if map_grid[y][x].walkable:
                # Higher chance near water or existing fungi
                has_nearby_water = any(
                    0 <= ny < height and 0 <= nx < width and map_grid[ny][nx].entity.name == "water"
                    for ny in range(max(0, y-2), min(height, y+3))
                    for nx in range(max(0, x-2), min(width, x+3))
                )
                
                has_nearby_fungi = any(
                    0 <= ny < height and 0 <= nx < width and map_grid[ny][nx].entity.name in ["fungi", "magic_fungi"]
                    for ny in range(max(0, y-2), min(height, y+3))
                    for nx in range(max(0, x-2), min(width, x+3))
                )
                
                # Probability based on proximity to water/fungi and distance from nexus
                dist_to_nexus = abs(x - nexus_site[0]) + abs(y - nexus_site[1])
                prob = 0.1  # Base probability
                if has_nearby_water:
                    prob += 0.3
                if has_nearby_fungi:
                    prob += 0.3
                
                # Probability decreases with distance from nexus
                prob = max(0.02, prob - (dist_to_nexus * 0.01))
                
                # Avoid nodes too close to each other
                too_close_to_existing = any(
                    abs(x - nx) + abs(y - ny) < 3
                    for nx, ny in potential_nodes + [nexus_site]
                )
                
                if not too_close_to_existing and random.random() < prob:
                    potential_nodes.append((x, y))
                    network[(x, y)] = []
            
            # Early exit if we've reached our node limit
            if len(potential_nodes) >= int(width * height * 0.2):
                break
    
    # Add all magic fungi as leaf nodes
    for x, y in magic_fungi_locations:
        if (x, y) not in network:
            network[(x, y)] = []
    
    # Generate connections using a modified spanning tree algorithm
    # Start from nexus and branch out organically
    def connect_nodes(start_node, available_nodes, max_connections=3):
        if not available_nodes:
            return
        
        # Sort by distance to start_node
        available_nodes.sort(key=lambda n: abs(n[0] - start_node[0]) + abs(n[1] - start_node[1]))
        
        # Connect to closest nodes with some randomness
        connections = 0
        for node in available_nodes[:10]:  # Consider closest 10
            if node != start_node and random.random() < 0.4 and connections < max_connections:  # Reduced connection probability
                # Add bidirectional connection
                network[start_node].append(node)
                network[node].append(start_node)
                connections += 1
                
                # Recursively connect from this node with lower max_connections
                # to create a branching effect
                next_max = max(1, max_connections - 1)
                remaining = [n for n in available_nodes if n != node]
                connect_nodes(node, remaining, max_connections=next_max)
    
    # Start connections from nexus
    all_nodes = list(network.keys())
    all_nodes.remove(nexus_site)  # Don't include nexus in available nodes
    connect_nodes(nexus_site, all_nodes, max_connections=3)  # Fewer connections from nexus
    
    return network


