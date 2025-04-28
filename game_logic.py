import random
from typing import TYPE_CHECKING, Dict, List, Tuple, Optional, cast

# Update constants import to relative
from .constants import MAP_WIDTH, MAP_HEIGHT, ANIMAL_MOVE_CHANCE, FISHING_TICKS, BASE_UNDERGROUND_MINING_TICKS

# Use relative imports for modules within the fungi_fortress package
from .characters import Task, Dwarf, NPC, Animal # Added Dwarf, NPC, Animal if needed here
from .missions import check_mission_completion, complete_mission
from .map_generation import generate_map, generate_mycelial_network # Ensure these are imported
# from .map_generation import generate_map, expose_to_spores # expose_to_spores moved from magic?
from .utils import a_star
from .tiles import Tile, ENTITY_REGISTRY
from .entities import ResourceNode, Structure, Sublevel, GameEntity # Added GameEntity
from .events import check_events
# from .magic import cast_spell # Import only if cast_spell is used directly in this file

# Import Entity types for type hinting using relative paths
if TYPE_CHECKING:
    from .game_state import GameState
    from .player import Player # Added for type hints
    # Tile already imported
    # Structure, Sublevel already imported

# --- Moved from map_generation.py ---
def expose_to_spores(game_state: 'GameState', intensity: int):
    """Randomly converts some floor tiles to mycelium based on intensity.

    Checks eligible tiles (stone floor, grass) on the current map.
    The chance of conversion increases significantly if a tile is adjacent
    to existing mycelium floor.

    Args:
        game_state (GameState): The current game state, used to access the map and entities.
        intensity (int): A factor influencing the base probability of spore spread.
                         Higher intensity increases the spread chance.
    """
    # Assume ENTITY_REGISTRY is populated correctly elsewhere (e.g., in tiles.py)
    # We access it directly; if keys are missing, it should raise an error early.
    mycelium_floor: Optional[GameEntity] = ENTITY_REGISTRY.get("mycelium_floor") # Use .get() for safety, check below
    stone_floor: Optional[GameEntity] = ENTITY_REGISTRY.get("stone_floor")
    grass: Optional[GameEntity] = ENTITY_REGISTRY.get("grass")
    bridge: Optional[GameEntity] = ENTITY_REGISTRY.get("bridge") # Assuming bridge exists

    # Check if essential entities were loaded
    if not all([mycelium_floor, stone_floor, grass, bridge]):
        # Collect names of missing entities for a more informative error message
        missing = []
        if not mycelium_floor: missing.append("mycelium_floor")
        if not stone_floor: missing.append("stone_floor")
        if not grass: missing.append("grass")
        if not bridge: missing.append("bridge") # Added bridge check
        raise ImportError(f"Essential floor/terrain entities not found in ENTITY_REGISTRY: {', '.join(missing)}")

    spread_chance: float = 0.01 * intensity # Base chance

    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            tile: Optional[Tile] = game_state.get_tile(x, y) # Use safe getter
            if not tile: continue

            # Can only spread to stone floor or grass
            if tile.entity in [stone_floor, grass]:
                # Check adjacent tiles for existing mycelium (more likely to spread near existing)
                adjacent_mycelium: bool = False
                for dy in range(-1, 2):
                    for dx in range(-1, 2):
                        if dx == 0 and dy == 0: continue
                        nx, ny = x + dx, y + dy
                        adj_tile: Optional[Tile] = game_state.get_tile(nx, ny)
                        if adj_tile and adj_tile.entity == mycelium_floor:
                                adjacent_mycelium = True
                                break
                    if adjacent_mycelium: break

                current_chance: float = spread_chance * 5 if adjacent_mycelium else spread_chance
                if random.random() < current_chance:
                    # Replace the entity on the existing Tile object
                    # We know mycelium_floor is not None due to the check above
                    tile.entity = cast(GameEntity, mycelium_floor)
# --- End moved function ---

# --- REMOVED Interaction/Entry Logic Functions (moved to interactions.py) ---
# def enter_sublevel_logic(...):
# def interact_mycelial_nexus_logic(...):
# def interact_dwarven_sporeforge_logic(...):

