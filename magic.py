# magic.py
"""Handles spell definitions, casting logic, and spell effects.

Defines individual spell effects, a central `spells` dictionary mapping spell names
to their properties (cost, effects, AOE), and the main `cast_spell` function
which verifies costs and applies effects based on the game state and cursor position.
"""
import random
from typing import TYPE_CHECKING, List, Tuple, Dict, Callable, Optional, TypedDict, Union, Set, cast

# Update imports to relative
from .lore import lore_base
from .constants import MAP_WIDTH, MAP_HEIGHT

# Use relative imports for sibling modules
from .player import Player
from .tiles import Tile, ENTITY_REGISTRY, GameEntity # Need registry and entity type
from .game_state import GameState # Need game state type

# Import entity types needed for runtime checks
from .characters import Dwarf, Animal, NPC # Corrected import path
from .entities import ResourceNode, Structure # Ensure these are imported

# Import a_star_for_illumination and find_path_on_network
from .utils import bresenham_line, a_star_for_illumination, find_path_on_network

if TYPE_CHECKING:
    # Avoid circular import - these types are only needed for hints
    # from .entities import Dwarf, Animal, NPC # Moved outside
    from .game_state import GameState # GameState is needed here too

# Define types for spell effects
# Forward references ('GameState', 'Tile', etc.) are used as strings
# Actual entity types are now imported and can be used directly
TileEffect = Callable[['Tile', 'GameState'], None]
EntityEffect = Callable[[Union[Dwarf, Animal, NPC]], None] # Use imported types
VisualEffect = Callable[['Tile'], None]
SpecialEffect = Callable[['GameState'], str]

# Define the structure of a spell dictionary using TypedDict
# total=False means keys are optional
class SpellDefinition(TypedDict, total=False):
    cost: int
    aoe_radius: int
    visual_effect: VisualEffect
    tile_effect: TileEffect
    entity_effect: EntityEffect
    special_effect: SpecialEffect


magic_system = lore_base["magic"]

