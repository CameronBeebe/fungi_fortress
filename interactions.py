# interactions.py
"""This module centralizes specific interaction and entry logic functions
that are assigned to Structure and Sublevel entities.

These functions are typically called when the player interacts ('e' key)
with the corresponding entity on the map.
"""
import random
from typing import TYPE_CHECKING

# Relative imports needed for the logic
from .constants import MAP_WIDTH, MAP_HEIGHT
# REMOVED top-level import to break cycle
# from .map_generation import generate_map, generate_mycelial_network

# Need Tile for type hints and potentially accessing tile properties
# Need Entity types for type hints
# Need GameState for type hints and modifying state

if TYPE_CHECKING:
    from .tiles import Tile
    from .entities import Structure, Sublevel
    from .game_state import GameState
    # Import for type checking if needed elsewhere, but avoid runtime import
    from .map_generation import generate_map, generate_mycelial_network

# --- Interaction/Entry Logic Functions ---

def enter_sublevel_logic(game_state: 'GameState', tile: 'Tile', sublevel: 'Sublevel'):
    """Handles the player attempting to enter a specific sublevel.

    This function is intended to be called via player interaction ('e' key)
    on a `Sublevel` entity. It assumes the sublevel's map has already been
    generated and stored in `game_state.sub_levels`.

    It activates the sublevel, switches the active map, updates the active
    mycelial network and related data, repositions the player cursor and dwarves,
    and updates the player's location state.

    Note: Dwarf entry into sublevels is handled separately by `GameLogic._trigger_sublevel_entry`
    when an 'enter' task is completed.

    Args:
        game_state (GameState): The main game state object.
        tile (Tile): The specific tile containing the `Sublevel` entity being entered.
        sublevel (Sublevel): The `Sublevel` entity instance itself.
    """
    # REMOVE local import
    # from .map_generation import generate_map
    
    sub_level_name = sublevel.name
    
    # Check if sublevel data exists and has a map pre-generated
    if sub_level_name in game_state.sub_levels and game_state.sub_levels[sub_level_name].get("map"):
        sub_level_data = game_state.sub_levels[sub_level_name]
        sub_level_data["active"] = True
        game_state.map = sub_level_data["map"]
        
        # Set the mycelial network for the sublevel if it exists
        if "mycelial_network" in sub_level_data:
            game_state.mycelial_network = sub_level_data["mycelial_network"]
            game_state.nexus_site = sub_level_data.get("nexus_site")
            game_state.magic_fungi_locations = sub_level_data.get("magic_fungi_locations", [])
            # Recalculate network distances with the sublevel's network
            game_state.network_distances = game_state.calculate_network_distances()
        
        game_state.entry_x, game_state.entry_y = game_state.cursor_x, game_state.cursor_y
        entry_pos_x, entry_pos_y = MAP_WIDTH // 2, MAP_HEIGHT // 2 # Default entry pos
        game_state.cursor_x, game_state.cursor_y = entry_pos_x, entry_pos_y
        for dwarf in game_state.dwarves:
            dwarf.x, dwarf.y = entry_pos_x + random.randint(-1, 1), entry_pos_y + random.randint(-1, 1)
        game_state.player.update_state("location", sub_level_name)
        game_state.add_debug_message(f"Entered {sub_level_name}")
    else:
        # This case should ideally not happen if the calling code pre-generates the map
        game_state.add_debug_message(f"Error: Tried to enter {sub_level_name}, but map was not pre-generated.")