class GameLogic:
    """Handles the core game logic updates performed each game tick.

    Responsible for advancing the game state by processing character actions,
    environmental effects, task management, and event checking.

    Key Responsibilities:
    - Incrementing the game tick counter.
    - Checking for and handling game events (via `events.check_events`).
    - Updating transient tile effects (e.g., highlight duration).
    - Managing animal AI (random movement on the surface).
    - Resolving entity stacking by spreading characters/animals to adjacent tiles.
    - Assigning pending tasks from the TaskManager to idle dwarves.
    - Updating dwarf states:
        - Pathfinding and movement execution.
        - Task execution (mining, chopping, building, fishing, fighting, entering sublevels).
        - Handling task completion (resource gain, tile changes, effects).
        - Managing the dwarf task queue.
    - Triggering spore spread effects (via `expose_to_spores`).
    - Checking for mission completion (via `missions.check_mission_completion`).

    Attributes:
        game_state (GameState): A reference to the main game state object, providing access
                              to the map, characters, inventory, player state, etc.
    """
    def __init__(self, game_state: 'GameState'):
        """Initializes the GameLogic controller.

        Args:
            game_state (GameState): The main game state object to be managed.
        """
        self.game_state: 'GameState' = game_state
        # Ensure inventory uses Resource enum if applicable, or string keys are fine
        # self.game_state.inventory.add_resource("Sclerotium", 1) # Assuming string keys for now

    def _trigger_sublevel_entry(self, dwarf: 'Dwarf', entry_tile: Tile):
        """Handles the logic for a dwarf entering a sublevel.

        This is triggered when a dwarf completes an 'enter' task by reaching
        the tile adjacent to the Sublevel entity.

        Steps:
        1. Validates the entry tile contains a Sublevel entity.
        2. Ensures the sublevel data structure exists in `game_state.sub_levels`.
        3. Generates the sublevel map and associated data (nexus site, fungi locations,
           mycelial network) if it doesn't exist yet, using `map_generation.generate_map`
           and `map_generation.generate_mycelial_network`.
        4. Switches the `game_state.map` to the sublevel map.
        5. Updates the `game_state.active_mycelial_network` and recalculates distances.
        6. Updates player location state.
        7. Finds a suitable spawn location within the sublevel.
        8. Repositions all dwarves to the spawn location (or nearby walkable tiles).
        9. Resets the state of all dwarves to 'idle'.

        Args:
            dwarf (Dwarf): The dwarf initiating the entry (used for debug messages).
            entry_tile (Tile): The tile containing the `Sublevel` entity itself.
        """
        if not isinstance(entry_tile.entity, Sublevel):
             self.game_state.add_debug_message(f"Error: Attempted sublevel entry on non-sublevel entity {entry_tile.entity.name}")
             return

        sub_level_entity: Sublevel = entry_tile.entity
        sub_level_name: str = sub_level_entity.name
        entry_x: int = entry_tile.x # Actual entrance coords
        entry_y: int = entry_tile.y

        # Ensure sub-level state exists
        if sub_level_name not in self.game_state.sub_levels:
            self.game_state.sub_levels[sub_level_name] = {
                "active": False,
                "map": None,
                "nexus_site": None,
                "magic_fungi_locations": None,
                "mycelial_network": None
            }

        # Generate map IF it doesn't exist yet
        sub_level_data = self.game_state.sub_levels[sub_level_name] # Type hint helper
        if not sub_level_data.get("map"):
            self.game_state.add_debug_message(f"Generating map for {sub_level_name}...")
            map_grid: Optional[List[List[Tile]]]
            nexus_site: Optional[Tuple[int, int]]
            magic_fungi_locations: Optional[List[Tuple[int, int]]]

            map_grid, nexus_site, magic_fungi_locations = generate_map(
                MAP_WIDTH, MAP_HEIGHT,
                depth=-1, # Depth indication for sublevels
                mission=self.game_state.mission,
                sub_level=sub_level_name.lower().replace(" ", "_") # Pass sublevel type for generation variations
            )
            if map_grid: # Check if generation succeeded
                sub_level_data["map"] = map_grid
                sub_level_data["nexus_site"] = nexus_site
                sub_level_data["magic_fungi_locations"] = magic_fungi_locations
                # Generate mycelial network for the new sublevel map
                if nexus_site is not None: # Check if nexus_site is valid before generating network
                    mycelial_network: Dict = generate_mycelial_network(map_grid, nexus_site, magic_fungi_locations or [])
                    sub_level_data["mycelial_network"] = mycelial_network
                    self.game_state.add_debug_message(f"Mycelial network generated for {sub_level_name}.")
                else:
                    self.game_state.add_debug_message(f"Warning: Nexus site not found for {sub_level_name}, skipping mycelial network generation.")
                    sub_level_data["mycelial_network"] = None # Ensure it's explicitly None
                self.game_state.add_debug_message(f"Map generated for {sub_level_name}.") # Moved message after network attempt
            else:
                self.game_state.add_debug_message(f"Error: Map generation failed for {sub_level_name}. Cannot enter.")
                return # Abort entry if map generation fails

        # Check again if map exists after attempting generation
        current_map_grid = sub_level_data.get("map")
        if not current_map_grid:
            self.game_state.add_debug_message(f"Error: Sublevel map for {sub_level_name} still missing after generation attempt.")
            return

        # --- Proceed with Entry ---
        self.game_state.add_debug_message(f"D{dwarf.id} entering {sub_level_name} at ({entry_x}, {entry_y})...")
        sub_level_data["active"] = True
        self.game_state.map = current_map_grid # Switch to sublevel map

        # Store the entry point coordinates to return to later
        self.game_state.entry_x, self.game_state.entry_y = entry_x, entry_y

        # Update Player State
        self.game_state.player.update_state("location", sub_level_name)

        # Update game state's active mycelial network and distances (if applicable)
        sub_level_network: Optional[Dict] = sub_level_data.get("mycelial_network")
        if isinstance(sub_level_network, dict):
            self.game_state.mycelial_network = sub_level_network
        else:
            self.game_state.mycelial_network = {}
            if sub_level_network is not None:
                 self.game_state.add_debug_message(f"Warning: Invalid mycelial network data found for {sub_level_name}, using empty network.")

        self.game_state.network_distances = self.game_state.calculate_network_distances() # Recalculate for the new map/network

        # Move dwarf(s) to a valid starting position within the sublevel
        # Find a walkable tile near the center or a predefined entry point
        spawn_found: bool = False
        spawn_x: int = -1
        spawn_y: int = -1
        center_x, center_y = MAP_WIDTH // 2, MAP_HEIGHT // 2
        for r in range(max(MAP_WIDTH, MAP_HEIGHT) // 2): # Search outwards from center
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if abs(dx) != r and abs(dy) != r: continue # Only check perimeter of search box
                    nx, ny = center_x + dx, center_y + dy
                    current_tile: Optional[Tile] = self.game_state.get_tile(nx, ny)
                    if current_tile and current_tile.walkable:
                        spawn_x, spawn_y = nx, ny
                        # Move all dwarves to this spawn point (or slightly offset)
                        for i, d in enumerate(self.game_state.dwarves):
                            offset_x: int = random.randint(-1, 1)
                            offset_y: int = random.randint(-1, 1)
                            final_x: int = max(0, min(MAP_WIDTH - 1, spawn_x + offset_x))
                            final_y: int = max(0, min(MAP_HEIGHT - 1, spawn_y + offset_y))
                            # Ensure offset position is also walkable
                            offset_tile: Optional[Tile] = self.game_state.get_tile(final_x, final_y)
                            if offset_tile and offset_tile.walkable:
                                d.x, d.y = final_x, final_y
                            else:
                                d.x, d.y = spawn_x, spawn_y # Fallback to original spawn point
                            d.state = 'idle' # Ensure dwarves are idle after transition
                            d.path = []
                            d.task = None
                        self.game_state.cursor_x, self.game_state.cursor_y = spawn_x, spawn_y # Move cursor too
                        spawn_found = True
                        break
                if spawn_found: break
            if spawn_found: break

        if not spawn_found:
             self.game_state.add_debug_message(f"Warning: No walkable spawn point found in {sub_level_name}. Placing at center.")
             # Fallback: Place dwarves at center (might be unwalkable!)
             fallback_x, fallback_y = MAP_WIDTH // 2, MAP_HEIGHT // 2
             for d in self.game_state.dwarves:
                 d.x, d.y = fallback_x, fallback_y
                 d.state = 'idle'
                 d.path = []
                 d.task = None
             self.game_state.cursor_x, self.game_state.cursor_y = fallback_x, fallback_y

        self.game_state.add_debug_message(f"Entered {sub_level_name}.")

    def update(self):
        """Advances the game state by one tick.

        Executes all per-tick logic, including character actions, task processing,
        event checks, and environmental updates, unless the game is paused or
        in a blocking UI state (inventory, shop, legend).

        Order of Operations:
        1. Return early if game is paused or in a blocking UI state.
        2. Increment `game_state.tick`.
        3. Call `check_events`.
        4. Decrement timers for temporary tile effects (highlight, flash, pulse).
        5. Process animal movement (randomly on surface map).
        6. Resolve character/animal stacking by spreading them to adjacent empty tiles.
        7. Assign tasks from `game_state.task_manager` to idle dwarves:
           - Finds path using `a_star`.
           - Sets dwarf state to 'moving' or appropriate work/fight/fish state.
           - Assigns task details (target, resource coords, ticks) to dwarf.
           - Removes assigned task from manager or queues for busy dwarves.
           - Marks unreachable tasks for removal.
        8. Update each dwarf based on their state:
           - 'moving': Follow path, transition state upon reaching destination.
                     Special handling for 'enter' tasks to call `_trigger_sublevel_entry`.
           - 'working'/'fighting'/'fishing': Decrement `task_ticks`. On completion:
               - Apply task effects (gain resources, change tiles, build structures/bridges,
                 kill animals/NPCs, trigger spore exposure, illuminate paths).
               - Reset dwarf state to 'idle' or assign next task from queue.
           - 'idle': Check task queue for new assignments.
        9. (Placeholder) Trigger periodic spore spread.
        10. (Placeholder) Check mission completion.
        """
        if self.game_state.paused or self.game_state.show_inventory or self.game_state.in_shop or self.game_state.show_legend:
            return

        self.game_state.tick += 1

        check_events(self.game_state)

        # Update tile effects
        current_map: List[List[Tile]] = self.game_state.map
        for row in current_map:
            for tile in row:
                if tile.highlight_ticks > 0:
                    tile.highlight_ticks -= 1
                    if tile.highlight_ticks == 0:
                         tile.set_color_override(None) # Corrected: Use set_color_override(None)
                if getattr(tile, 'flash_ticks', 0) > 0:
                    tile.flash_ticks -= 1
                    if tile.flash_ticks == 0:
                        tile.set_color_override(None) # Corrected: Use set_color_override(None)
                if getattr(tile, 'pulse_ticks', 0) > 0:
                    tile.pulse_ticks -= 1
                    if tile.pulse_ticks == 0:
                        tile.set_color_override(None) # Corrected: Use set_color_override(None)

        # --- Animal Movement ---
        # Only move animals if on surface map (depth 0 and no active sublevel)
        is_surface_map: bool = self.game_state.depth == 0 and \
                               not any(sub_data.get("active", False)
                                       for sub_data in self.game_state.sub_levels.values())

        if is_surface_map:
            grass_entity: Optional[GameEntity] = ENTITY_REGISTRY.get("grass")
            if grass_entity: # Only proceed if grass exists
                for animal in self.game_state.animals:
                    if animal.alive and random.random() < ANIMAL_MOVE_CHANCE:
                        dx, dy = random.choice([(0, 1), (0, -1), (1, 0), (-1, 0)])
                        nx, ny = animal.x + dx, animal.y + dy
                        if (0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT):
                            target_tile: Optional[Tile] = self.game_state.get_tile(nx, ny)
                            # Check tile, entity, and occupancy
                            if (target_tile and target_tile.entity == grass_entity and
                                not any(d.x == nx and d.y == ny for d in self.game_state.dwarves) and
                                not any(c.x == nx and c.y == ny and c.alive for c in self.game_state.characters) and
                                not any(a.x == nx and a.y == ny and a.alive and a is not animal for a in self.game_state.animals)): # Exclude self
                                    animal.x, animal.y = nx, ny

        # --- Stacking Resolution ---
        # OPTIMIZATION TODO: This is O(W*H*N). Could be optimized by only checking occupied tiles.
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                 #target_tile: Optional[Tile] = self.game_state.get_tile(x, y) # Already got current_map
                 #if not target_tile: continue

                 dwarves_here: List[Dwarf] = [d for d in self.game_state.dwarves if d.x == x and d.y == y]
                 animals_here: List[Animal] = [a for a in self.game_state.animals if a.x == x and a.y == y and a.alive]
                 characters_here: List[NPC] = [c for c in self.game_state.characters if c.x == x and c.y == y and c.alive] # Include NPCs
                 
                 total_entities_here = len(dwarves_here) + len(animals_here) + len(characters_here)

                 # Spread dwarves if more than one entity total, or if stacked with NPC
                 if len(dwarves_here) > 0 and (total_entities_here > 1 or any(isinstance(c, NPC) for c in characters_here)):
                    # Spread all but one dwarf
                    dwarves_to_move = dwarves_here[1:] if len(dwarves_here) > 1 else dwarves_here if characters_here else []
                    for dwarf in dwarves_to_move:
                        adj: Optional[Tuple[int, int]] = self.find_adjacent_tile(x, y)
                        if adj:
                            dwarf.x, dwarf.y = adj
                            self.game_state.add_debug_message(f"Dwarf spread to ({adj[0]}, {adj[1]})")

                 # Spread animals if more than one entity total (or if stacked with dwarf/NPC)
                 if len(animals_here) > 0 and total_entities_here > 1:
                     # Spread all but one animal
                     animals_to_move = animals_here[1:] if len(animals_here) > 1 else animals_here if (dwarves_here or characters_here) else []
                     for animal in animals_to_move:
                        adj = self.find_adjacent_tile(x, y)
                        if adj:
                             adj_tile: Optional[Tile] = self.game_state.get_tile(adj[0], adj[1])
                             # Only spread animals onto grass if possible (on surface) or walkable floor otherwise
                             if adj_tile and ( (is_surface_map and adj_tile.entity.name == "Grass") or adj_tile.walkable ):
                                 animal.x, animal.y = adj
                                 self.game_state.add_debug_message(f"Animal spread to ({adj[0]}, {adj[1]})")

        # --- Task Assignment ---
        idle_dwarves: List[Dwarf] = [d for d in self.game_state.dwarves if d.state == 'idle']
        tasks_to_remove: List[Task] = []
        # REFACTORING TODO: Task assignment logic (here and in queue handling below) is complex and duplicated. Could be merged/simplified.
        for task in self.game_state.task_manager.tasks:
            # Check if any idle dwarf can reach the task
            reachable_idle_dwarves: List[Tuple[Dwarf, Optional[List[Tuple[int, int]]], int]] = [] # (dwarf, path, distance)
            if idle_dwarves:
                for d in idle_dwarves:
                    # Target for pathfinding is the task's interaction point (x, y)
                    path: Optional[List[Tuple[int, int]]] = a_star(current_map, (d.x, d.y), (task.x, task.y))
                    if path is not None:
                        reachable_idle_dwarves.append((d, path, len(path)))
                    elif (d.x, d.y) == (task.x, task.y): # Already at the interaction point
                        reachable_idle_dwarves.append((d, [], 0)) # Empty path, distance 0

            if reachable_idle_dwarves:
                # Assign to the NEAREST reachable idle dwarf
                reachable_idle_dwarves.sort(key=lambda item: item[2]) # Sort by distance (path length)
                dwarf, path, dist = reachable_idle_dwarves[0]

                if path is not None and len(path) > 0:
                    dwarf.state = 'moving'
                    dwarf.path = path
                    self.game_state.add_debug_message(f"D{dwarf.id} moving to ({task.x}, {task.y}) with path length {len(path)}")
                else: # Already at location
                    # Set state based on task type
                    if task.type in ['mine', 'chop', 'build', 'build_bridge']:
                        dwarf.state = 'working'
                    elif task.type in ['hunt', 'fight']:
                        dwarf.state = 'fighting'
                    elif task.type == 'fish':
                        dwarf.state = 'fishing'
                    elif task.type == 'enter': # Should be handled in 'moving' state completion, but set state here just in case
                        dwarf.state = 'moving' # Still technically 'moving' to the entry point tile
                    else:
                        dwarf.state = 'idle' # Fallback
                    dwarf.path = []
                    self.game_state.add_debug_message(f"D{dwarf.id} already at ({task.x}, {task.y}), starting {task.type}")

                # Assign task details
                dwarf.target_x, dwarf.target_y = task.x, task.y
                dwarf.task = task
                dwarf.resource_x, dwarf.resource_y = task.resource_x, task.resource_y

                # Set initial task ticks
                if task.type in ['fish', 'hunt', 'fight']:
                    dwarf.task_ticks = FISHING_TICKS
                elif task.type == 'build' and task.building and task.building in self.game_state.buildings:
                    dwarf.task_ticks = self.game_state.buildings[task.building]['ticks']
                elif task.type == 'build_bridge':
                    dwarf.task_ticks = BASE_UNDERGROUND_MINING_TICKS # Assuming this constant is appropriate
                elif task.type in ['mine', 'chop']: # Base ticks for mining/chopping (adjusted by skill later)
                     # Use a base value, actual time depends on skill check during update
                     resource_tile_for_ticks = self.game_state.get_tile(task.resource_x, task.resource_y) if task.resource_x is not None else None
                     base_ticks = getattr(resource_tile_for_ticks.entity, 'hardness', BASE_UNDERGROUND_MINING_TICKS) if resource_tile_for_ticks else BASE_UNDERGROUND_MINING_TICKS
                     dwarf.task_ticks = base_ticks
                elif task.type == 'enter':
                    dwarf.task_ticks = 1 # Entering is instantaneous once adjacent
                else:
                    dwarf.task_ticks = 0 # Default/unknown task

                tasks_to_remove.append(task)
                idle_dwarves.remove(dwarf) # Remove from idle list for this tick
                self.game_state.add_debug_message(f"Assigned {task.type} task to D{dwarf.id} at ({task.x}, {task.y})")

            # If no IDLE dwarf can reach it, check if ANY dwarf can reach it to queue
            elif not idle_dwarves: # Only queue if no idle dwarves are left
                reachable_any_dwarves: List[Tuple[Dwarf, Optional[List[Tuple[int, int]]], int]] = []
                for d in self.game_state.dwarves:
                     path = a_star(current_map, (d.x, d.y), (task.x, task.y))
                     if path is not None:
                         reachable_any_dwarves.append((d, path, len(path)))
                     elif (d.x, d.y) == (task.x, task.y):
                         reachable_any_dwarves.append((d, [], 0))

                if reachable_any_dwarves:
                     # Queue for the NEAREST dwarf
                     reachable_any_dwarves.sort(key=lambda item: item[2])
                     dwarf_to_queue, _, _ = reachable_any_dwarves[0]
                     # Add only if not already the current task and not already in queue
                     if dwarf_to_queue.task != task and task not in dwarf_to_queue.task_queue:
                         dwarf_to_queue.task_queue.append(task)
                         tasks_to_remove.append(task)
                         self.game_state.add_debug_message(f"Task ({task.type} at {task.x},{task.y}) queued for D{dwarf_to_queue.id}")
                     else:
                        # Task already assigned or queued, don't remove from manager yet
                        pass
                else: # Task is unreachable by any dwarf
                    task.task_unreachable_ticks += 1
                    if task.task_unreachable_ticks >= 5: # Remove after 5 ticks of being unreachable
                        tasks_to_remove.append(task)
                        self.game_state.add_debug_message(f"Task ({task.type} at {task.x},{task.y}) unreachable by any dwarf, removed")

        # Remove assigned/queued/unreachable tasks from the main manager list
        for task in tasks_to_remove:
            self.game_state.task_manager.remove_task(task)

        # --- Dwarf State Updates ---
        for dwarf in self.game_state.dwarves:
            if dwarf.state == 'moving':
                if dwarf.path:
                    next_x, next_y = dwarf.path.pop(0)
                    # DEBUG: Check if next step is walkable before moving
                    next_tile = self.game_state.get_tile(next_x, next_y)
                    if next_tile and next_tile.walkable:
                        dwarf.x, dwarf.y = next_x, next_y
                        #self.game_state.add_debug_message(f" D{dwarf.id} popping path: moving to ({next_x}, {next_y})") # Less verbose debug
                    else:
                        # Path blocked, recalculate or idle? For now, just idle.
                        self.game_state.add_debug_message(f" D{dwarf.id} path blocked at ({next_x},{next_y}). Resetting task.")
                        dwarf.path = []
                        dwarf.state = 'idle'
                        dwarf.task = None # Drop current task if path blocked mid-way
                        continue # Skip rest of update for this dwarf this tick

                # Check path completion AFTER potentially moving
                if not dwarf.path:
                    current_task: Optional[Task] = dwarf.task
                    self.game_state.add_debug_message(f"DEBUG: D{dwarf.id} reached destination ({dwarf.x},{dwarf.y}). Current task: {current_task}") # DEBUG

                    # --- Handle 'enter' task completion ---
                    if current_task and current_task.type == 'enter':
                        self.game_state.add_debug_message(f"DEBUG: Detected 'enter' task completion for D{dwarf.id}.") # DEBUG
                        # Dwarf is at the adjacent tile (dwarf.x, dwarf.y)
                        # The actual entrance is at (current_task.resource_x, current_task.resource_y)
                        entry_point_x: Optional[int] = current_task.resource_x
                        entry_point_y: Optional[int] = current_task.resource_y
                        if entry_point_x is not None and entry_point_y is not None:
                            self.game_state.add_debug_message(f"DEBUG: Entry point coords: ({entry_point_x}, {entry_point_y})") # DEBUG
                            entry_tile: Optional[Tile] = self.game_state.get_tile(entry_point_x, entry_point_y)
                            if entry_tile and isinstance(entry_tile.entity, Sublevel):
                                self.game_state.add_debug_message(f"DEBUG: Found entry tile: {entry_tile}. Calling _trigger_sublevel_entry.") # DEBUG
                                self._trigger_sublevel_entry(dwarf, entry_tile)
                                # The transition function resets dwarf state, so we can just continue
                                continue # Skip the rest of the state handling for this tick
                            else:
                                self.game_state.add_debug_message(f"DEBUG: ERROR - Invalid entry tile or entity at ({entry_point_x}, {entry_point_y}) for enter task.") # DEBUG
                                dwarf.state = 'idle' # Reset dwarf state anyway
                                dwarf.task = None
                        else:
                            self.game_state.add_debug_message("DEBUG: ERROR - 'enter' task missing resource coordinates.") # DEBUG
                            dwarf.state = 'idle'
                            dwarf.task = None
                        # If we reached here after attempting entry, something went wrong or continue wasn't hit
                        self.game_state.add_debug_message(f"DEBUG: Post-entry attempt for D{dwarf.id}. State: {dwarf.state}") # DEBUG

                    # --- Transition to other states from moving ---
                    else:
                        self.game_state.add_debug_message(f"DEBUG: Task was not 'enter' or no task. Determining next state.") # DEBUG
                        next_state: str = 'idle' # Default
                        if current_task:
                            if current_task.type in ['mine', 'chop', 'build', 'build_bridge']:
                                next_state = 'working'
                            elif current_task.type in ['hunt', 'fight']:
                                next_state = 'fighting'
                            elif current_task.type == 'fish':
                                next_state = 'fishing'
                            # Keep 'enter' state logic separate above

                        dwarf.state = next_state
                        self.game_state.add_debug_message(f"D{dwarf.id} now {dwarf.state}")

            elif dwarf.state in ['working', 'fighting', 'fishing']:
                current_task = dwarf.task # Type hint helper
                # Check if task and target coordinates exist
                if current_task and dwarf.target_x is not None and dwarf.target_y is not None:
                    # --- Make sure the 'enter' task is not processed here ---
                    if current_task.type == 'enter':
                        self.game_state.add_debug_message(f"Warning: D{dwarf.id} in state {dwarf.state} with 'enter' task. Resetting.")
                        dwarf.state = 'idle'
                        dwarf.task = None
                        continue # Skip rest of processing for this dwarf

                    # --- Task Progress ---
                    work_rate = 1
                    if dwarf.state == 'working' and current_task.type in ['mine', 'chop']:
                        work_rate = dwarf.mining_skill # Assuming mining skill affects chopping too
                    dwarf.task_ticks -= work_rate

                    # --- Task Completion ---
                    if dwarf.task_ticks <= 0:
                        target_tile: Optional[Tile] = self.game_state.get_tile(dwarf.target_x, dwarf.target_y) # Tile being interacted with (adjacent)
                        resource_tile: Optional[Tile] = self.game_state.get_tile(dwarf.resource_x, dwarf.resource_y) if dwarf.resource_x is not None else None # Tile containing the resource/build site

                        completed_task_type: str = current_task.type
                        self.game_state.add_debug_message(f"D{dwarf.id} finished {completed_task_type} task at ({dwarf.target_x},{dwarf.target_y}) targeting resource at ({dwarf.resource_x},{dwarf.resource_y})")

                        # --- Handle Task Completion Effects ---
                        if completed_task_type == 'mine' and resource_tile:
                            if isinstance(resource_tile.entity, ResourceNode):
                                resource_node: ResourceNode = resource_tile.entity # Type hint helper
                                resource_name: str = resource_node.resource_type
                                yield_amount: int = resource_node.yield_amount
                                self.game_state.inventory.add_resource(resource_name, yield_amount)
                                self.game_state.add_debug_message(f"Yielded {yield_amount} {resource_name}")

                                # Replace mined entity with appropriate floor
                                floor_entity_name = "stone_floor" # Default underground
                                if self.game_state.depth == 0: floor_entity_name = "grass"
                                # Example: Check if in a specific sublevel type
                                # elif any(sub_name == "Mycelial Nexus Core" and sub_data.get("active", False) for sub_name, sub_data in self.game_state.sub_levels.items()):
                                #    floor_entity_name = "mycelium_floor"

                                floor_entity: Optional[GameEntity] = ENTITY_REGISTRY.get(floor_entity_name)
                                if floor_entity:
                                    resource_tile.entity = floor_entity
                                    self.game_state.add_debug_message(f"Replaced {resource_name} with {floor_entity_name}")
                                else:
                                     self.game_state.add_debug_message(f"Warning: Could not find floor entity '{floor_entity_name}' to replace {resource_name}")


                                # --- Special effect for fungi ---
                                if resource_name in ["fungi", "magic_fungi"]:
                                    spore_gain: int = getattr(resource_node, 'spore_yield', 0)
                                    if spore_gain > 0:
                                         self.game_state.player.spore_exposure += spore_gain
                                         self.game_state.add_debug_message(f"Gained {spore_gain} spore exposure (total: {self.game_state.player.spore_exposure})")
                                         expose_to_spores(self.game_state, spore_gain) # Expose area

                                    # --- Path Illumination Logic ---
                                    if resource_name == "magic_fungi" and self.game_state.nexus_site:
                                        if self.game_state.player.spore_exposure >= self.game_state.spore_exposure_threshold:
                                            start_pos: Tuple[int, int] = (dwarf.x, dwarf.y) # Dwarf's current position
                                            target_site: Tuple[int, int] = self.game_state.nexus_site
                                            self.game_state.add_debug_message(f"Attempting to illuminate path from {start_pos} to nexus at {target_site}")
                                            path_to_nexus: Optional[List[Tuple[int, int]]] = a_star(current_map, start_pos, target_site)

                                            if path_to_nexus:
                                                path_length: int = len(path_to_nexus)
                                                highlight_duration: int = 50 # Duration in ticks
                                                self.game_state.add_debug_message(f"Illuminating path ({path_length} steps) to Nexus {target_site}")

                                                # Colors for the mycelium visualization (purple/pink/magenta)
                                                mycelium_colors: List[int] = [5, 13, 201, 206] # Purple, Bright Magenta, Pink variants

                                                # Apply path highlighting with proper colors
                                                for i, (px, py) in enumerate(path_to_nexus):
                                                    path_tile: Optional[Tile] = self.game_state.get_tile(px, py)
                                                    if path_tile:
                                                        path_tile.highlight_ticks = highlight_duration
                                                        # Calculate position in path (0 to 1.0)
                                                        pos: float = i / max(1, path_length - 1)
                                                        # Choose color based on position - creates gradient effect
                                                        color_index: int = min(int(pos * len(mycelium_colors)), len(mycelium_colors) - 1)
                                                        # Apply custom color instead of default highlight color
                                                        path_tile.set_color_override(mycelium_colors[color_index])

                                                # Make nexus pulse with special color effect
                                                nexus_tile: Optional[Tile] = self.game_state.get_tile(target_site[0], target_site[1])
                                                if nexus_tile:
                                                    nexus_tile.flash_ticks = 100
                                                    nexus_tile.set_color_override(13) # Bright Magenta for nexus
                                            else:
                                                self.game_state.add_debug_message(f"Could not find path from {start_pos} to Nexus {target_site}")
                                        else:
                                            self.game_state.add_debug_message(f"Spore exposure ({self.game_state.player.spore_exposure}) below threshold ({self.game_state.spore_exposure_threshold})")
                                    # --- End Path Illumination Logic ---
                            else:
                                self.game_state.add_debug_message(f"Warning: Mine task completed on non-ResourceNode entity: {resource_tile.entity.name if resource_tile and resource_tile.entity else 'None'}")

                        elif completed_task_type == 'chop' and resource_tile:
                             if isinstance(resource_tile.entity, ResourceNode) and resource_tile.entity.resource_type == "wood":
                                 resource_node = resource_tile.entity # Type hint helper
                                 yield_amount = resource_node.yield_amount
                                 self.game_state.inventory.add_resource("wood", yield_amount)
                                 self.game_state.add_debug_message(f"Yielded {yield_amount} wood")
                                 # Replace tree with appropriate floor
                                 floor_entity_name = "grass" if self.game_state.depth == 0 else "stone_floor"
                                 floor_entity = ENTITY_REGISTRY.get(floor_entity_name)
                                 if floor_entity:
                                     resource_tile.entity = floor_entity
                                     self.game_state.add_debug_message(f"Replaced tree with {floor_entity_name}")
                                 else:
                                     self.game_state.add_debug_message(f"Warning: Could not find floor entity '{floor_entity_name}' to replace tree")
                             else:
                                  self.game_state.add_debug_message(f"Warning: Chop task completed on non-wood entity: {resource_tile.entity.name if resource_tile and resource_tile.entity else 'None'}")

                        elif completed_task_type == 'build':
                            building_name: Optional[str] = current_task.building
                            build_site_x: Optional[int] = current_task.resource_x
                            build_site_y: Optional[int] = current_task.resource_y

                            if building_name and build_site_x is not None and build_site_y is not None:
                                building_template: Optional[GameEntity] = ENTITY_REGISTRY.get(building_name)
                                build_site_tile: Optional[Tile] = self.game_state.get_tile(build_site_x, build_site_y)

                                if building_template and build_site_tile:
                                    # Check resources (example for Nexus, generalize for others)
                                    can_build = False
                                    cost = self.game_state.buildings.get(building_name, {}).get('cost', {})
                                    special_cost = self.game_state.buildings.get(building_name, {}).get('special_cost', {})

                                    # Check resource costs
                                    has_resources = all(self.game_state.inventory.resources.get(res, 0) >= amount for res, amount in cost.items())
                                    # Check special item costs
                                    has_special_items = all(self.game_state.inventory.special_items.get(item, 0) >= amount for item, amount in special_cost.items())

                                    if has_resources and has_special_items:
                                        # Deduct costs
                                        for res, amount in cost.items():
                                            self.game_state.inventory.remove_resource(res, amount)
                                        for item, amount in special_cost.items():
                                            self.game_state.inventory.remove_item(item, amount)

                                        # Place the building entity (create a new instance if needed)
                                        # Assuming building templates in ENTITY_REGISTRY are classes or copyable
                                        build_site_tile.entity = building_template # TODO: Ensure this doesn't reuse same object instance if stateful
                                        self.game_state.add_debug_message(f"Built {building_name} at ({build_site_x}, {build_site_y})")
                                        can_build = True

                                        # Check mission completion after successful build
                                        if check_mission_completion(self.game_state, self.game_state.mission):
                                            complete_mission(self.game_state, self.game_state.mission)
                                    else:
                                        missing_res = {res: amount for res, amount in cost.items() if self.game_state.inventory.resources.get(res, 0) < amount}
                                        missing_items = {item: amount for item, amount in special_cost.items() if self.game_state.inventory.special_items.get(item, 0) < amount}
                                        self.game_state.add_debug_message(f"Cannot build {building_name}. Missing: {missing_res}, {missing_items}")

                                else:
                                     self.game_state.add_debug_message(f"ERROR: Cannot build {building_name}. Invalid entity template or build site tile at ({build_site_x}, {build_site_y}).")
                            else:
                                self.game_state.add_debug_message(f"Warning: Build task completed for invalid building '{building_name}' or missing coordinates.")


                        elif completed_task_type == 'build_bridge':
                             bridge_target_x: Optional[int] = current_task.resource_x
                             bridge_target_y: Optional[int] = current_task.resource_y
                             if bridge_target_x is not None and bridge_target_y is not None:
                                bridge_target_tile = self.game_state.get_tile(bridge_target_x, bridge_target_y)
                                # Check adjacency using dwarf's current position (target_x/y) vs resource_x/y
                                is_adjacent = abs(dwarf.target_x - bridge_target_x) + abs(dwarf.target_y - bridge_target_y) == 1

                                if bridge_target_tile and bridge_target_tile.entity.name == "Water" and is_adjacent:
                                    wood_cost = 1 # Example cost
                                    if self.game_state.inventory.resources.get("wood", 0) >= wood_cost:
                                        self.game_state.inventory.remove_resource("wood", wood_cost)
                                        if self.game_state.update_tile_entity(bridge_target_x, bridge_target_y, "bridge"):
                                            self.game_state.add_debug_message(f"D{dwarf.id} built bridge segment at ({bridge_target_x}, {bridge_target_y})")
                                        else:
                                             self.game_state.add_debug_message(f"ERROR: Failed to update tile entity to bridge at ({bridge_target_x}, {bridge_target_y})")
                                    else:
                                        self.game_state.add_debug_message(f"D{dwarf.id} cannot build bridge: Needs {wood_cost} wood.")
                                elif not bridge_target_tile:
                                     self.game_state.add_debug_message(f"D{dwarf.id} cannot build bridge: Target tile {bridge_target_x},{bridge_target_y} invalid.")
                                elif not is_adjacent:
                                     self.game_state.add_debug_message(f"D{dwarf.id} cannot build bridge: Not adjacent to target {bridge_target_x},{bridge_target_y}. Dwarf at {dwarf.target_x},{dwarf.target_y}")
                                else: # Target tile is not water anymore
                                    self.game_state.add_debug_message(f"D{dwarf.id} cannot build bridge: Target tile at ({bridge_target_x}, {bridge_target_y}) is no longer water ({bridge_target_tile.entity.name}).")
                             else:
                                self.game_state.add_debug_message(f"Warning: Build_bridge task completed with invalid resource coordinates.")

                        elif completed_task_type == 'fish':
                            if random.random() < 0.3: # Chance to catch fish
                                self.game_state.inventory.add_resource("food", 1)
                                self.game_state.add_debug_message(f"D{dwarf.id} caught a fish!")
                            else:
                                self.game_state.add_debug_message(f"D{dwarf.id} fished but caught nothing.")

                        elif completed_task_type == 'hunt':
                             # Target animal is at resource_x, resource_y for hunt/fight tasks
                             target_x, target_y = current_task.resource_x, current_task.resource_y
                             if target_x is not None and target_y is not None:
                                 animal_at_target: Optional[Animal] = next((a for a in self.game_state.animals if a.x == target_x and a.y == target_y and a.alive), None)
                                 if animal_at_target:
                                     animal_at_target.alive = False # Kill the animal
                                     self.game_state.inventory.add_resource("food", animal_at_target.yield_food) # Gain food based on animal type
                                     self.game_state.add_debug_message(f"D{dwarf.id} hunted {animal_at_target.name}! Got {animal_at_target.yield_food} food.")
                                 else:
                                     self.game_state.add_debug_message(f"D{dwarf.id} finished hunt, but animal at ({target_x},{target_y}) moved or was gone.")
                             else:
                                 self.game_state.add_debug_message(f"Warning: Hunt task missing target coordinates.")

                        elif completed_task_type == 'fight':
                             # Target character is at resource_x, resource_y
                             target_x, target_y = current_task.resource_x, current_task.resource_y
                             if target_x is not None and target_y is not None:
                                 character_at_target: Optional[NPC] = next((c for c in self.game_state.characters if c.x == target_x and c.y == target_y and c.alive), None)
                                 if character_at_target:
                                     # Simple fight logic: character dies
                                     character_at_target.alive = False
                                     self.game_state.add_debug_message(f"D{dwarf.id} defeated {character_at_target.name}!")
                                     # Potentially trigger mission completion check
                                     if check_mission_completion(self.game_state, self.game_state.mission):
                                         complete_mission(self.game_state, self.game_state.mission)
                                 else:
                                     self.game_state.add_debug_message(f"D{dwarf.id} finished fight, but target at ({target_x},{target_y}) moved or was already defeated.")
                             else:
                                  self.game_state.add_debug_message(f"Warning: Fight task missing target coordinates.")


                        # --- Reset Dwarf State After Task Completion ---
                        dwarf.state = 'idle'
                        dwarf.path = []
                        dwarf.task = None
                        dwarf.target_x, dwarf.target_y = None, None
                        dwarf.resource_x, dwarf.resource_y = None, None
                        dwarf.task_ticks = 0

                        # --- Assign Next Task From Queue ---
                        if dwarf.task_queue:
                            next_task: Task = dwarf.task_queue.pop(0)
                            # Check reachability for the next task
                            path_to_next: Optional[List[Tuple[int, int]]] = a_star(current_map, (dwarf.x, dwarf.y), (next_task.x, next_task.y))

                            if path_to_next is not None or (dwarf.x, dwarf.y) == (next_task.x, next_task.y):
                                # Assign the task
                                if path_to_next:
                                    dwarf.state = 'moving'
                                    dwarf.path = path_to_next
                                else: # Already there
                                    if next_task.type in ['mine', 'chop', 'build', 'build_bridge']: dwarf.state = 'working'
                                    elif next_task.type in ['hunt', 'fight']: dwarf.state = 'fighting'
                                    elif next_task.type == 'fish': dwarf.state = 'fishing'
                                    elif next_task.type == 'enter': dwarf.state = 'moving' # Go to adjacent tile
                                    else: dwarf.state = 'idle'
                                    dwarf.path = []

                                dwarf.target_x, dwarf.target_y = next_task.x, next_task.y
                                dwarf.task = next_task
                                dwarf.resource_x, dwarf.resource_y = next_task.resource_x, next_task.resource_y

                                # Set initial task ticks for the queued task
                                if next_task.type in ['fish', 'hunt', 'fight']:
                                    dwarf.task_ticks = FISHING_TICKS
                                elif next_task.type == 'build' and next_task.building and next_task.building in self.game_state.buildings:
                                    dwarf.task_ticks = self.game_state.buildings[next_task.building]['ticks']
                                elif next_task.type == 'build_bridge':
                                    dwarf.task_ticks = BASE_UNDERGROUND_MINING_TICKS
                                elif next_task.type in ['mine', 'chop']:
                                     resource_tile_for_ticks = self.game_state.get_tile(next_task.resource_x, next_task.resource_y) if next_task.resource_x is not None else None
                                     base_ticks = getattr(resource_tile_for_ticks.entity, 'hardness', BASE_UNDERGROUND_MINING_TICKS) if resource_tile_for_ticks else BASE_UNDERGROUND_MINING_TICKS
                                     dwarf.task_ticks = base_ticks
                                elif next_task.type == 'enter':
                                    dwarf.task_ticks = 1
                                else:
                                    dwarf.task_ticks = 0

                                self.game_state.add_debug_message(f"Started next queued {next_task.type} task for D{dwarf.id}")
                            else:
                                # Next task in queue is unreachable, drop it
                                self.game_state.add_debug_message(f"No path to next queued task ({next_task.type} at {next_task.x},{next_task.y}) for D{dwarf.id}, task dropped")
                                # Dwarf remains idle, will check queue again next tick if needed
                        else:
                             # No tasks left in queue
                            self.game_state.add_debug_message(f"D{dwarf.id} now idle")

                else: # Dwarf is working/fighting/fishing but task object or target coords are missing?
                     self.game_state.add_debug_message(f"Warning: D{dwarf.id} in state {dwarf.state} but has invalid task/target. Task: {dwarf.task}, Target: ({dwarf.target_x},{dwarf.target_y}). Resetting.")
                     dwarf.state = 'idle' # Reset state to idle
                     dwarf.task = None
                     dwarf.path = []
                     dwarf.target_x, dwarf.target_y = None, None
                     dwarf.resource_x, dwarf.resource_y = None, None
                     dwarf.task_ticks = 0

            elif dwarf.state == 'idle':
                # --- Check Task Queue If Idle --- (Logic moved to task completion section)
                # If a dwarf finished a task and had something in queue, it was handled above.
                # If a dwarf becomes idle for other reasons (e.g., path blocked),
                # the main task assignment loop at the beginning of the update()
                # will try to assign a new task from the TaskManager if available.
                # So, no explicit queue check needed here anymore.
                pass

        # --- Spore Spread Logic (Placeholder) ---
        # Example: Trigger every 100 ticks
        # if self.game_state.tick % 100 == 0:
        #     expose_to_spores(self.game_state, intensity=1)
        pass

        # --- Mission Update Logic (Placeholder) ---
        # Example: Check every 50 ticks
        # if self.game_state.tick % 50 == 0:
        #     if check_mission_completion(self.game_state, self.game_state.mission):
        #          complete_mission(self.game_state, self.game_state.mission)
        pass

    def find_adjacent_tile(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        """Finds a random, walkable, and unoccupied adjacent tile.

        Checks the four cardinal directions (N, S, E, W) from the given (x, y).
        A tile is considered valid if it is within map bounds, its entity allows walking,
        and it is not currently occupied by another dwarf, animal, or NPC.

        Args:
            x (int): The x-coordinate of the center tile.
            y (int): The y-coordinate of the center tile.

        Returns:
            tuple[int, int] | None: The coordinates (nx, ny) of a randomly chosen valid
                                   adjacent tile, or None if no such tile exists.
        """
        options: List[Tuple[int, int]] = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT:
                tile: Optional[Tile] = self.game_state.get_tile(nx, ny)
                # Check the walkable property of the tile (delegated to entity)
                if tile and tile.walkable and \
                   not any(d.x == nx and d.y == ny for d in self.game_state.dwarves) and \
                   not any(a.x == nx and a.y == ny and a.alive for a in self.game_state.animals) and \
                   not any(c.x == nx and c.y == ny and c.alive for c in self.game_state.characters):
                    options.append((nx, ny))
        return random.choice(options) if options else None