def fungal_bloom_effect(tile: 'Tile', game: 'GameState'):
    """Applies the Fungal Bloom spell effect to a single tile.

    This function is called by `cast_spell` for each tile within the AOE.
    It handles:
    - Converting fungi to magic fungi near water.
    - Converting floor/grass tiles to regular fungi.
    - Potentially adding the affected tile to the mycelial network or strengthening
      connections if near existing nodes (modifies `game.mycelial_network` and
      triggers recalculation of `game.network_distances`).

    Args:
        tile (Tile): The map tile being affected by the spell.
        game (GameState): The current game state, used for accessing map, entities,
                          network, and adding debug messages.
    """
    # Get required entities from the registry, marking them as Optional
    fungi_entity: Optional[GameEntity] = ENTITY_REGISTRY.get("fungi")
    magic_fungi_entity: Optional[GameEntity] = ENTITY_REGISTRY.get("magic_fungi")
    grass_entity: Optional[GameEntity] = ENTITY_REGISTRY.get("grass")
    stone_floor_entity: Optional[GameEntity] = ENTITY_REGISTRY.get("stone_floor")
    mycelium_floor_entity: Optional[GameEntity] = ENTITY_REGISTRY.get("mycelium_floor")
    tree_entity: Optional[GameEntity] = ENTITY_REGISTRY.get("tree") # Get tree entity
    # water_entity is checked by name, no need to fetch the object here

    # 1. BASIC FUNGI CONVERSION LOGIC

    # Check for water and trees nearby
    has_nearby_water = False
    has_nearby_tree = False
    nearby_radius = 2 # Check within 2 tiles

    for dx in range(-nearby_radius, nearby_radius + 1):
        for dy in range(-nearby_radius, nearby_radius + 1):
            # Skip the center tile itself
            if dx == 0 and dy == 0:
                continue
            neighbor_tile = game.get_tile(tile.x + dx, tile.y + dy)
            if neighbor_tile and neighbor_tile.entity:
                if neighbor_tile.entity.name == "water":
                    has_nearby_water = True
                elif neighbor_tile.entity == tree_entity: # Check against the entity object
                    has_nearby_tree = True
            # Early exit if both found
            if has_nearby_water and has_nearby_tree:
                break
        if has_nearby_water and has_nearby_tree:
            break

    # Handle conversion logic
    if tile.entity == fungi_entity and fungi_entity is not None and magic_fungi_entity is not None:
        base_prob = 0.10 # Base 10% chance to convert 'f' to 'F'
        if has_nearby_water:
            base_prob += 0.30 # Add 30% if near water
        if has_nearby_tree:
            base_prob += 0.20 # Add 20% if near tree

        # Ensure probability doesn't exceed a cap (e.g., 90%)
        conversion_prob = min(base_prob, 0.90)

        if random.random() < conversion_prob:
            tile.entity = magic_fungi_entity
            if hasattr(game, 'magic_fungi_locations'):
                magic_fungi_loc = (tile.x, tile.y)
                if magic_fungi_loc not in game.magic_fungi_locations:
                    game.magic_fungi_locations.append(magic_fungi_loc)
            game.add_debug_message(f"Fungal Bloom: Converted fungi to magic fungi at ({tile.x}, {tile.y}) with prob {conversion_prob:.2f}")

    # Convert grass/stone floor/mycelium floor to fungi
    elif tile.entity in [grass_entity, stone_floor_entity, mycelium_floor_entity] and random.random() < 0.3 and fungi_entity is not None:
        # Ensure tile isn't occupied by a living entity before converting
        # Need to check against actual types here too
        if not any(isinstance(e, (Dwarf, Animal, NPC)) and e.x == tile.x and e.y == tile.y and getattr(e, 'alive', True)
                   for e in game.dwarves + game.animals + game.characters):
            tile.entity = fungi_entity # Assignment is safe now
            game.add_debug_message(f"Fungal Bloom: Created fungi at ({tile.x}, {tile.y})")

    # 2. MYCELIAL NETWORK ENHANCEMENT
    # Only proceed if we're near the mycelial network and the network exists
    if game.mycelial_network and game.nexus_site:
        tile_pos = (tile.x, tile.y)
        existing_nodes = list(game.mycelial_network.keys())

        # Find nearby nodes (within 5 tiles using Manhattan distance)
        nearby_nodes = [
            node for node in existing_nodes
            if abs(node[0] - tile.x) + abs(node[1] - tile.y) <= 5
        ]

        if nearby_nodes:
            # 50% chance to potentially enhance the network at this tile
            if random.random() < 0.5:
                is_new_node = tile_pos not in game.mycelial_network

                # Only add walkable tiles as network nodes
                if tile.walkable:
                    if is_new_node:
                        game.mycelial_network[tile_pos] = []

                    # Connect to up to 2 random nearby existing nodes
                    connect_nodes = random.sample(nearby_nodes, min(2, len(nearby_nodes)))
                    for node in connect_nodes:
                        # Ensure bidirectional connection without duplicates
                        if node not in game.mycelial_network[tile_pos]:
                            game.mycelial_network[tile_pos].append(node)
                        if tile_pos not in game.mycelial_network[node]:
                            game.mycelial_network[node].append(tile_pos)

                    if is_new_node:
                        # Recalculate network distances if a new node was added
                        game.network_distances = game.calculate_network_distances()
                        game.add_debug_message(f"Fungal Bloom: Enhanced mycelial network at ({tile.x}, {tile.y})")
                        # Visual feedback: make the new node pulse briefly
                        tile.pulse_ticks = 15
                        tile.set_color_override(206) # Bright pink

