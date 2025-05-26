import random
from typing import TYPE_CHECKING, Dict, List, Tuple, Optional, cast

# Update constants import to relative
from .constants import MAP_WIDTH, MAP_HEIGHT, ANIMAL_MOVE_CHANCE, FISHING_TICKS, BASE_UNDERGROUND_MINING_TICKS

# Use relative imports for modules within the fungi_fortress package
from .characters import Task, Dwarf, NPC, Animal, Oracle # Added Oracle
from .missions import check_mission_completion, complete_mission
from .map_generation import generate_map, generate_mycelial_network # Ensure these are imported
# from .map_generation import generate_map, expose_to_spores # expose_to_spores moved from magic?
from .utils import a_star
from .tiles import Tile, ENTITY_REGISTRY
from .entities import ResourceNode, Structure, Sublevel, GameEntity # Added GameEntity
from .events import check_events
from .oracle_logic import get_canned_response # <--- ADD THIS IMPORT
from .text_streaming import StreamingTextType # <--- ADD THIS IMPORT
from .magic import reveal_mycelial_network, highlight_path_to_nexus, expose_to_spores # <--- MODIFIED IMPORT
# from .magic import cast_spell # Import only if cast_spell is used directly in this file

# --- LLM Interface Import --- 
try:
    from . import llm_interface # Assuming llm_interface.py is in the same directory
    LLM_INTERFACE_AVAILABLE = True
except ImportError:
    llm_interface = None
    LLM_INTERFACE_AVAILABLE = False

# Import Entity types for type hinting using relative paths
if TYPE_CHECKING:
    from .game_state import GameState, GameEvent # Added GameEvent
    from .player import Player # Added for type hints
    # Tile already imported
    # Structure, Sublevel already imported
    from .config_manager import LLMConfig # For type hint if LLMConfig used directly (was OracleConfig)