def interact_mycelial_nexus_logic(game_state: 'GameState', tile: 'Tile', structure: 'Structure'):
    """Specific interaction logic triggered when the player interacts with the Mycelial Nexus.

    Handles generating and entering the 'Mycelial Nexus Core' sublevel.

    Args:
        game_state (GameState): The main game state object.
        tile (Tile): The tile containing the Mycelial Nexus structure.
        structure (Structure): The Mycelial Nexus structure instance.
    """
    # --- Local import to break circular dependency ---
    from .map_generation import generate_map, generate_mycelial_network
    # --- End Local import ---
    
    # --- Adapted Sublevel Entry Logic ---
    sub_level_name = "Mycelial Nexus Core" # Target sublevel for the built Nexus
    entry_x, entry_y = tile.x, tile.y # Coordinates of the Nexus structure itself

    # Ensure sub-level state exists
    if sub_level_name not in game_state.sub_levels:
        game_state.sub_levels[sub_level_name] = {"active": False, "map": None, "nexus_site": None, "magic_fungi_locations": None, "mycelial_network": None}

    # Generate map IF it doesn't exist yet
    if not game_state.sub_levels[sub_level_name].get("map"):
        game_state.add_debug_message(f"Generating map for {sub_level_name}...")
        # Use generate_map, assuming it can handle the sublevel name identifier
        map_grid, nexus_site, magic_fungi_locations = generate_map(
            MAP_WIDTH, MAP_HEIGHT,
            depth=-1, # Indicate sublevel depth
            mission=game_state.mission, # Pass current mission if relevant
            sub_level=sub_level_name.lower().replace(" ", "_") # Pass sublevel type identifier
        )
        if map_grid: # Check if generation succeeded
            game_state.sub_levels[sub_level_name]["map"] = map_grid
            # Nexus Core might not have its own "nexus_site" in the same way
            game_state.sub_levels[sub_level_name]["nexus_site"] = nexus_site
            game_state.sub_levels[sub_level_name]["magic_fungi_locations"] = magic_fungi_locations
            # Generate mycelial network for the new sublevel map (if applicable)
            # Core might have a specific network or none needed
            if nexus_site is not None:
                mycelial_network = generate_mycelial_network(map_grid, nexus_site, magic_fungi_locations)
                game_state.sub_levels[sub_level_name]["mycelial_network"] = mycelial_network
                game_state.add_debug_message(f"Mycelial network generated for {sub_level_name}.")
            else:
                game_state.add_debug_message(f"No specific nexus site in {sub_level_name}, skipping mycelial network generation.")
                game_state.sub_levels[sub_level_name]["mycelial_network"] = None # Ensure it's explicitly None
            game_state.add_debug_message(f"Map generated for {sub_level_name}.")
        else:
            game_state.add_debug_message(f"Error: Map generation failed for {sub_level_name}. Cannot enter.")
            return # Abort entry if map generation fails

    # Check again if map exists after attempting generation
    if not game_state.sub_levels[sub_level_name].get("map"):
        game_state.add_debug_message(f"Error: Sublevel map for {sub_level_name} still missing after generation attempt.")
        return

    # --- Proceed with Entry ---
    game_state.add_debug_message(f"Player interacting with {structure.name}, entering {sub_level_name} at ({entry_x}, {entry_y})...")
    game_state.sub_levels[sub_level_name]["active"] = True
    game_state.map = game_state.sub_levels[sub_level_name]["map"] # Switch to sublevel map

    # Store the entry point coordinates to return to later (the Nexus location on main map)
    game_state.entry_x, game_state.entry_y = entry_x, entry_y

    # Update Player State
    game_state.player.update_state("location", sub_level_name)

    # Update game state's active mycelial network and distances (if applicable for the core)
    sub_level_network = game_state.sub_levels[sub_level_name].get("mycelial_network")
    if isinstance(sub_level_network, dict):
        game_state.mycelial_network = sub_level_network
    else:
        game_state.mycelial_network = {} # Default to empty if no network or invalid
        if sub_level_network is not None:
             game_state.add_debug_message(f"Warning: Invalid mycelial network data found for {sub_level_name}, using empty network.")

    game_state.network_distances = game_state.calculate_network_distances() # Recalculate for the new map/network

    # Move dwarf(s) to a valid starting position within the sublevel
    spawn_found = False
    center_x, center_y = MAP_WIDTH // 2, MAP_HEIGHT // 2
    for r in range(max(MAP_WIDTH, MAP_HEIGHT) // 2): # Search outwards from center
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if abs(dx) != r and abs(dy) != r: continue # Only check perimeter
                nx, ny = center_x + dx, center_y + dy
                if 0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT and game_state.map[ny][nx].walkable:
                    # Move all dwarves to this spawn point (or slightly offset)
                    for i, d in enumerate(game_state.dwarves):
                        offset_x = random.randint(-1, 1)
                        offset_y = random.randint(-1, 1)
                        final_x = max(0, min(MAP_WIDTH - 1, nx + offset_x))
                        final_y = max(0, min(MAP_HEIGHT - 1, ny + offset_y))
                        # Ensure offset position is also walkable
                        if game_state.map[final_y][final_x].walkable:
                            d.x, d.y = final_x, final_y
                        else:
                            d.x, d.y = nx, ny # Fallback to original spawn point
                        # Reset dwarf state upon entering a new area via interaction
                        d.state = 'idle'
                        d.path = []
                        d.task = None
                    game_state.cursor_x, game_state.cursor_y = nx, ny # Move cursor too
                    spawn_found = True
                    break
            if spawn_found: break
        if spawn_found: break

    if not spawn_found:
         game_state.add_debug_message(f"Warning: No walkable spawn point found in {sub_level_name}. Placing at center.")
         fallback_x, fallback_y = MAP_WIDTH // 2, MAP_HEIGHT // 2
         for d in game_state.dwarves:
             d.x, d.y = fallback_x, fallback_y
             d.state = 'idle'
             d.path = []
             d.task = None
         game_state.cursor_x, game_state.cursor_y = fallback_x, fallback_y

    game_state.add_debug_message(f"Entered {sub_level_name}.")
    # --- End Adapted Logic ---

def interact_dwarven_sporeforge_logic(game_state: 'GameState', tile: 'Tile', structure: 'Structure'):
    """Specific interaction logic triggered when the player interacts with the Dwarven Sporeforge.

    Currently logs a placeholder message. Future implementation should handle
    Sporeforge-specific UI (e.g., crafting) or game mechanics.

    Args:
        game_state (GameState): The main game state object.
        tile (Tile): The tile containing the Dwarven Sporeforge structure.
        structure (Structure): The Dwarven Sporeforge structure instance.
    """
    game_state.add_debug_message(f"Interacting with {structure.name}... (Sporeforge UI/feature TBD)")
    # TODO: Implement Sporeforge UI or functionality 