def reveal_mycelial_network(game: 'GameState') -> str:
    """Highlights the entire mycelial network on the current map.

    This is a special spell effect, not tied to AOE. It performs a BFS from the
    nexus site to find all reachable network nodes and their paths.
    It then applies visual effects (pulsing, color overrides) to tiles belonging
    to the network nodes and the paths connecting them, using Bresenham's line
    algorithm for path segments.
    Effects decay over time, fading from the edges towards the nexus.

    Args:
        game (GameState): The current game state, used for accessing the map,
                          network data, nexus site, and applying tile effects.

    Returns:
        str: A message indicating success or failure (e.g., "No network detected!").
    """
    if not game.mycelial_network or not game.nexus_site:
        return "No mycelial network detected!"

    all_paths: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
    max_distance = 0

    # Start BFS from the nexus
    queue: List[Tuple[Tuple[int, int], List[Tuple[int, int]]]] = [(game.nexus_site, [game.nexus_site])]
    visited: Set[Tuple[int, int]] = {game.nexus_site}

    while queue:
        current, path = queue.pop(0)
        all_paths[current] = path
        current_distance = len(path) - 1
        max_distance = max(max_distance, current_distance)

        for next_node in game.mycelial_network.get(current, []):
            if next_node not in visited:
                visited.add(next_node)
                queue.append((next_node, path + [next_node]))

    # Include nodes not reachable from nexus (if any exist) to show the full network
    for node in game.mycelial_network:
        if node not in all_paths:
            all_paths[node] = [node] # Path is just the node itself

    mycelium_colors = [5, 13, 201, 206] # Purple, Bright Magenta, Pink variants

    # Clear existing visual effects from all tiles
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            tile = game.get_tile(x, y)
            if tile:
                tile.highlight_ticks = 0
                tile.flash_ticks = 0
                tile.pulse_ticks = 0
                tile.set_color_override(None)

    # Apply special effect to the nexus tile
    nexus_tile = game.get_tile(game.nexus_site[0], game.nexus_site[1])
    if nexus_tile:
        nexus_tile.pulse_ticks = 250
        nexus_tile.set_color_override(16) # Bright Magenta for nexus

    # Store network distance for each node
    node_distances: Dict[Tuple[int, int], int] = {}
    for node, path in all_paths.items():
        distance = len(path) - 1
        node_distances[node] = distance

    base_duration = 200

    # Apply effects to each node based on distance from nexus
    for node, path in all_paths.items():
        if node == game.nexus_site: continue

        tile = game.get_tile(node[0], node[1])
        if not tile: continue

        distance = node_distances.get(node, 0) # Use .get for safety
        color_index = distance % len(mycelium_colors)
        color = mycelium_colors[color_index]

        # Duration decreases with distance for fade-out effect
        duration = max(50, base_duration - (distance * 3))

        tile.pulse_ticks = duration
        tile.set_color_override(color)

        # Enhance effect for magic fungi tiles (check entity exists)
        if tile.entity and tile.entity.name == "magic_fungi":
            tile.pulse_ticks = duration + 50
            tile.set_color_override(16) # Bright Magenta

    # Draw and highlight connections between nodes
    already_processed_connections: Set[Tuple[Tuple[int, int], Tuple[int, int]]] = set()

    for node, connections in game.mycelial_network.items():
        node_distance = node_distances.get(node, 0)

        for connected_node in connections:
            # Use a sorted tuple as the key to avoid duplicates regardless of order
            # Explicitly cast to satisfy mypy, though types should match
            connection_key = cast(Tuple[Tuple[int, int], Tuple[int, int]], tuple(sorted((node, connected_node))))
            if node == connected_node or connection_key in already_processed_connections:
                continue
            already_processed_connections.add(connection_key)

            connected_distance = node_distances.get(connected_node, 0)
            # Use the distance of the node *further* from the nexus for path effects
            max_node_distance = max(node_distance, connected_distance)

            # Get points along the line between nodes
            line_path = bresenham_line(node[0], node[1], connected_node[0], connected_node[1])

            # Apply effects to tiles along the path (excluding endpoints)
            for i, (px, py) in enumerate(line_path):
                if (px, py) == node or (px, py) == connected_node: continue

                path_tile = game.get_tile(px, py)
                if path_tile: # Allow highlighting non-walkable path segments like water
                    path_pos_ratio = i / max(1, len(line_path) - 1) # Position along path [0, 1]

                    # Duration based on max node distance, fading from edges
                    path_duration = max(50, base_duration - (max_node_distance * 3))
                    path_duration += int(path_pos_ratio * 20) # Slight variation along path

                    # Longer duration for paths touching fungi/magic fungi (check entity exists)
                    if path_tile.entity and path_tile.entity.name in ["fungi", "magic_fungi"]:
                        path_duration += 30

                    path_tile.highlight_ticks = path_duration # Controls effect duration
                    # Cycle colors along the path
                    color_offset = (i % len(mycelium_colors))
                    path_tile.set_color_override(mycelium_colors[color_offset])

    game.add_debug_message(f"Revealed mycelial network with {len(all_paths)} nodes. Decay from edges inward.")
    return "Mycelial network revealed! Watch as it pulses with fungal life!"