def surface_mycelium(game_state: 'GameState'):
    """Spreads mycelium floor tiles on the surface based on underground network proximity and player spore exposure.

    Only runs on the surface map (depth 0).
    Eligible tiles (grass, stone floor) can be converted if they are adjacent
    to a tile directly above an underground mycelial network node.
    The base chance increases with player spore exposure and is boosted
    if adjacent to existing surface mycelium floor.
    """
    # Only run on the surface map
    if game_state.depth != 0:
        return

    mycelium_floor = ENTITY_REGISTRY.get("mycelium_floor")
    stone_floor = ENTITY_REGISTRY.get("stone_floor")
    grass = ENTITY_REGISTRY.get("grass")
    # bridge = ENTITY_REGISTRY.get("bridge") # Add if bridges should also be convertible

    if not all([mycelium_floor, stone_floor, grass]): # Add bridge if needed
        missing = [name for name, entity in [("mycelium_floor", mycelium_floor), ("stone_floor", stone_floor), ("grass", grass)] if not entity]
        game_state.add_debug_message(f"Warning: Cannot spread surface mycelium, missing entities: {', '.join(missing)}")
        return

    # Base chance influenced by total spore exposure (adjust scaling/cap as needed)
    base_spread_chance = min(0.05, 0.000001 * game_state.player.spore_exposure) # Reduced chance significantly

    # Iterate through tiles on the current map
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            tile = game_state.get_tile(x, y)
            if not tile: continue

            # Target eligible tiles (grass, stone floor)
            if tile.entity in [stone_floor, grass]: # Add bridge if needed
                is_near_network = False
                # Check if this tile or its neighbours (3x3 area) are directly above a network node
                # This checks if the (x,y) coordinate exists as a key in the network dict
                for dy in range(-1, 2):
                    for dx in range(-1, 2):
                        check_x, check_y = x + dx, y + dy
                        if (check_x, check_y) in game_state.mycelial_network:
                            is_near_network = True
                            break
                    if is_near_network: break

                # Only spread if near the underground network
                if is_near_network:
                    # Check adjacent tiles for existing surface mycelium (boosts chance)
                    adjacent_surface_mycelium = False
                    for dy_adj in range(-1, 2):
                         for dx_adj in range(-1, 2):
                             if dx_adj == 0 and dy_adj == 0: continue
                             adj_tile = game_state.get_tile(x + dx_adj, y + dy_adj)
                             if adj_tile and adj_tile.entity == mycelium_floor:
                                 adjacent_surface_mycelium = True
                                 break
                         if adjacent_surface_mycelium: break

                    current_chance = base_spread_chance * 10 if adjacent_surface_mycelium else base_spread_chance # Higher boost adjacent
                    if random.random() < current_chance:
                         # We know mycelium_floor is not None due to the check above
                         tile.entity = cast(GameEntity, mycelium_floor)

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
        """Main game loop update function called each tick.

        Increments tick, checks events, updates tiles, handles AI, manages tasks,
        and checks mission status.
        Also processes events through the LLM interface.
        """
        # Check for Oracle timeout (prevent hanging forever) - this should work even when paused
        if (self.game_state.oracle_interaction_state == "AWAITING_LLM_RESPONSE" and 
            hasattr(self.game_state, 'oracle_query_start_tick')):
            elapsed_ticks = self.game_state.tick - self.game_state.oracle_query_start_tick
            timeout_ticks = 120  # 2 minutes at ~1 tick per second
            
            if elapsed_ticks > timeout_ticks:
                self.game_state.add_debug_message("Oracle query timed out after 2 minutes")
                self.game_state.oracle_current_dialogue.append("The Oracle's contemplation has grown too deep. The cosmic forces have withdrawn.")
                self.game_state.oracle_interaction_state = "AWAITING_PROMPT"
                self.game_state.oracle_dialogue_page_start_index = 0
        
        # --- Event Processing (including Oracle events) ---
        # Always process events, even when paused, to allow Oracle dialogue to work
        game_events = self.game_state.consume_events()
        all_llm_actions: List[Dict[str, Any]] = []
        for event in game_events:
            # Pass game_state to handle_game_event
            # Ensure llm_interface and game_state.oracle_config are available
            if LLM_INTERFACE_AVAILABLE and self.game_state.llm_config:
                 # Check if the event is an ORACLE_QUERY, then call llm_interface
                if event.get("type") == "ORACLE_QUERY":
                    llm_actions = llm_interface.handle_game_event(event, self.game_state)
                    if llm_actions:
                        all_llm_actions.extend(llm_actions)
            else:
                # Handle other non-LLM events or log if LLM components are missing
                if event.get("type") == "ORACLE_QUERY":
                    self.game_state.add_debug_message("LLM interface or Oracle config missing, cannot process Oracle query.")
                    # Potentially add a canned response action here if desired
                    all_llm_actions.append({
                        "action_type": "add_oracle_dialogue",
                        "details": {"text": "(The Oracle's connection seems offline.)", "is_llm_response": True}
                    })
                    all_llm_actions.append({"action_type": "set_oracle_state", "details": {"state": "AWAITING_PROMPT"}})

        # Process actions returned by the LLM interface or other event handlers
        # This should also work even when paused to allow Oracle dialogue updates
        if all_llm_actions:
            for action in all_llm_actions:
                action_type = action.get("action_type")
                details = action.get("details", {})
                self.game_state.add_debug_message(f"[GameLogic] Processing Action: {action_type} - Details: {details}")

                if action_type == "add_message":
                    message_text = details.get("text", "An unknown event occurred.")
                    self.game_state.add_debug_message(f"LLM: {message_text}") # Or a different log for player
                elif action_type == "spawn_character":
                    # Basic implementation: Add to characters list.
                    # Needs more robust handling (e.g., checking position, ensuring valid type)
                    char_type = details.get("type", "NPC") # Default to NPC
                    name = details.get("name", "Mysterious Figure")
                    x = details.get("x", self.game_state.cursor_x)
                    y = details.get("y", self.game_state.cursor_y)
                    
                    # Track this as oracle-generated content
                    content_entry = {
                        "type": "character",
                        "name": name,
                        "char_type": char_type,
                        "location": (x, y),
                        "tick": self.game_state.tick,
                        "details": details.copy()
                    }
                    self.game_state.oracle_generated_content.append(content_entry)
                    self.game_state.add_debug_message(f"[Oracle] Generated character: {name} ({char_type})")
                    
                    # Ensure x, y are within map bounds
                    x = max(0, min(MAP_WIDTH - 1, x))
                    y = max(0, min(MAP_HEIGHT - 1, y))

                    # Ensure tile is walkable or find nearby walkable
                    original_x, original_y = details.get('x'), details.get('y') # Store original for message
                    tile = self.game_state.get_tile(x,y)
                    initial_spawn_valid = tile and tile.walkable

                    if not initial_spawn_valid:
                        found_walkable = False
                        for r_s in range(1, 4): # Search radius
                            for dx_s in range(-r_s, r_s + 1):
                                for dy_s in range(-r_s, r_s + 1):
                                    if abs(dx_s) != r_s and abs(dy_s) != r_s: continue # Only check perimeter of square
                                    nx_s, ny_s = x + dx_s, y + dy_s
                                    if 0 <= nx_s < MAP_WIDTH and 0 <= ny_s < MAP_HEIGHT:
                                        adj_tile = self.game_state.get_tile(nx_s, ny_s)
                                        if adj_tile and adj_tile.walkable:
                                            x, y = nx_s, ny_s
                                            found_walkable = True
                                            self.game_state.add_debug_message(f"LLM spawn: Original ({original_x},{original_y}) unwalkable. Found nearby at ({x},{y}).")
                                            break
                                if found_walkable: break
                            if found_walkable: break
                        
                        if not found_walkable:
                            # Fallback to cursor position
                            cursor_tile = self.game_state.get_tile(self.game_state.cursor_x, self.game_state.cursor_y)
                            if cursor_tile and cursor_tile.walkable:
                                x, y = self.game_state.cursor_x, self.game_state.cursor_y
                                self.game_state.add_debug_message(f"Could not find walkable spot for LLM spawn near ({original_x}, {original_y}). Spawning at cursor ({x},{y}).")
                            else:
                                # All fallbacks failed, inform player through oracle dialogue
                                self.game_state.add_debug_message(f"Critical spawn fail: Could not find any walkable spot for LLM spawn near ({original_x},{original_y}) or at cursor. Action aborted.")
                                self.game_state.oracle_current_dialogue.append(f"(The Oracle's vision for a {char_type} at ({original_x},{original_y}) was obscured, and it could not manifest.)")
                                # Skip creating this character
                                continue # Continue to the next action in all_llm_actions
                    
                    # If we've reached here, x and y are valid spawn points (either original, nearby, or cursor)

                    if char_type == "Oracle": # Should Oracles be spawnable by LLM? Maybe only other NPCs/Creatures
                        new_char = Oracle(name=name, x=x, y=y)
                    elif char_type == "Dwarf": # Probably shouldn't allow LLM to spawn controllable units easily
                        # For now, let's make it an NPC if "Dwarf" type is given by LLM for safety
                        new_char = NPC(name=name, x=x, y=y) 
                        self.game_state.add_debug_message(f"LLM tried to spawn Dwarf, created NPC {name} instead.")
                    else: # Default to NPC, or could have a registry for LLM-spawnable creatures
                        new_char = NPC(name=name, x=x, y=y)
                    
                    self.game_state.characters.append(new_char)
                    self.game_state.add_debug_message(f"LLM spawned {char_type} '{name}' at ({x},{y}).")

                elif action_type == "add_oracle_dialogue":
                    dialogue_text = details.get("text", "The Oracle says nothing.")
                    # Only add dialogue if Oracle dialogue is still active to prevent late responses
                    if (self.game_state.show_oracle_dialog and 
                        self.game_state.oracle_interaction_state != "IDLE"):
                        self.game_state.oracle_current_dialogue.append(dialogue_text)
                        # If it was an LLM response and we were waiting, transition state back
                        if details.get("is_llm_response") and self.game_state.oracle_interaction_state == "AWAITING_LLM_RESPONSE":
                            self.game_state.oracle_interaction_state = "AWAITING_PROMPT"
                    else:
                        # Oracle dialogue was closed, log the response but don't interfere with UI
                        self.game_state.add_debug_message(f"Oracle response after dialogue closed: {dialogue_text[:100]}{'...' if len(dialogue_text) > 100 else ''}")
                
                elif action_type == "set_oracle_state":
                    new_state = details.get("state")
                    if new_state:
                        # Only change Oracle state if dialogue is still active
                        if (self.game_state.show_oracle_dialog and 
                            self.game_state.oracle_interaction_state != "IDLE"):
                            old_state = self.game_state.oracle_interaction_state
                            self.game_state.oracle_interaction_state = new_state
                            self.game_state.add_debug_message(f"Oracle state set to: {new_state}")
                            
                            # If state changes and new introductory dialogue is added, reset page index - REMOVING THIS
                            # reset_page_for_new_dialogue = False
                            # if new_state == "AWAITING_PROMPT" and not self.game_state.oracle_current_dialogue:
                            #      self.game_state.oracle_current_dialogue.append("The Oracle awaits your words...")
                            #      reset_page_for_new_dialogue = True
                            # elif new_state == "AWAITING_LLM_RESPONSE" and old_state != "AWAITING_LLM_RESPONSE":
                            #     if not any("Oracle contemplates" in line for line in self.game_state.oracle_current_dialogue[-2:]):
                            #         self.game_state.oracle_current_dialogue.append("The Oracle contemplates your query...")
                            #         reset_page_for_new_dialogue = True
                            # 
                            # if reset_page_for_new_dialogue:
                            #     self.game_state.oracle_dialogue_page_start_index = 0

                            # Simplified: Add standard prompts if dialogue is empty or specific transitions occur, but don't reset scroll.
                            if new_state == "AWAITING_PROMPT" and not self.game_state.oracle_current_dialogue:
                                 self.game_state.oracle_current_dialogue.append("The Oracle awaits your words...")
                            elif new_state == "AWAITING_LLM_RESPONSE" and old_state != "AWAITING_LLM_RESPONSE":
                                if not any("Oracle contemplates" in line for line in self.game_state.oracle_current_dialogue[-2:]):
                                    self.game_state.oracle_current_dialogue.append("The Oracle contemplates your query...")
                        else:
                            # Oracle dialogue was closed, ignore state change
                            self.game_state.add_debug_message(f"Oracle state change ignored (dialogue closed): {new_state}")

                elif action_type == "start_oracle_streaming":
                    # Initialize streaming Oracle response
                    if (self.game_state.show_oracle_dialog and 
                        self.game_state.oracle_interaction_state != "IDLE"):
                        # Start the streaming process
                        streaming_details = details
                        oracle_name = streaming_details.get("oracle_name", "The Oracle")
                        
                        # Initialize streaming state
                        if not hasattr(self.game_state, 'oracle_streaming_generator'):
                            self.game_state.oracle_streaming_generator = None
                        if not hasattr(self.game_state, 'oracle_streaming_active'):
                            self.game_state.oracle_streaming_active = False
                        if not hasattr(self.game_state, 'oracle_streaming_buffer'):
                            self.game_state.oracle_streaming_buffer = ""
                        
                        # Start the streaming generator
                        self.game_state.oracle_streaming_generator = llm_interface.process_oracle_streaming(
                            streaming_details["prompt"],
                            streaming_details["api_key"],
                            streaming_details["model_name"],
                            streaming_details["provider_hint"],
                            streaming_details["llm_config"], # was oracle_config
                            streaming_details["player_query"],
                            oracle_name
                        )
                        self.game_state.oracle_streaming_active = True
                        self.game_state.oracle_streaming_buffer = ""
                        self.game_state.oracle_interaction_state = "STREAMING_RESPONSE"
                        
                        self.game_state.add_debug_message(f"Started Oracle streaming response from {oracle_name}")

                elif action_type == "start_oracle_dialogue_stream":
                    # Begin streaming dialogue display
                    if (self.game_state.show_oracle_dialog and 
                        self.game_state.oracle_interaction_state == "STREAMING_RESPONSE"):
                        oracle_name = details.get("oracle_name", "The Oracle")
                        # Add a placeholder line that will be updated with streaming text
                        self.game_state.oracle_current_dialogue.append("")
                        self.game_state.oracle_dialogue_page_start_index = 0
                        self.game_state.add_debug_message(f"Started dialogue stream for {oracle_name}")

                elif action_type == "append_oracle_dialogue_stream":
                    # Add text chunk to the streaming dialogue
                    if (self.game_state.show_oracle_dialog and 
                        self.game_state.oracle_interaction_state == "STREAMING_RESPONSE"):
                        text_chunk = details.get("text_chunk", "")
                        if text_chunk:
                            # Update the streaming buffer
                            self.game_state.oracle_streaming_buffer += text_chunk
                            
                            # Update the last dialogue line with the accumulated text
                            if self.game_state.oracle_current_dialogue:
                                self.game_state.oracle_current_dialogue[-1] = self.game_state.oracle_streaming_buffer
                            else:
                                    self.game_state.oracle_current_dialogue.append(self.game_state.oracle_streaming_buffer)

                elif action_type == "finish_oracle_dialogue_stream":
                    # Complete the streaming dialogue
                    if (self.game_state.show_oracle_dialog and 
                        self.game_state.oracle_interaction_state == "STREAMING_RESPONSE"):
                        final_text = details.get("final_text", "")
                        is_error = details.get("error", False)
                        
                        # Update the final dialogue text
                        if final_text:
                            if self.game_state.oracle_current_dialogue:
                                self.game_state.oracle_current_dialogue[-1] = final_text
                            else:
                                    self.game_state.oracle_current_dialogue.append(final_text)
                        
                        # Clean up streaming state
                        self.game_state.oracle_streaming_active = False
                        self.game_state.oracle_streaming_generator = None
                        self.game_state.oracle_streaming_buffer = ""
                        
                        if details.get("is_llm_response"):
                            self.game_state.oracle_interaction_state = "AWAITING_PROMPT"
                        
                        self.game_state.add_debug_message(f"Finished Oracle dialogue stream (error: {is_error})")

                elif action_type == "update_oracle_history":
                    # Update the Oracle interaction history
                    player_query = details.get("player_query", "")
                    oracle_response = details.get("oracle_response", "")
                    
                    if player_query and oracle_response:
                        self.game_state.oracle_llm_interaction_history.append({
                            "player": player_query, 
                            "oracle": oracle_response
                        })
                        if len(self.game_state.oracle_llm_interaction_history) > 10:
                            self.game_state.oracle_llm_interaction_history.pop(0)
                        self.game_state.add_debug_message("Updated Oracle interaction history")

                elif action_type == "create_quest":
                    # Track quest generation
                    quest_name = details.get("name", "Unknown Quest")
                    content_entry = {
                        "type": "quest",
                        "name": quest_name,
                        "description": details.get("description", "A mysterious quest..."),
                        "objectives": details.get("objectives", []),
                        "rewards": details.get("rewards", []),
                        "tick": self.game_state.tick,
                        "details": details.copy()
                    }
                    self.game_state.oracle_generated_content.append(content_entry)
                    self.game_state.add_debug_message(f"[Oracle] Generated quest: {quest_name}")
                    self.game_state.new_oracle_content_count += 1
                    
                    # Add feedback to Oracle dialogue if still active
                    if (self.game_state.show_oracle_dialog and 
                        self.game_state.oracle_interaction_state != "IDLE"):
                        self.game_state.oracle_current_dialogue.append(f"✦ Quest Created: '{quest_name}' ✦")

                elif action_type == "create_item":
                    # Track item/artifact generation
                    item_name = details.get("name", "Unknown Item")
                    content_entry = {
                        "type": "item",
                        "name": item_name,
                        "description": details.get("description", "A mysterious item..."),
                        "location": details.get("location", "Unknown"),
                        "properties": details.get("properties", {}),
                        "tick": self.game_state.tick,
                        "details": details.copy()
                    }
                    self.game_state.oracle_generated_content.append(content_entry)
                    self.game_state.add_debug_message(f"[Oracle] Generated item: {item_name}")
                    self.game_state.new_oracle_content_count += 1
                    
                    # Add feedback to Oracle dialogue if still active
                    if (self.game_state.show_oracle_dialog and 
                        self.game_state.oracle_interaction_state != "IDLE"):
                        self.game_state.oracle_current_dialogue.append(f"✦ Item Created: '{item_name}' ✦")

                elif action_type == "create_character":
                    # Track character generation
                    char_name = details.get("name", "Unknown Character")
                    content_entry = {
                        "type": "character",
                        "name": char_name,
                        "description": details.get("description", "A mysterious character..."),
                        "location": details.get("location", "Unknown"),
                        "faction": details.get("faction", "None"),
                        "tick": self.game_state.tick,
                        "details": details.copy()
                    }
                    self.game_state.oracle_generated_content.append(content_entry)
                    self.game_state.add_debug_message(f"[Oracle] Generated character: {char_name}")
                    self.game_state.new_oracle_content_count += 1
                    
                    # Add feedback to Oracle dialogue if still active
                    if (self.game_state.show_oracle_dialog and 
                        self.game_state.oracle_interaction_state != "IDLE"):
                        self.game_state.oracle_current_dialogue.append(f"✦ Character Created: '{char_name}' ✦")

                elif action_type == "create_event":
                    # Track event generation
                    event_name = details.get("name", "Unknown Event")
                    content_entry = {
                        "type": "event", 
                        "name": event_name,
                        "description": details.get("description", "A mysterious event..."),
                        "trigger": details.get("trigger", "Unknown"),
                        "effects": details.get("effects", []),
                        "tick": self.game_state.tick,
                        "details": details.copy()
                    }
                    self.game_state.oracle_generated_content.append(content_entry)
                    self.game_state.add_debug_message(f"[Oracle] Generated event: {event_name}")
                    self.game_state.new_oracle_content_count += 1
                    
                    # Add feedback to Oracle dialogue if still active
                    if (self.game_state.show_oracle_dialog and 
                        self.game_state.oracle_interaction_state != "IDLE"):
                        self.game_state.oracle_current_dialogue.append(f"✦ Event Created: '{event_name}' ✦")

                # For any other action types (except simple messages), track as miscellaneous content
                elif action_type not in ["add_message", "set_oracle_state", "start_enhanced_oracle_streaming"]:  # Don't track simple message additions or state changes
                    content_entry = {
                        "type": "other",
                        "action_type": action_type,
                        "description": f"Oracle action: {action_type}",
                        "tick": self.game_state.tick,
                        "details": details.copy()
                    }
                    self.game_state.oracle_generated_content.append(content_entry)
                    self.game_state.add_debug_message(f"[Oracle] Generated content: {action_type}")

                # Add more action handlers here as needed (e.g., update_quest, give_item)

                elif action_type == "start_enhanced_oracle_streaming":
                    # Initialize enhanced streaming Oracle response with flavor text
                    if (self.game_state.show_oracle_dialog and 
                        self.game_state.oracle_interaction_state != "IDLE"):
                        # Start the enhanced streaming process
                        streaming_details = details
                        oracle_name = streaming_details.get("oracle_name", "The Oracle")
                        
                        # Initialize streaming state
                        if not hasattr(self.game_state, 'oracle_streaming_generator'):
                            self.game_state.oracle_streaming_generator = None
                        if not hasattr(self.game_state, 'oracle_streaming_active'):
                            self.game_state.oracle_streaming_active = False
                        if not hasattr(self.game_state, 'oracle_streaming_buffer'):
                            self.game_state.oracle_streaming_buffer = ""
                        if not hasattr(self.game_state, 'oracle_streaming_delay_counter'):
                            self.game_state.oracle_streaming_delay_counter = 0
                        
                        # Start the enhanced streaming generator
                        self.game_state.oracle_streaming_generator = llm_interface.process_enhanced_oracle_streaming(
                            streaming_details["prompt"],
                            streaming_details["api_key"],
                            streaming_details["model_name"],
                            streaming_details["provider_hint"],
                            streaming_details["llm_config"], # was oracle_config
                            streaming_details["player_query"],
                            oracle_name
                        )
                        self.game_state.oracle_streaming_active = True
                        self.game_state.oracle_streaming_buffer = ""
                        self.game_state.oracle_streaming_delay_counter = 0
                        self.game_state.oracle_interaction_state = "STREAMING_RESPONSE"
                        
                        # Scroll to the end of the current dialogue so new flavor text starts in view.
                        self.game_state.oracle_dialogue_page_start_index = len(self.game_state.oracle_current_dialogue)
                        
                        self.game_state.add_debug_message(f"Started enhanced Oracle streaming response from {oracle_name}")

                # Log unhandled actions
                else:
                    if action_type != "add_message":  # Don't log message additions as unhandled
                        self.game_state.add_debug_message(f"[GameLogic] Unhandled Action: {action_type}")
        
        # --- Process Oracle Streaming (if active) ---
        self._process_oracle_streaming()
        
        # Return to normal game flow after paused-allowed operations
        if self.game_state.paused:
            return

        # Increment tick
        self.game_state.tick += 1

        # Check events
        check_events(self.game_state)

        # Update active pulses (BEFORE tile highlights are reduced)
        self._update_active_pulses()

        # Update tiles (reduce highlight duration)
        for row in self.game_state.map:
            for tile in row:
                if tile.highlight_ticks > 0:
                    tile.highlight_ticks -= 1

        # Handle animals
        if self.game_state.depth == 0:  # Only on surface
            for animal in self.game_state.animals:
                if random.random() < ANIMAL_MOVE_CHANCE:
                    dx = random.randint(-1, 1)
                    dy = random.randint(-1, 1)
                    new_x = animal.x + dx
                    new_y = animal.y + dy
                    new_tile = self.game_state.get_tile(new_x, new_y)
                    if new_tile and new_tile.walkable:
                        animal.x = new_x
                        animal.y = new_y

        # Check for stacked entities and spread them
        occupied_positions = {}
        all_entities = self.game_state.dwarves + self.game_state.characters + self.game_state.animals
        
        for entity in all_entities:
            pos = (entity.x, entity.y)
            if pos not in occupied_positions:
                occupied_positions[pos] = []
            occupied_positions[pos].append(entity)
        
        # Spread stacked entities
        for pos, entities in occupied_positions.items():
            if len(entities) > 1:
                for i, entity in enumerate(entities[1:], 1):
                    # Try to find nearby empty position
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            if dx == 0 and dy == 0:
                                continue
                            new_x = pos[0] + dx
                            new_y = pos[1] + dy
                            new_pos = (new_x, new_y)
                            
                            if new_pos not in occupied_positions or len(occupied_positions.get(new_pos, [])) == 0:
                                tile = self.game_state.get_tile(new_x, new_y)
                                if tile and tile.walkable:
                                    entity.x = new_x
                                    entity.y = new_y
                                    occupied_positions[new_pos] = [entity]
                                    break
                        else:
                            continue
                        break

        # Assign pending tasks to idle dwarves
        pending_tasks = list(self.game_state.task_manager.tasks)
        if pending_tasks: # Add this check
            self.game_state.add_debug_message(f"Pending tasks to assign: {len(pending_tasks)}")

        for task_idx, task in enumerate(pending_tasks):
            self.game_state.add_debug_message(f"Attempting to assign Task {task_idx}: {task.type} at ({task.x},{task.y}) for target ({task.resource_x},{task.resource_y})")
            assigned = False
            for dwarf in self.game_state.dwarves:
                self.game_state.add_debug_message(f"  Checking Dwarf {dwarf.id} ({dwarf.state}) at ({dwarf.x},{dwarf.y}) for task {task.type}")
                if dwarf.state == 'idle' and not dwarf.task:
                    self.game_state.add_debug_message(f"    Dwarf {dwarf.id} is idle. Finding path to ({task.x},{task.y})...")
                    # Find path to task
                    path = a_star(self.game_state.map, (dwarf.x, dwarf.y), (task.x, task.y))
                    self.game_state.add_debug_message(f"    Path for Dwarf {dwarf.id} to Task {task.type}: {path}")
                    if path is not None: # Path can be empty list if start == goal, which is fine.
                        dwarf.task = task
                        dwarf.path = path # Corrected line: use path directly
                        dwarf.state = 'moving'
                        self.game_state.task_manager.remove_task(task)
                        self.game_state.add_debug_message(f"  SUCCESS: Assigned Task {task.type} to Dwarf {dwarf.id}. Path: {dwarf.path}")
                        assigned = True
                        break 
                    else:
                        self.game_state.add_debug_message(f"    No path found for Dwarf {dwarf.id} to task {task.type} at ({task.x},{task.y}).")
            
            if not assigned:
                self.game_state.add_debug_message(f"  FAILED: Task {task.type} at ({task.x},{task.y}) could not be assigned to any dwarf.")

        # Update dwarves
        for dwarf in self.game_state.dwarves:
            self._update_dwarf(dwarf)

        # Spread mycelium on surface based on underground network
        surface_mycelium(self.game_state)

        # Check mission completion
        check_mission_completion(self.game_state, self.game_state.mission)

    def _update_active_pulses(self):
        """Updates the state of all active mycelial pulses."""
        if not hasattr(self.game_state, 'active_pulses') or not self.game_state.active_pulses:
            return

        pulses_to_remove = []
        for i, pulse in enumerate(self.game_state.active_pulses):
            pulse["ticks_on_current_tile"] += 1

            # Determine which tiles are part of the current pulse segment
            pulse["tiles_to_render"] = []
            path = pulse["path"]
            head_index = pulse["current_tile_index"]
            
            for j in range(pulse["pulse_length"]):
                tile_index_in_pulse = head_index - j
                if 0 <= tile_index_in_pulse < len(path):
                    pulse["tiles_to_render"].append(path[tile_index_in_pulse])
                else:
                    break # Pulse tail goes off the start of the path
            
            # Move pulse head
            if pulse["ticks_on_current_tile"] >= pulse["pulse_speed"]:
                pulse["ticks_on_current_tile"] = 0
                pulse["current_tile_index"] += 1

                # Check if pulse reached end of path
                if pulse["current_tile_index"] >= len(pulse["path"]):
                    pulse["remaining_sends"] -= 1
                    if pulse["remaining_sends"] > 0:
                        # Reset for next send from nexus
                        pulse["current_tile_index"] = 0
                        pulse["ticks_on_current_tile"] = 0
                        self.game_state.add_debug_message(f"Pulse {pulse['id']} re-sending from nexus. {pulse['remaining_sends']} sends left.")
                    else:
                        # Pulse series finished
                        pulses_to_remove.append(i)
                        self.game_state.add_debug_message(f"Pulse {pulse['id']} finished all sends.")
            
            # Ensure tiles_to_render is up-to-date if pulse didn't move but head is beyond path start
            # This handles the case where the pulse is just starting or has a tail off the path beginning.
            if not pulse["tiles_to_render"] and pulse["current_tile_index"] < len(path):
                for j in range(pulse["pulse_length"]):
                    tile_index_in_pulse = pulse["current_tile_index"] - j
                    if 0 <= tile_index_in_pulse < len(path):
                        pulse["tiles_to_render"].append(path[tile_index_in_pulse])
                    else:
                        break

        # Remove completed pulses (iterate in reverse to avoid index issues)
        for i in sorted(pulses_to_remove, reverse=True):
            del self.game_state.active_pulses[i]

    def _process_oracle_streaming(self):
        """Process Oracle streaming in a separate method to avoid code duplication."""
        if not (hasattr(self.game_state, 'oracle_streaming_active') and 
                self.game_state.oracle_streaming_active and 
                hasattr(self.game_state, 'oracle_streaming_generator') and
                self.game_state.oracle_streaming_generator is not None):
            return
        
        # Time budget for Oracle streaming within this game tick
        time_spent_streaming_this_tick_ms = 0
        max_streaming_time_per_tick_ms = 50  # Reduced to 50ms for better game performance
        MAX_DIALOGUE_LINE_WIDTH = 56 # Adjusted from 58 to 56 to match renderer
        MAX_CONTENT_H_APPROX = 14

        # Initialize delay counter if it doesn't exist
        if not hasattr(self.game_state, 'oracle_streaming_delay_counter'):
            self.game_state.oracle_streaming_delay_counter = 0

        # Decrement counter by the time of a game logic tick (approx 100ms)
        if self.game_state.oracle_streaming_delay_counter > 0:
            self.game_state.oracle_streaming_delay_counter -= 100

        # Process chunks within time budget
        while (self.game_state.oracle_streaming_delay_counter <= 0 and 
               time_spent_streaming_this_tick_ms < max_streaming_time_per_tick_ms):
            try:
                streaming_action = next(self.game_state.oracle_streaming_generator)
                action_type = streaming_action.get("action_type")
                details = streaming_action.get("details", {})
                
                if action_type == "stream_text_chunk":
                    # Pass only details, max_width and max_height are not used by the revised _process_stream_text_chunk
                    self._process_stream_text_chunk(details) 
                elif action_type == "stream_pause":
                    # Handle stream_pause action if needed
                    pass
                
                time_spent_streaming_this_tick_ms += 10  # Approximate time per chunk

            except StopIteration:
                # Commit any final buffered text from the streaming_line_buffer
                final_line_text, final_line_style = self.game_state.oracle_streaming_line_buffer
                if final_line_text: # Only commit if there's actual text
                    self.game_state.oracle_current_dialogue.append((final_line_text, final_line_style))
                
                self._cleanup_oracle_streaming() # Resets active flag, generator, and line buffer
                self.game_state.add_debug_message("Oracle streaming completed successfully (StopIteration).")
                
                if self.game_state.oracle_interaction_state == "STREAMING_RESPONSE":
                    self.game_state.oracle_interaction_state = "AWAITING_PROMPT"
                    
                    # Adjust scroll to show the end of the completed dialogue.
                    # Renderer's dialog_h = 28, max_content_h = 22.
                    max_content_h_approx = 22 
                    if self.game_state.oracle_current_dialogue:
                        num_dialogue_lines = len(self.game_state.oracle_current_dialogue)
                        self.game_state.oracle_dialogue_page_start_index = max(0, num_dialogue_lines - max_content_h_approx)
                    else:
                        self.game_state.oracle_dialogue_page_start_index = 0
                        
                    self.game_state.add_debug_message("Oracle interaction state set to AWAITING_PROMPT.")
                break

            except Exception as e:
                # Log the exception from the generator itself
                self.game_state.add_debug_message(f"Critical Error during Oracle streaming generator processing: {e}")
                # Attempt to display an error in the dialogue
                # Commit any partial line before showing error.
                error_intro_text, error_intro_style = self.game_state.oracle_streaming_line_buffer
                if error_intro_text:
                    self.game_state.oracle_current_dialogue.append((error_intro_text, error_intro_style))

                self.game_state.oracle_current_dialogue.append(("Oracle: A sudden disruption in the stream...", "ITALIC"))
                self.game_state.oracle_current_dialogue.append(("Oracle: Please try again later.", "ITALIC"))
                
                self._cleanup_oracle_streaming() # Resets active flag, generator, and line buffer
                
                self.game_state.oracle_interaction_state = "AWAITING_PROMPT"
                # Similar scroll adjustment for error case
                max_content_h_approx_err = 22
                if self.game_state.oracle_current_dialogue:
                    num_dialogue_lines_err = len(self.game_state.oracle_current_dialogue)
                    self.game_state.oracle_dialogue_page_start_index = max(0, num_dialogue_lines_err - max_content_h_approx_err)
                else:
                    self.game_state.oracle_dialogue_page_start_index = 0
                self.game_state.add_debug_message(f"Oracle state set to AWAITING_PROMPT due to error in streaming generator.")
                break

    def _process_stream_text_chunk(self, details): # Removed max_width, max_height
        """Process a single streaming text chunk. Modifies oracle_streaming_line_buffer.
        Commits to oracle_current_dialogue only on newlines or style changes."""
        text_char = details.get("text", "")
        target = details.get("target", "oracle_dialogue")
        delay_ms = details.get("delay_ms", 0) # Keep delay for pacing
        
        if target != "oracle_dialogue" or text_char is None:
            return
        
        current_char_style = self._get_text_style(details.get("text_type"), details)
        current_line_text, current_line_style = self.game_state.oracle_streaming_line_buffer
        
        # Handle style changes: if style changes and there's existing text in buffer, commit it.
        if current_char_style != current_line_style and current_line_text:
            self.game_state.oracle_current_dialogue.append((current_line_text, current_line_style))
            current_line_text = "" # Text for the new style starts fresh
        
        # Update current_line_style to the new character's style for the buffer
        current_line_style = current_char_style
        
        if text_char == '\n':
            # Commit the buffered line to dialogue
            self.game_state.oracle_current_dialogue.append((current_line_text, current_line_style))
            # Reset buffer for the next line (style of the \n character, i.e., current_line_style, persists for the new empty line)
            current_line_text = "" 
        else:
            # Append character to buffer's text. No wrapping logic here.
            current_line_text += text_char
        
        # Update the game state's streaming line buffer
        self.game_state.oracle_streaming_line_buffer = (current_line_text, current_line_style)
        
        # Set delay for this chunk
        self.game_state.oracle_streaming_delay_counter = delay_ms
        
        # Auto-scroll logic (based on committed lines only) - can be removed if renderer handles all scrolling
        # MAX_CONTENT_H_APPROX = 14 # This constant was here before
        # if len(self.game_state.oracle_current_dialogue) > MAX_CONTENT_H_APPROX:
        #    self.game_state.oracle_dialogue_page_start_index = len(self.game_state.oracle_current_dialogue) - MAX_CONTENT_H_APPROX
    
    def _get_text_style(self, text_type_str, details):
        """Determine the style for a text chunk."""
        if isinstance(text_type_str, str):
            if text_type_str == "flavor_text":
                return "ITALIC"
            elif text_type_str == "oracle_dialogue":
                if details.get("is_error") or details.get("is_waiting"):
                    return "ITALIC"
        elif hasattr(text_type_str, 'name'):  # Enum type
            try:
                from .text_streaming import StreamingTextType
                if text_type_str == StreamingTextType.FLAVOR_TEXT:
                    return "ITALIC"
                elif text_type_str == StreamingTextType.ORACLE_DIALOGUE:
                    if details.get("is_error") or details.get("is_waiting"):
                        return "ITALIC"
            except ImportError:
                pass
        return "NORMAL"

    def _cleanup_oracle_streaming(self):
        """Clean up Oracle streaming state."""
        self.game_state.oracle_streaming_active = False
        self.game_state.oracle_streaming_generator = None
        self.game_state.oracle_streaming_buffer = "" 
        self.game_state.oracle_streaming_delay_counter = 0
        self.game_state.oracle_streaming_line_buffer = ("", "NORMAL") # Reset line buffer

    def _update_dwarf(self, dwarf):
        # Log if state changed or if dwarf is active
        if dwarf.state != dwarf.previous_state or (dwarf.state != 'idle' or dwarf.task or dwarf.path):
            self.game_state.add_debug_message(f"Updating D{dwarf.id}. Prev State: {dwarf.previous_state}, New State: {dwarf.state}, Task: {dwarf.task.type if dwarf.task else 'None'}, Path len: {len(dwarf.path) if dwarf.path else 0}")

        # Only log extensively if the dwarf is not idle or has a task/path
        # if dwarf.state != 'idle' or dwarf.task or dwarf.path: # This condition is now part of the above log
            # self.game_state.add_debug_message(f"BEGIN _update_dwarf for D{dwarf.id}, id(dwarf)={id(dwarf)}. State: {dwarf.state}, Task: {dwarf.task.type if dwarf.task else 'None'}, Path len: {len(dwarf.path) if dwarf.path else 0}, Action Progress: {dwarf.action_progress}")

        original_state_for_tick = dwarf.state # Store state at start of this update for comparison later

        if dwarf.state == 'moving' and dwarf.path:
            # Move towards target
            next_pos = dwarf.path[0]
            next_tile = self.game_state.get_tile(next_pos[0], next_pos[1])
            
            if next_tile and next_tile.walkable:
                dwarf.x, dwarf.y = next_pos
                dwarf.path.pop(0)
                
                if not dwarf.path:
                    # Reached destination
                    if dwarf.task:
                        if dwarf.task.type == 'move':
                            self.game_state.add_debug_message(f"D{dwarf.id} completed MOVE task to ({dwarf.x},{dwarf.y}). Setting state to IDLE.")
                            dwarf.state = 'idle'
                            dwarf.task = None # Clear the completed move task
                            dwarf.action_progress = 0
                        elif dwarf.task.type == 'talk':
                            # Handle talk completion directly
                            self.game_state.add_debug_message(f"D{dwarf.id} reached destination for TALK task at ({dwarf.x},{dwarf.y}) targeting ({dwarf.task.resource_x},{dwarf.task.resource_y}).")
                            target_entity = None
                            if dwarf.task.resource_x is not None and dwarf.task.resource_y is not None:
                                for char in self.game_state.characters:
                                    if char.x == dwarf.task.resource_x and char.y == dwarf.task.resource_y:
                                        target_entity = char
                                        break
                            
                            if target_entity:
                                if isinstance(target_entity, Oracle):
                                    self.game_state.active_oracle_entity_id = target_entity.name
                                    self.game_state.show_oracle_dialog = True
                                    self.game_state.paused = True
                                    self.game_state.oracle_interaction_state = "AWAITING_OFFERING"
                                    offering_cost_str = ", ".join([f"{qty} {res.replace('_', ' ')}" for res, qty in self.game_state.oracle_offering_cost.items()])
                                    self.game_state.oracle_current_dialogue = [
                                        (f"{target_entity.name} desires an offering to share deeper insights:", "NORMAL"),
                                        (f"({offering_cost_str}).", "NORMAL"),
                                        ("Will you make this offering? (Y/N)", "NORMAL")
                                    ]
                                    self.game_state.add_debug_message(f"D{dwarf.id} initiated Oracle dialogue with {target_entity.name}. Awaiting offering.")
                                elif isinstance(target_entity, NPC):
                                    self.game_state.add_debug_message(f"D{dwarf.id} talks to {target_entity.name}. They grunt noncommittally.")
                                else:
                                    self.game_state.add_debug_message(f"D{dwarf.id} tried to talk to non-NPC/Oracle entity: {target_entity.name if hasattr(target_entity, 'name') else 'Unknown Entity'}")
                            else:
                                self.game_state.add_debug_message(f"D{dwarf.id} could not find target entity for TALK task at ({dwarf.task.resource_x},{dwarf.task.resource_y}).")

                            dwarf.state = 'idle'
                            dwarf.task = None
                            dwarf.action_progress = 0
                        else:
                            # For other tasks (chop, mine, etc.), transition to that action state
                            task_type_to_action_state = {
                                "mine": "mining",
                                "chop": "chopping",
                                "build": "building",
                                "fish": "fishing",
                                "fight": "fighting",
                                "enter": "entering",
                                "move": "moving", # Should be caught above, but keep for safety
                                "build_bridge": "building_bridge"
                            }
                            action_state = task_type_to_action_state.get(dwarf.task.type)

                            if action_state:
                                self.game_state.add_debug_message(f"D{dwarf.id} reached destination for {dwarf.task.type} task. Setting state to {action_state}.")
                                dwarf.state = action_state
                                dwarf.action_progress = 0
                            else:
                                self.game_state.add_debug_message(f"WARNING: D{dwarf.id} reached destination for unknown task type '{dwarf.task.type}'. Setting to idle.")
                                dwarf.state = 'idle'
                                dwarf.task = None # Clear unknown task
                                dwarf.action_progress = 0
                    else:
                        # No task, should be idle (this case might be redundant if task is always set for moving)
                        self.game_state.add_debug_message(f"D{dwarf.id} finished moving but had no task. Setting to IDLE.")
                        dwarf.state = 'idle'
            else:
                # Path blocked, recalculate
                self.game_state.add_debug_message(f"D{dwarf.id} path blocked at {next_pos[0]},{next_pos[1]}. Current pos: ({dwarf.x},{dwarf.y})")
                if dwarf.task:
                    self.game_state.add_debug_message(f"D{dwarf.id} attempting to recalculate path for task {dwarf.task.type} to ({dwarf.task.x},{dwarf.task.y}).")
                    new_path = a_star(self.game_state.map, (dwarf.x, dwarf.y), (dwarf.task.x, dwarf.task.y))
                    if new_path:
                        self.game_state.add_debug_message(f"D{dwarf.id} recalculated path: {new_path}")
                        dwarf.path = new_path
                    else:
                        # Can't reach task
                        self.game_state.add_debug_message(f"D{dwarf.id} path recalculation failed. Setting to IDLE.")
                        dwarf.state = 'idle'
                        dwarf.task = None
                else:
                    self.game_state.add_debug_message(f"D{dwarf.id} path blocked but no task. Setting to IDLE.")
                    dwarf.state = 'idle'
        elif dwarf.state in ['mining', 'chopping', 'building', 'fishing', 'fighting', 'entering', 'building_bridge']:
            self.game_state.add_debug_message(f"D{dwarf.id} is in state '{dwarf.state}'. Matched action state. Calling _handle_dwarf_action (current action_progress: {dwarf.action_progress}).")
            self._handle_dwarf_action(dwarf)
            self.game_state.add_debug_message(f"D{dwarf.id} AFTER _handle_dwarf_action. State: {dwarf.state}, Action Progress: {dwarf.action_progress}")
        
        # Handle task queue
        if dwarf.state == 'idle' and dwarf.task_queue:
            next_task = dwarf.task_queue.pop(0)
            path = a_star(self.game_state.map, (dwarf.x, dwarf.y), (next_task.x, next_task.y))
            if path:
                dwarf.task = next_task
                dwarf.path = path
                dwarf.state = 'moving'

        # Update previous_state at the end of the dwarf's update logic for this tick
        if original_state_for_tick != dwarf.state: # If state changed during this tick
            self.game_state.add_debug_message(f"D{dwarf.id} state changed from {original_state_for_tick} to {dwarf.state} within _update_dwarf.")
        
        dwarf.previous_state = dwarf.state # Update previous_state for the next tick

    def _handle_dwarf_action(self, dwarf):
        self.game_state.add_debug_message(f"ENTERING _handle_dwarf_action for D{dwarf.id} (State: {dwarf.state}, Task Type: {dwarf.task.type if dwarf.task else 'No Task'})")
        if not dwarf.task:
            if dwarf.state != 'idle':
                self.game_state.add_debug_message(f"D{dwarf.id} in state {dwarf.state} HAD NO TASK. Setting to idle.")
                dwarf.state = 'idle'
            return
        
        # self.game_state.add_debug_message(f"D{dwarf.id} handling action: {dwarf.state}, progress: {dwarf.action_progress}, task: {dwarf.task.type} at ({dwarf.task.x},{dwarf.task.y})")
        dwarf.action_progress += 1
        
        action_durations = {
            'mining': BASE_UNDERGROUND_MINING_TICKS if self.game_state.depth != 0 else 10,
            'chopping': 10,
            'building': 10,
            'fishing': FISHING_TICKS,
            'fighting': 5,
            'entering': 5,
            'build_bridge': BASE_UNDERGROUND_MINING_TICKS
        }
        duration = action_durations.get(dwarf.state, 10)
        self.game_state.add_debug_message(f"D{dwarf.id} action {dwarf.state}. Progress: {dwarf.action_progress}/{duration}. Task target: ({dwarf.task.resource_x},{dwarf.task.resource_y})")

        if dwarf.action_progress >= duration:
            self.game_state.add_debug_message(f"D{dwarf.id} action {dwarf.state} Met Duration. Progress: {dwarf.action_progress}/{duration}. Completing action.")
            # Tile dwarf is standing on to perform the action
            tile_dwarf_is_on = self.game_state.get_tile(dwarf.task.x, dwarf.task.y)
            
            if tile_dwarf_is_on:
                try:
                    self.game_state.add_debug_message(f"D{dwarf.id} calling _complete_dwarf_action for {dwarf.state} (standing on {tile_dwarf_is_on.x},{tile_dwarf_is_on.y})")
                    self._complete_dwarf_action(dwarf, tile_dwarf_is_on) # Pass the tile dwarf is on
                    self.game_state.add_debug_message(f"D{dwarf.id} _complete_dwarf_action finished for {dwarf.state}")
                except Exception as e:
                    self.game_state.add_debug_message(f"!!! EXCEPTION in _complete_dwarf_action for D{dwarf.id} {dwarf.state}: {e}")
                    # Log traceback for more details
                    import traceback
                    self.game_state.add_debug_message(f"Traceback: {traceback.format_exc()}")
            else:
                self.game_state.add_debug_message(f"D{dwarf.id} could not get tile ({dwarf.task.x},{dwarf.task.y}) where dwarf is standing for action {dwarf.state}")
            
            self.game_state.add_debug_message(f"D{dwarf.id} resetting state from {dwarf.state} to idle. Clearing task {dwarf.task.type}.")
            dwarf.state = 'idle'
            dwarf.task = None
            dwarf.action_progress = 0
        # else:
            # self.game_state.add_debug_message(f"D{dwarf.id} action {dwarf.state} continuing. Progress: {dwarf.action_progress}/{duration}")

    def _complete_dwarf_action(self, dwarf, tile):
        """Complete a dwarf's action and apply its effects."""
        if dwarf.state == 'mining':
            self._complete_mining(dwarf, tile)
        elif dwarf.state == 'chopping':
            self._complete_chopping(dwarf, tile)
        elif dwarf.state == 'building':
            self._complete_building(dwarf, tile)
        elif dwarf.state == 'fishing':
            self._complete_fishing(dwarf, tile)
        elif dwarf.state == 'fighting':
            self._complete_fighting(dwarf, tile)
        elif dwarf.state == 'entering':
            self._complete_entering(dwarf, tile)
        elif dwarf.state == 'building_bridge':
            self._complete_build_bridge(dwarf, tile)

    def _complete_mining(self, dwarf, tile_dwarf_is_on):
        """Complete mining action."""
        if dwarf.task and dwarf.task.resource_x is not None and dwarf.task.resource_y is not None:
            target_tile = self.game_state.get_tile(dwarf.task.resource_x, dwarf.task.resource_y)
            if target_tile and hasattr(target_tile.entity, 'resource_type') and hasattr(target_tile.entity, 'yield_amount'):
                resource = target_tile.entity.resource_type
                amount = target_tile.entity.yield_amount
                self.game_state.inventory.add_resource(resource, amount)
                self.game_state.add_debug_message(f"D{dwarf.id} mined {amount} {resource} from ({dwarf.task.resource_x},{dwarf.task.resource_y})")

                # Grant spore exposure if the entity has spore_yield
                if hasattr(target_tile.entity, 'spore_yield') and target_tile.entity.spore_yield > 0:
                    expose_to_spores(self.game_state, target_tile.entity.spore_yield)
                    self.game_state.add_debug_message(f"Player gained {target_tile.entity.spore_yield} spore exposure from {resource}.")

                # Change TARGET tile to floor
                floor_entity = ENTITY_REGISTRY.get("mycelium_floor" if self.game_state.depth != 0 else "stone_floor")
                if floor_entity:
                    target_tile.entity = floor_entity
                else:
                    self.game_state.add_debug_message(f"D{dwarf.id} mining: Could not find floor entity to replace mined target.")

                # If magic fungi was mined, reveal the network
                if resource == "magic_fungi":
                    fungus_location = (dwarf.task.resource_x, dwarf.task.resource_y)
                    message = highlight_path_to_nexus(self.game_state, fungus_location)
                    self.game_state.add_debug_message(f"D{dwarf.id} mined Magic Fungi. {message}")

            elif target_tile:
                self.game_state.add_debug_message(f"D{dwarf.id} mining target ({dwarf.task.resource_x},{dwarf.task.resource_y}) entity '{target_tile.entity.name}' does not have resource_type or yield_amount.")
            else:
                self.game_state.add_debug_message(f"D{dwarf.id} mining: Target tile ({dwarf.task.resource_x},{dwarf.task.resource_y}) not found.")
        else:
            self.game_state.add_debug_message(f"D{dwarf.id} mining task has no resource_x/resource_y defined.")

    def _complete_chopping(self, dwarf, tile_dwarf_is_on):
        """Complete chopping action."""
        if dwarf.task and dwarf.task.resource_x is not None and dwarf.task.resource_y is not None:
            target_tile = self.game_state.get_tile(dwarf.task.resource_x, dwarf.task.resource_y)
            if target_tile and hasattr(target_tile.entity, 'resource_type') and hasattr(target_tile.entity, 'yield_amount'):
                resource = target_tile.entity.resource_type
                amount = target_tile.entity.yield_amount
                self.game_state.inventory.add_resource(resource, amount)
                self.game_state.add_debug_message(f"D{dwarf.id} chopped {amount} {resource} from ({dwarf.task.resource_x},{dwarf.task.resource_y})")
        
                # Change TARGET tile to grass
                grass_entity = ENTITY_REGISTRY.get("grass")
                if grass_entity:
                    target_tile.entity = grass_entity
                else:
                    self.game_state.add_debug_message(f"D{dwarf.id} chopping: Could not find grass entity to replace chopped target.")
            elif target_tile:
                self.game_state.add_debug_message(f"D{dwarf.id} chopping target ({dwarf.task.resource_x},{dwarf.task.resource_y}) entity '{target_tile.entity.name}' does not have resource_type or yield_amount.")
            else:
                self.game_state.add_debug_message(f"D{dwarf.id} chopping: Target tile ({dwarf.task.resource_x},{dwarf.task.resource_y}) not found.")
        else:
            self.game_state.add_debug_message(f"D{dwarf.id} chopping task has no resource_x/resource_y defined.")

    def _complete_building(self, dwarf, tile):
        """Complete building action."""
        structure_name = dwarf.task.structure_type
        structure = ENTITY_REGISTRY.get(structure_name)
        
        if structure and self.game_state.inventory.can_afford(structure.cost):
            for resource, amount in structure.cost:
                self.game_state.inventory.remove_resource(resource, amount)
            
            tile.entity = structure
            self.game_state.add_debug_message(f"D{dwarf.id} built {structure_name}")

    def _complete_fishing(self, dwarf, tile):
        """Complete fishing action."""
        self.game_state.inventory.add_resource("Fish", 1)
        self.game_state.add_debug_message(f"D{dwarf.id} caught 1 Fish")

    def _complete_fighting(self, dwarf, tile):
        """Complete fighting action."""
        # Find enemy at location
        for enemy in self.game_state.characters:
            if enemy.x == tile.x and enemy.y == tile.y and hasattr(enemy, 'health'):
                enemy.health -= 10
                if enemy.health <= 0:
                    self.game_state.characters.remove(enemy)
                    self.game_state.add_debug_message(f"D{dwarf.id} defeated {enemy.name}")
                else:
                    self.game_state.add_debug_message(f"D{dwarf.id} damaged {enemy.name}")
                break

    def _complete_entering(self, dwarf, tile):
        """Complete entering sublevel action."""
        self._trigger_sublevel_entry(dwarf, tile)

    def _complete_build_bridge(self, dwarf, tile_dwarf_is_on):
        """Complete building a bridge segment."""
        if not (dwarf.task and dwarf.task.resource_x is not None and dwarf.task.resource_y is not None):
            self.game_state.add_debug_message(f"D{dwarf.id} build_bridge task has no resource_x/resource_y defined.")
            return

        target_bridge_tile = self.game_state.get_tile(dwarf.task.resource_x, dwarf.task.resource_y)
        bridge_entity_data = ENTITY_REGISTRY.get("bridge") # Get the GameEntity data for bridge

        # Define bridge cost here
        bridge_cost = [("wood", 1)]

        if not target_bridge_tile:
            self.game_state.add_debug_message(f"D{dwarf.id} build_bridge: Target tile ({dwarf.task.resource_x},{dwarf.task.resource_y}) not found.")
            return
        
        if not bridge_entity_data:
            self.game_state.add_debug_message(f"D{dwarf.id} build_bridge: 'bridge' entity data not found in registry.")
            return

        if not self.game_state.inventory.can_afford(bridge_cost):
            self.game_state.add_debug_message(f"D{dwarf.id} cannot afford to build bridge. Needs: {bridge_cost}")
            return # Exit early if cannot afford
        
        if target_bridge_tile.entity.name == "Water":
            # Resources are deducted now that we've confirmed affordability and target type
            for resource, amount in bridge_cost:
                self.game_state.inventory.remove_resource(resource, amount)
            
            target_bridge_tile.entity = bridge_entity_data # Assign the GameEntity instance
            self.game_state.add_debug_message(f"D{dwarf.id} built bridge segment at ({dwarf.task.resource_x},{dwarf.task.resource_y})")
        else:
            self.game_state.add_debug_message(f"D{dwarf.id} cannot build bridge at ({dwarf.task.resource_x},{dwarf.task.resource_y}). Target is not Water, it is {target_bridge_tile.entity.name}.")