# Define the spells dictionary using the SpellDefinition TypedDict
spells: Dict[str, SpellDefinition] = {
    "Spore Cloud": {
        "cost": 10,
        "aoe_radius": 3,
        "visual_effect": lambda tile: setattr(tile, 'flash_ticks', 20),
        "entity_effect": lambda entity: setattr(entity, 'health', entity.health - 10) if hasattr(entity, 'health') else None
    },
    "Fungal Bloom": {
        "cost": 15,
        "aoe_radius": 5,
        # Check if tile.entity exists before accessing its name
        "visual_effect": lambda tile: setattr(tile, 'pulse_ticks', 5) if tile.entity and tile.entity.name == 'Grass' else None,
        "tile_effect": fungal_bloom_effect
    },
    "Reveal Mycelium": {
        "cost": 15,
        # aoe_radius is not used, but setting to 0 for completeness
        "aoe_radius": 0,
        "special_effect": reveal_mycelial_network
    }
}

def cast_spell(spell_name: str, game: 'GameState') -> str:
    """Attempts to cast a spell, checking cost and applying effects."""
    if spell_name not in spells:
        return f"Spell {spell_name} not found!"

    spell = spells[spell_name] # spell is now known to be SpellDefinition

    if spell_name not in game.player.spells:
        return f"Spell {spell_name} not learned!"

    # Check cost using .get() for safety, though 'cost' should ideally always be present
    cost = spell.get("cost", 9999) # Default to a high cost if missing
    if game.player.spore_exposure >= cost:
        game.player.spore_exposure -= cost

        # Handle special effects first
        special_effect = spell.get("special_effect")
        if special_effect:
            # Type checker knows special_effect is Callable[['GameState'], str] here
            return special_effect(game)

        # Handle AOE effects
        cx, cy = game.cursor_x, game.cursor_y
        aoe_radius = spell.get("aoe_radius", 0) # Default to 0 if missing

        # Pre-fetch effect functions using .get() - returns None if key is absent
        visual_effect = spell.get("visual_effect")
        tile_effect = spell.get("tile_effect")
        entity_effect = spell.get("entity_effect")

        # Define the types affected by entity_effect *once* outside the loop
        # These types (Dwarf, Animal, NPC) are now imported normally
        AffectedEntityTypes = (Dwarf, Animal, NPC)

        for y in range(max(0, cy - aoe_radius), min(MAP_HEIGHT, cy + aoe_radius + 1)):
            for x in range(max(0, cx - aoe_radius), min(MAP_WIDTH, cx + aoe_radius + 1)):
                # Check distance using the correctly typed aoe_radius
                if (x - cx)**2 + (y - cy)**2 <= aoe_radius**2:
                    tile = game.get_tile(x, y)
                    if tile:
                        # Apply effects if the functions exist
                        if visual_effect:
                            visual_effect(tile)
                        if tile_effect:
                            tile_effect(tile, game)
                        if entity_effect:
                            # Apply entity effect to relevant entities on the tile
                            # Check against the pre-defined tuple of types
                            for entity in game.dwarves + game.animals + game.characters:
                                if isinstance(entity, AffectedEntityTypes) and entity.x == x and entity.y == y and getattr(entity, 'alive', True):
                                    # Type checker knows entity_effect is Callable[[Union[Dwarf, Animal, NPC]], None] here
                                    entity_effect(entity)

        game.add_debug_message(f"Cast {spell_name}")
        return f"{spell_name} cast successfully!"
    else:
        return "Insufficient spore exposure!"

def expose_to_spores(game: 'GameState', amount: int):
    """Increases player spore exposure."""
    game.player.spore_exposure += amount

def highlight_path_to_nexus(game: 'GameState', magic_fungi_location: Tuple[int, int]) -> str:
    """Highlights a path ALONG THE MYCELIAL NETWORK from a magic fungus to the nexus.

    Uses BFS on the mycelial network graph. Visualizes segments with Bresenham's line.

    Args:
        game (GameState): The current game state.
        magic_fungi_location (Tuple[int, int]): The (x,y) coords of the harvested magic fungus.

    Returns:
        str: A message indicating success or failure.
    """
    if not game.mycelial_network or not game.nexus_site:
        # It's crucial that nexus_site is part of the mycelial_network keys for this to work
        return "No mycelial network or nexus site detected to highlight path!"

    # Determine the starting node for pathfinding on the network.
    # If the magic_fungi_location itself is a network node, use it.
    # Otherwise, find the closest network node to the magic fungus.
    start_node_for_network_path = None
    if magic_fungi_location in game.mycelial_network:
        start_node_for_network_path = magic_fungi_location
    else:
        min_dist = float('inf')
        closest_node = None
        for node_coord in game.mycelial_network.keys():
            dist = abs(node_coord[0] - magic_fungi_location[0]) + abs(node_coord[1] - magic_fungi_location[1])
            if dist < min_dist:
                min_dist = dist
                closest_node = node_coord
        
        if closest_node:
            game.add_debug_message(f"Magic fungus at {magic_fungi_location} not a direct network node. Pathing from closest node: {closest_node}")
            start_node_for_network_path = closest_node
        else:
            return f"Magic fungus at {magic_fungi_location} is not near any mycelial network nodes."
    
    if not start_node_for_network_path:
         return f"Could not determine a starting network node for illumination from {magic_fungi_location}."

    # Find path on the network graph from the determined start node to the nexus site
    network_path_nodes = find_path_on_network(game.mycelial_network, start_node_for_network_path, game.nexus_site)

    if not network_path_nodes:
        return f"No path found in mycelial network from {start_node_for_network_path} to nexus {game.nexus_site}."

    # DO NOT Clear existing visual effects to allow multiple paths
    # for y_coord in range(MAP_HEIGHT):
    #     for x_coord in range(MAP_WIDTH):
    #         tile = game.get_tile(x_coord, y_coord)
    #         if tile:
    #             tile.highlight_ticks = 0
    #             tile.flash_ticks = 0
    #             tile.pulse_ticks = 0
    #             tile.set_color_override(None)
    
    path_colors = [16, 206, 13, 5] # Bright Magenta, Pink, Dark Magenta, Cyan/Blue
    water_highlight_color = 6 # Magenta for water
    reveal_duration = 75 # Duration for the initial static path reveal

    # Apply a static highlight for the initial reveal
    all_highlighted_tiles_on_path = set()
    for node_coord in network_path_nodes:
        all_highlighted_tiles_on_path.add(node_coord)

    for i in range(len(network_path_nodes) - 1):
        node1 = network_path_nodes[i]
        node2 = network_path_nodes[i+1]
        line_segment_tiles = bresenham_line(node1[0], node1[1], node2[0], node2[1])
        for seg_tile_coord in line_segment_tiles:
            all_highlighted_tiles_on_path.add(seg_tile_coord)

    for i, tile_coord in enumerate(list(all_highlighted_tiles_on_path)):
        tile = game.get_tile(tile_coord[0], tile_coord[1])
        if not tile: continue

        current_color = path_colors[i % len(path_colors)]
        is_water_tile = tile.entity and tile.entity.name == "Water"

        if is_water_tile:
            current_color = water_highlight_color
        
        tile.set_color_override(current_color)
        tile.highlight_ticks = reveal_duration # Use highlight_ticks for the static reveal

        # Special emphasis for start (fungus location or closest node) and end (nexus)
        if tile_coord == start_node_for_network_path:
            if start_node_for_network_path == magic_fungi_location:
                 tile.set_color_override(14) # Bright Red for the actual fungus
            else:
                 tile.set_color_override(path_colors[0])
            tile.highlight_ticks = reveal_duration + 25 # Slightly longer for terminals
        elif tile_coord == game.nexus_site:
             tile.set_color_override(16) # Bright Magenta for nexus
             tile.highlight_ticks = reveal_duration + 25 # Slightly longer for terminals

    # After initial reveal, initiate the pulsing effect
    initiate_nexus_pulse(game, network_path_nodes, start_node_for_network_path) # NEW FUNCTION CALL

    path_display = [(x,y) for x,y in network_path_nodes]
    game.add_debug_message(f"Revealed mycelial network path ({len(path_display)} nodes) from {start_node_for_network_path} to nexus: {path_display}")
    magic_fungi_entity = ENTITY_REGISTRY.get('magic_fungi')
    fungi_name = magic_fungi_entity.name if magic_fungi_entity else "Magic Fungus"
    return f"A path from the {fungi_name} (near {start_node_for_network_path}) to the Nexus ({game.nexus_site}) now reveals itself!"

def initiate_nexus_pulse(game: 'GameState', path_nodes: List[Tuple[int, int]], fungus_node: Tuple[int, int]):
    """Initiates a series of pulses from the nexus along the given path.

    Args:
        game (GameState): The current game state.
        path_nodes (List[Tuple[int, int]]): The list of coordinates representing the path
                                          from the fungus (or nearest network node) to the nexus.
                                          Important: This path is FROM FUNGUS TO NEXUS.
        fungus_node (Tuple[int, int]): The coordinate of the fungus or its closest network node.
    """
    if not game.nexus_site or not path_nodes:
        return

    # The provided path_nodes is from fungus_node to nexus_site.
    # For pulsing from nexus to fungus, we need to reverse it.
    # However, the visual effect is that the *signal* goes from fungus to nexus (path reveal),
    # and then *energy* pulses from nexus back to fungus.
    # So, the path for pulsing should indeed be from nexus to fungus.

    pulse_path_nexus_to_fungus = list(reversed(path_nodes))

    if not pulse_path_nexus_to_fungus or pulse_path_nexus_to_fungus[0] != game.nexus_site:
        game.add_debug_message(f"Pulse Error: Path for pulsing does not start at nexus. Nexus: {game.nexus_site}, Path Start: {pulse_path_nexus_to_fungus[0] if pulse_path_nexus_to_fungus else 'Empty'}")
        return

    path_length = len(pulse_path_nexus_to_fungus)
    if path_length == 0:
        return

    num_sends = 3 + (path_length // 5)  # e.g., 3 base pulses, +1 for every 5 path segments
    pulse_speed = 3  # Ticks per tile
    pulse_length = 3 # How many tiles the pulse occupies visually
    pulse_color = 201 # Example: Pinkish color for the pulse itself

    # Ensure there's a game.active_pulses attribute
    if not hasattr(game, 'active_pulses'):
        game.active_pulses = []

    new_pulse_id = f"pulse_{game.tick}_{fungus_node[0]}_{fungus_node[1]}"

    # Create the pulse object using the ActivePulse structure
    # Note: current_tile_index starts at 0 (the nexus)
    # tiles_to_render will be populated by the game logic update
    new_pulse = {
        "id": new_pulse_id,
        "path": pulse_path_nexus_to_fungus, 
        "current_tile_index": 0, 
        "ticks_on_current_tile": 0,
        "pulse_speed": pulse_speed,
        "pulse_color": pulse_color,
        "remaining_sends": num_sends,
        "tiles_to_render": [],
        "pulse_length": pulse_length
    }
    game.active_pulses.append(new_pulse)
    game.add_debug_message(f"Initiated pulse series: {new_pulse_id} ({num_sends} sends) from nexus to {fungus_node} along path of {path_length} nodes.")

# Removed __main__ block as it's not type-safe without significant test setup
