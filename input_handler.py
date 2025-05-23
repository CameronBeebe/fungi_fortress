import curses
import random
from typing import TYPE_CHECKING, Optional

# Update constants import to relative
from .constants import MAP_WIDTH, MAP_HEIGHT, MAX_TASKS, FISHING_TICKS, BASE_UNDERGROUND_MINING_TICKS, SPELL_HOTKEYS

# Use relative imports for sibling modules
from .characters import Task, Dwarf, NPC, Animal, Oracle
from .map_generation import generate_map, generate_mycelial_network
from .missions import generate_mission # Commented out in original, keep commented
from .player import Player
from .magic import cast_spell, spells
from .utils import a_star
from .tiles import Tile, ENTITY_REGISTRY
from .entities import ResourceNode, Structure, Sublevel, GameEntity

# Import for Oracle logic
from .oracle_logic import get_canned_response 

if TYPE_CHECKING:
    from .game_state import GameState, InteractionEventDetails

class InputHandler:
    """Processes user input based on the current game state.

    Handles keyboard input for various game modes:
    - Map navigation and interaction.
    - Inventory screen.
    - Shop screen (including item selection and descent confirmation).
    - Legend screen.
    - Spell casting.
    - Task assignment.
    - General commands (pause, quit).

    Attributes:
        game_state (GameState): Reference to the main game state object.
    """
    def __init__(self, game_state: 'GameState'):
        """Initializes the InputHandler.

        Args:
            game_state (GameState): The game state object to be manipulated by this handler.
        """
        self.game_state = game_state

    def handle_input(self, key: int) -> bool:
        """Processes a single key press based on the current game state.

        Dispatches the key to different handling logic depending on whether
        the inventory, shop, or legend is displayed, or if the game is in the
        main map view.

        Args:
            key (int): The integer representation of the key pressed (from curses).

        Returns:
            bool: False if the game should quit (user pressed 'q'), True otherwise.

        Key Bindings (Summary):

        Global:
          q: Quit game.
          p: Toggle pause.
          i: Toggle inventory screen.
          l: Toggle legend screen (pauses game).

        Inventory Screen (`show_inventory == True`):
          i, q: Close inventory.

        Shop Screen (`in_shop == True`):
          If `shop_confirm == True`:
            y: Confirm descent, sell uncarried items, generate next level.
            n: Cancel descent confirmation, return to shop selection.
          If `shop_confirm == False`:
            1-6: Increase carry amount for corresponding resource (stone, wood, ...).
            !@#$%^: Decrease carry amount for corresponding resource.
            s: Display potential gold gain from selling uncarried items.
            r: Reset carried amounts (non-gold) to maximum possible within weight limit.
            y: Initiate descent confirmation prompt.
            n: Cancel shop/descent, reset carry amounts.

        Legend Screen (`show_legend == True`):
          l: Close legend (unpauses game).

        Main Map View (default):
          Arrow Keys: Move cursor.
          s: Cycle selected spell.
          c: Cast selected spell.
          m: Assign 'mine'/'chop' task (on resource) or 'move' task (on walkable) at cursor.
          b: Assign 'build_bridge' (on water) or 'build' (Mycelial Nexus on designated site) task at cursor.
          f: Assign 'fish' (on water), 'hunt' (on animal), or 'fight' (on NPC) task at cursor.
          e: Assign 'enter' task (on Sublevel), call interact() (on interactive Structure), or exit current sublevel.
          t: Talk to adjacent NPC (currently placeholder, defeats Vyx).
          d: Enter shop/descent preparation screen.
          1-5: Select spell in corresponding hotbar slot.
        """
        # Convert key to character if it's a number key
        key_char = chr(key) if 32 <= key <= 126 else None

        if self.game_state.show_inventory:
            if key in [ord('i'), ord('q')]:
                self.game_state.show_inventory = False
                return True
            return True # Absorb other keys when inventory is open

        if self.game_state.show_oracle_dialog:
            # Allow 't' or 'q' to close the dialog regardless of sub-state first
            if key == ord('t') or key == ord('q'):
                self.game_state.show_oracle_dialog = False
                self.game_state.paused = False
                self.game_state.oracle_interaction_state = "IDLE"
                self.game_state.oracle_current_dialogue = []
                self.game_state.active_oracle_entity_id = None
                self.game_state.add_debug_message(f"Oracle dialog closed via '{chr(key)}'.")
                return True

            current_oracle = self._get_active_oracle()

            if self.game_state.oracle_interaction_state == "AWAITING_OFFERING":
                if key == ord('y'):
                    if current_oracle and self._handle_offering(current_oracle):
                        # Offering successful, transition to prompt state (Phase 2)
                        # For now, let's show a placeholder message and allow exit
                        self.game_state.oracle_interaction_state = "AWAITING_PROMPT" # This will be next phase
                        self.game_state.oracle_current_dialogue = ["The Oracle acknowledges your offering.", "It awaits your query... (LLM interaction pending implementation)"]
                    else:
                        # Offering failed (not enough resources or no oracle)
                        # Message already added by _handle_offering or implicitly by current_oracle being None
                        # Stay in AWAITING_OFFERING or let renderer show canned response for no_offering_made
                        if current_oracle:
                             self.game_state.oracle_current_dialogue = get_canned_response(current_oracle, "no_offering_made")
                        # self.game_state.oracle_interaction_state = "SHOWING_CANNED_RESPONSE" # Or revert, or just let current state render appropriate message
                elif key == ord('n'):
                    self.game_state.add_debug_message("Declined Oracle's offering.")
                    if current_oracle:
                        self.game_state.oracle_current_dialogue = get_canned_response(current_oracle, "no_offering_made")
                    self.game_state.oracle_interaction_state = "SHOWING_CANNED_RESPONSE" # Show canned response, then allow exit
                return True # Absorb other keys in this state
            
            elif self.game_state.oracle_interaction_state == "SHOWING_CANNED_RESPONSE":
                # If showing canned response, any key (or specific like enter/q/t) could close
                # For now, 'q' is the main exit, handled above. If other keys should close here:
                if key in [ord('t'), ord('q'), curses.KEY_ENTER, 10, 13]: # Allow exit with t, q, or Enter
                    self.game_state.show_oracle_dialog = False
                    self.game_state.paused = False
                    self.game_state.oracle_interaction_state = "IDLE"
                    self.game_state.oracle_current_dialogue = []
                    self.game_state.active_oracle_entity_id = None
                    return True
                return True # Absorb other keys
            
            # Placeholder for AWAITING_PROMPT and other future states (Phase 2+)
            # For now, any key in these states will just be absorbed
            # elif self.game_state.oracle_interaction_state == "AWAITING_PROMPT":
            #     # ... handle text input ...
            #     return True 

            return True # Absorb any unhandled keys while oracle dialog is open

        if self.game_state.in_shop:
            # --- Shop Input Handling ---
            # Define resources EXCLUDING gold for add/remove keys
            shop_resources = ['stone', 'wood', 'food', 'crystals', 'fungi', 'magic_fungi'] # Exclude 'gold'
            add_keys = {ord(str(i)): res for i, res in enumerate(shop_resources, 1)}
            remove_key_chars = '!@#$%^' # Adjust to match number of shop_resources
            remove_keys = {ord(char): res for char, res in zip(remove_key_chars, shop_resources)}

            max_carry_weight = self.game_state.player.max_carry_weight
            # Calculate current weight EXCLUDING gold from shop_carry 
            current_carry_weight = sum(qty for res, qty in self.game_state.shop_carry.items() if res != 'gold')

            if self.game_state.shop_confirm:
                if key == ord('y'):
                    # --- Actual Descent Processing --- 
                    sell_values = {"stone": 1, "wood": 1, "food": 2, "crystals": 15, "fungi": 3, "magic_fungi": 10} # Exclude gold sell value
                    gold_gained_from_sale = 0
                    original_gold = self.game_state.inventory.resources.get("gold", 0)
                    
                    # 1. Create the new inventory based *only* on what's marked to carry (excluding gold initially)
                    new_inventory_resources = {res: qty for res, qty in self.game_state.shop_carry.items() if qty > 0 and res != 'gold'}
                    new_inventory_special_items = self.game_state.inventory.special_items.copy() 

                    # 2. Calculate gold gained from selling the difference of NON-GOLD items
                    for res, current_qty in self.game_state.inventory.resources.items():
                        if res == 'gold': continue # Skip gold
                        carry_qty = self.game_state.shop_carry.get(res, 0)
                        if current_qty > carry_qty:
                            sell_qty = current_qty - carry_qty
                            gold_gained_from_sale += sell_qty * sell_values.get(res, 0)
                    
                    # 3. Add original gold + gained gold to the new inventory
                    new_inventory_resources["gold"] = original_gold + gold_gained_from_sale
                    
                    # 4. Update the main inventory state
                    self.game_state.inventory.resources = new_inventory_resources
                    self.game_state.inventory.special_items = new_inventory_special_items 
                    if gold_gained_from_sale > 0:
                        self.game_state.add_debug_message(f"Gained {gold_gained_from_sale} Gold from selling uncarried items.")

                    # 5. Proceed with level change and map generation
                    current_carry_weight = sum(qty for res, qty in self.game_state.inventory.resources.items() if res != 'gold') # Exclude gold weight
                    self.game_state.add_debug_message(f"Preparing descent to Depth {self.game_state.depth + 1} with {current_carry_weight} units carried (+{self.game_state.inventory.resources.get('gold', 0)} Gold).")
                    
                    self.game_state.depth += 1 
                    spawn_found = False
                    self.game_state.main_map, self.game_state.nexus_site, self.game_state.magic_fungi_locations = generate_map(MAP_WIDTH, MAP_HEIGHT, self.game_state.depth, self.game_state.mission)
                    self.game_state.map = self.game_state.main_map
                    
                    # Generate new mycelial network for the new map
                    assert self.game_state.nexus_site is not None # Ensure nexus site exists
                    self.game_state.mycelial_network = generate_mycelial_network(
                        self.game_state.main_map,
                        self.game_state.nexus_site,
                        self.game_state.magic_fungi_locations
                    )
                    self.game_state.network_distances = self.game_state.calculate_network_distances()
                    
                    # Find spawn point on the NEW map
                    for y in range(MAP_HEIGHT):
                        for x in range(MAP_WIDTH):
                            if self.game_state.map[y][x].walkable:
                                self.game_state.dwarves = [Dwarf(x, y, 0)] # Recreate dwarf at new spawn
                                self.game_state.cursor_x, self.game_state.cursor_y = x, y
                                spawn_found = True
                                break
                        if spawn_found:
                            break
                    if not spawn_found:
                        # Fallback spawn logic
                        fallback_x, fallback_y = MAP_WIDTH // 2, MAP_HEIGHT // 2
                        self.game_state.dwarves = [Dwarf(fallback_x, fallback_y, 0)] 
                        self.game_state.cursor_x, self.game_state.cursor_y = fallback_x, fallback_y
                        self.game_state.add_debug_message("Warning: No walkable spawn found, placed dwarf at center")
                    
                    self.game_state.animals = [] # Reset animals
                    self.game_state.task_manager.clear_tasks()
                    self.game_state.mission_complete = False
                    self.game_state.in_shop = False # Exit shop state
                    for sub_level in self.game_state.sub_levels:
                        self.game_state.sub_levels[sub_level]["active"] = False
                        self.game_state.sub_levels[sub_level]["map"] = None
                    self.game_state.shop_confirm = False # Reset flag
                    self.game_state.inventory.reset_resources_gained()
                    self.game_state.shop_carry = {k: 0 for k in self.game_state.inventory.resources.keys()} # Clear selection post-descent
                    # --- Temporarily Disable Mission Generation --- 
                    # self.game_state.mission = generate_mission(self.game_state)
                    self.game_state.mission = {} # Assign empty mission for now
                    # --- End Disable --- 
                    
                    # Generate map AFTER resetting mission state potentially?
                    self.game_state.main_map, self.game_state.nexus_site, self.game_state.magic_fungi_locations = generate_map(MAP_WIDTH, MAP_HEIGHT, self.game_state.depth, self.game_state.mission)
                    self.game_state.map = self.game_state.main_map
                    
                    # Generate new mycelial network for the new map
                    assert self.game_state.nexus_site is not None # Ensure nexus site exists
                    self.game_state.mycelial_network = generate_mycelial_network(
                        self.game_state.main_map,
                        self.game_state.nexus_site,
                        self.game_state.magic_fungi_locations
                    )
                    self.game_state.network_distances = self.game_state.calculate_network_distances()
                    
                    # NPC spawn logic (should happen after map gen)
                    self.game_state.characters = [] # Clear previous NPCs
                    for npc_name in self.game_state.mission.get("required_npcs", []):
                        # ... (existing NPC placement logic, ensure it uses self.game_state.map) ...
                        npc_spawn_found = False
                        for _ in range(50): # Try placing NPC 50 times
                            nx, ny = random.randint(0, MAP_WIDTH - 1), random.randint(0, MAP_HEIGHT - 1)
                            if self.game_state.map[ny][nx].walkable and \
                               not any(c.x == nx and c.y == ny for c in self.game_state.characters) and \
                               not any(d.x == nx and d.y == ny for d in self.game_state.dwarves) and \
                               not any(a.x == nx and a.y == ny and a.alive for a in self.game_state.animals):
                                self.game_state.characters.append(NPC(npc_name, nx, ny))
                                npc_spawn_found = True
                                break
                        if not npc_spawn_found:
                            self.game_state.add_debug_message(f"Warning: Could not place required NPC {npc_name}")
                    
                    self.game_state.add_debug_message(f"Descended to Depth {self.game_state.depth}.")
                    return True # Handled
                elif key == ord('n'):
                    self.game_state.in_shop = False
                    self.game_state.shop_carry = {k: 0 for k in self.game_state.inventory.resources.keys()}
                    return True

            # Handle Add Keys (1-6 for non-gold)
            if key in add_keys:
                res_to_add = add_keys[key]
                if self.game_state.inventory.resources[res_to_add] > self.game_state.shop_carry[res_to_add]:
                    if current_carry_weight + 1 <= max_carry_weight:
                        self.game_state.shop_carry[res_to_add] += 1
                    else:
                        self.game_state.add_debug_message("Cannot carry more weight!")
                else:
                    self.game_state.add_debug_message(f"No more {res_to_add} available to carry")
            
            # Handle Remove Keys (!@#$%^ for non-gold)
            elif key in remove_keys:
                res_to_remove = remove_keys[key]
                if self.game_state.shop_carry[res_to_remove] > 0:
                    self.game_state.shop_carry[res_to_remove] -= 1
            
            # Handle Sell ('s') - Calculate potential gain for non-gold items
            elif key == ord('s'):
                sell_values = {"stone": 1, "wood": 1, "food": 2, "crystals": 15, "fungi": 3, "magic_fungi": 10} # Excludes gold
                potential_gold_gain = 0
                sold_items_summary = []
                for res, current_qty in self.game_state.inventory.resources.items():
                    if res == 'gold': continue # Skip gold
                    carry_qty = self.game_state.shop_carry.get(res, 0)
                    if current_qty > carry_qty: 
                        sell_qty = current_qty - carry_qty 
                        gain = sell_qty * sell_values.get(res, 0)
                        if gain > 0:
                            potential_gold_gain += gain
                            sold_items_summary.append(f"{sell_qty} {res}")
                
                if potential_gold_gain > 0:
                    summary_str = ", ".join(sold_items_summary)
                    self.game_state.add_debug_message(f"Auto-selling uncarried {summary_str} for {potential_gold_gain} Gold upon descent.")
                else:
                    self.game_state.add_debug_message("Nothing uncarried to sell.")
            
            # Handle Reset ('r') - Reset non-gold items to default carry
            elif key == ord('r'):
                self.game_state.shop_carry = {k: 0 for k in self.game_state.inventory.resources.keys()} # Reset all including gold
                temp_carry_weight = 0
                for res in shop_resources: # Iterate only non-gold resources
                    available = self.game_state.inventory.resources.get(res, 0)
                    can_take = max_carry_weight - temp_carry_weight
                    take_amount = min(available, can_take)
                    if take_amount > 0:
                        self.game_state.shop_carry[res] = take_amount
                        temp_carry_weight += take_amount
                    if temp_carry_weight >= max_carry_weight:
                        break
                # Gold is not affected by reset, just non-gold resource selection
                self.game_state.add_debug_message(f"Shop reset non-gold carry ({temp_carry_weight}/{max_carry_weight})")
            # Handle Confirm ('y') - prompt
            elif key == ord('y'):
                self.game_state.shop_confirm = True
                self.game_state.add_debug_message("Confirm descent? (y/n)")
            # Handle Cancel ('n')
            elif key == ord('n'):
                self.game_state.in_shop = False
                self.game_state.shop_carry = {k: 0 for k in self.game_state.inventory.resources.keys()}
            return True # Handled shop input
            # --- End Shop Input Handling ---

        if self.game_state.show_legend:
            if key == ord('l'):
                self.game_state.show_legend = False
                self.game_state.paused = False
                return True

        if key == ord('q'):
            return False
        elif key == ord('p'):
            self.game_state.paused = not self.game_state.paused
            self.game_state.add_debug_message("Paused" if self.game_state.paused else "Running")
        elif key == ord('i'):
            self.game_state.show_inventory = not self.game_state.show_inventory
        elif key == ord('l'):
            self.game_state.show_legend = True
            self.game_state.paused = True
            self.game_state.add_debug_message("Legend displayed")
        elif key == ord('s'):
            # Cycle through spells using the new cycle_spell_selection method
            if not self.game_state.player.spells:
                self.game_state.add_debug_message("You haven't learned any spells yet.")
            else:
                next_spell = self.game_state.player.cycle_spell_selection(self.game_state.selected_spell)
                if next_spell:
                    self.game_state.selected_spell = next_spell
                    slot_index = self.game_state.player.get_spell_slot_index(next_spell)
                    self.game_state.add_debug_message(f"Selected spell: {next_spell} (Slot {slot_index + 1})")
                else:
                    self.game_state.add_debug_message("No spells available in slots")
        elif key == ord('c'):
            # Cast the currently selected spell
            if self.game_state.selected_spell:
                result = cast_spell(self.game_state.selected_spell, self.game_state)
                self.game_state.add_debug_message(result)
            else:
                self.game_state.add_debug_message("No spell selected. Use number keys (1-5) or 's' to select a spell.")
        elif key == curses.KEY_UP:
            self.game_state.cursor_y = max(0, self.game_state.cursor_y - 1)
        elif key == curses.KEY_DOWN:
            self.game_state.cursor_y = min(MAP_HEIGHT - 1, self.game_state.cursor_y + 1)
        elif key == curses.KEY_LEFT:
            self.game_state.cursor_x = max(0, self.game_state.cursor_x - 1)
        elif key == curses.KEY_RIGHT:
            self.game_state.cursor_x = min(MAP_WIDTH - 1, self.game_state.cursor_x + 1)
        elif key == ord('m'):
            tile = self.game_state.map[self.game_state.cursor_y][self.game_state.cursor_x]
            entity = tile.entity
            self.game_state.add_debug_message(f"Attempting task on {entity.name} at ({self.game_state.cursor_x}, {self.game_state.cursor_y})")
            dwarf = self.game_state.dwarves[0] if self.game_state.dwarves else None
            if not dwarf:
                self.game_state.add_debug_message("No dwarf available for task")
                return True

            # Check if the entity is a resource node that can be mined/chopped
            if isinstance(entity, ResourceNode) and entity.resource_type in ["stone", "fungi", "magic_fungi", "wood"]:
                path = a_star(self.game_state.map, (dwarf.x, dwarf.y), (self.game_state.cursor_x, self.game_state.cursor_y), adjacent=True)
                task_type = 'chop' if entity.resource_type == "wood" else 'mine'
                if path is not None and len(path) > 0:
                    ax, ay = path[-1] # Adjacent tile to work from
                    task = Task(ax, ay, task_type, self.game_state.cursor_x, self.game_state.cursor_y)
                    if self.game_state.task_manager.add_task(task):
                        self.game_state.add_debug_message(f"{task_type.capitalize()} task assigned for {entity.name} at ({self.game_state.cursor_x}, {self.game_state.cursor_y}) via ({ax}, {ay})")
                elif path is not None and len(path) == 0 and abs(dwarf.x - self.game_state.cursor_x) + abs(dwarf.y - self.game_state.cursor_y) == 1:
                    # Dwarf is already adjacent
                    task = Task(dwarf.x, dwarf.y, task_type, self.game_state.cursor_x, self.game_state.cursor_y)
                    if self.game_state.task_manager.add_task(task):
                        self.game_state.add_debug_message(f"{task_type.capitalize()} task assigned for {entity.name} at ({self.game_state.cursor_x}, {self.game_state.cursor_y}) from current pos")
                else:
                    self.game_state.add_debug_message(f"No adjacent walkable path to {entity.name}")
            # Check if the tile is walkable (implying a move task)
            elif tile.walkable:
                # Move task goes directly to the tile
                task = Task(self.game_state.cursor_x, self.game_state.cursor_y, 'move')
                if self.game_state.task_manager.add_task(task):
                    self.game_state.add_debug_message(f"Move task assigned to ({self.game_state.cursor_x}, {self.game_state.cursor_y})")
            else:
                 self.game_state.add_debug_message(f"Cannot assign task to non-resource, non-walkable entity: {entity.name}")
        elif key == ord('b'): # Build logic (Bridge or Structure)
            cursor_pos = (self.game_state.cursor_x, self.game_state.cursor_y)
            tile_at_cursor = self.game_state.get_tile(cursor_pos[0], cursor_pos[1])

            if not tile_at_cursor:
                self.game_state.add_debug_message("Cursor out of bounds.")
                return True

            entity_at_cursor = tile_at_cursor.entity
            dwarf = self.game_state.dwarves[0] if self.game_state.dwarves else None

            if not dwarf:
                self.game_state.add_debug_message("No dwarf available for task")
                return True

            # --- Check if building a Bridge ---
            if entity_at_cursor.name == "Water":
                task_type = 'build_bridge'
                target_x, target_y = cursor_pos

                # Find adjacent walkable tile for dwarf to stand
                path = a_star(self.game_state.map, (dwarf.x, dwarf.y), (target_x, target_y), adjacent=True)

                if path is not None and len(path) > 0:
                    adjacent_x, adjacent_y = path[-1] # Adjacent tile to work from
                    task = Task(adjacent_x, adjacent_y, task_type, target_x, target_y)
                    if self.game_state.task_manager.add_task(task):
                        self.game_state.add_debug_message(f"Bridge building task assigned for ({target_x}, {target_y}) via ({adjacent_x}, {adjacent_y})")
                    else:
                        self.game_state.add_debug_message(f"Failed to add bridge task (manager full?)")
                elif path is not None and len(path) == 0 and abs(dwarf.x - target_x) + abs(dwarf.y - target_y) == 1:
                    # Dwarf is already adjacent
                    task = Task(dwarf.x, dwarf.y, task_type, target_x, target_y)
                    if self.game_state.task_manager.add_task(task):
                        self.game_state.add_debug_message(f"Bridge building task assigned for ({target_x}, {target_y}) from current pos")
                    else:
                        self.game_state.add_debug_message(f"Failed to add bridge task (manager full?)")
                else:
                     self.game_state.add_debug_message(f"No adjacent walkable path to water tile at ({target_x}, {target_y}) for bridge building.")

            # --- Else, try building a Structure (Original Logic) ---
            else:
                # TODO: Implement a build menu or selection mechanism
                # For now, assume 'b' always tries to build a Nexus
                building_name = "Mycelial Nexus"
                # Check if building_name exists in the registry and is a Structure
                if building_name not in ENTITY_REGISTRY or not isinstance(ENTITY_REGISTRY[building_name], Structure):
                     self.game_state.add_debug_message(f"Error: Building '{building_name}' not defined as a Structure.")
                     return True
                # building_entity = ENTITY_REGISTRY[building_name] # Get the Structure instance

                can_build_here = False
                # 1. Check if cursor is on the designated nexus_site for this level
                if self.game_state.nexus_site and cursor_pos == self.game_state.nexus_site:
                    # 2. Check the buildable flag on the TILE's *current* entity at the site
                    if tile_at_cursor.buildable: # Uses the property delegating to the entity
                        can_build_here = True
                    else:
                        self.game_state.add_debug_message(f"Designated Nexus site ({tile_at_cursor.entity.name}) is not buildable!")
                else:
                     self.game_state.add_debug_message("Can only build a Nexus on the designated site for this level")

                if can_build_here:
                    # Fetch requirements
                    if building_name not in self.game_state.buildings:
                        self.game_state.add_debug_message(f"Error: Build requirements for '{building_name}' not found.")
                        return True
                    reqs = self.game_state.buildings[building_name]

                    # Check resources
                    has_resources = True
                    for res, qty in reqs["resources"].items():
                        if self.game_state.inventory.resources.get(res, 0) < qty:
                            has_resources = False
                            self.game_state.add_debug_message(f"Need {qty} {res}")
                            break
                    if has_resources:
                        for item, qty in reqs["special_items"].items():
                            if self.game_state.inventory.special_items.get(item, 0) < qty:
                                has_resources = False
                                self.game_state.add_debug_message(f"Need {qty} {item}")
                                break
                    
                    if has_resources:
                        # Find path and assign task
                        path = a_star(self.game_state.map, (dwarf.x, dwarf.y), cursor_pos, adjacent=True)
                        if path is not None: # Path exists (or dwarf is already adjacent)
                            # Determine adjacent tile for task creation
                            task_x, task_y = dwarf.x, dwarf.y # Default if already adjacent
                            if len(path) > 0:
                                task_x, task_y = path[-1]

                            task = Task(task_x, task_y, 'build', cursor_pos[0], cursor_pos[1], building=building_name)
                            if self.game_state.task_manager.add_task(task):
                                self.game_state.add_debug_message(f"Assigned build task for {building_name} at {cursor_pos} via ({task_x},{task_y})")
                            else:
                                self.game_state.add_debug_message(f"Failed to add build task (manager full?) - Resources potentially lost!")
                                # TODO: Consider refunding resources if add_task fails
                        else:
                            self.game_state.add_debug_message(f"No adjacent walkable path to build {building_name} at {cursor_pos}")
                    # else: Message about lacking resources already sent
                # else: Message about build location already sent
        elif key == ord('f'):
            tile_at_cursor = self.game_state.get_tile(self.game_state.cursor_x, self.game_state.cursor_y)
            if not tile_at_cursor:
                self.game_state.add_debug_message("Cannot interact: Cursor out of bounds.")
                return True # Stop processing if tile is invalid

            entity = tile_at_cursor.entity
            dwarf = self.game_state.dwarves[0] if self.game_state.dwarves else None
            if not dwarf:
                self.game_state.add_debug_message("No dwarf available for task")
                return True

            task_type = None
            target_description = ""
            # Check for water entity for fishing
            if entity.name == "Water": # Use name comparison for specific terrain types like water
                 task_type = 'fish'
                 target_description = "water tile"
            # Check for animals at the cursor location
            elif any(a.x == self.game_state.cursor_x and a.y == self.game_state.cursor_y and a.alive for a in self.game_state.animals):
                 task_type = 'hunt'
                 target_description = "animal"
            # Check for NPCs at the cursor location
            elif any(c.x == self.game_state.cursor_x and c.y == self.game_state.cursor_y and c.alive for c in self.game_state.characters):
                 task_type = 'fight'
                 target_description = "character"

            if task_type:
                path = a_star(self.game_state.map, (dwarf.x, dwarf.y), (self.game_state.cursor_x, self.game_state.cursor_y), adjacent=True)
                if path is not None and len(path) > 0:
                    ax, ay = path[-1]
                    task = Task(ax, ay, task_type, self.game_state.cursor_x, self.game_state.cursor_y)
                    if self.game_state.task_manager.add_task(task):
                        self.game_state.add_debug_message(f"{task_type.capitalize()} task at ({self.game_state.cursor_x}, {self.game_state.cursor_y}) via ({ax}, {ay})")
                elif path is not None and len(path) == 0 and abs(dwarf.x - self.game_state.cursor_x) + abs(dwarf.y - self.game_state.cursor_y) == 1:
                    task = Task(dwarf.x, dwarf.y, task_type, self.game_state.cursor_x, self.game_state.cursor_y)
                    if self.game_state.task_manager.add_task(task):
                        self.game_state.add_debug_message(f"{task_type.capitalize()} task at ({self.game_state.cursor_x}, {self.game_state.cursor_y}) from current pos")
                else:
                    self.game_state.add_debug_message(f"No adjacent walkable path for {task_type} task")
            else:
                self.game_state.add_debug_message(f"No fishing/fighting target at cursor ({entity.name})")
        elif key == ord('e'): # Enter / Interact
            tile_at_cursor = self.game_state.get_tile(self.game_state.cursor_x, self.game_state.cursor_y)
            if not tile_at_cursor:
                self.game_state.add_debug_message("Cannot interact: Cursor out of bounds.")
                return True # Stop processing if tile is invalid

            entity = tile_at_cursor.entity
            in_sub_level = any(sub_data.get("active", False) for sub_name, sub_data in self.game_state.sub_levels.items())

            if not in_sub_level:
                # --- Check for adjacent Oracle FIRST --- 
                target_char = None
                cx, cy = self.game_state.cursor_x, self.game_state.cursor_y
                for char_entity in self.game_state.characters:
                    if isinstance(char_entity, Oracle) and \
                       abs(char_entity.x - cx) <= 1 and \
                       abs(char_entity.y - cy) <= 1 and \
                       char_entity.alive:
                        target_char = char_entity
                        break
                
                if target_char: # Found an adjacent Oracle
                    # --- Oracle Interaction: Trigger Event --- 
                    details: InteractionEventDetails = {
                        "actor_id": "player",
                        "target_id": target_char.name, 
                        "target_type": "Oracle",
                        "location": (target_char.x, target_char.y), # Use Oracle's location
                        "outcome": None # Placeholder for now
                    }
                    self.game_state.add_event("interaction", details)
                    self.game_state.add_debug_message(f"Initiated interaction with Oracle {target_char.name}.")
                    # NOTE: Returning True here prevents further 'e' checks (Sublevel/Structure) in this turn
                    return True 
                
                # --- If no Oracle, proceed with original checks --- 
                elif isinstance(entity, Sublevel):
                    # ... (original sublevel 'enter' task assignment logic) ...
                    sub_level_name = entity.name
                    entry_x, entry_y = self.game_state.cursor_x, self.game_state.cursor_y
                    dwarf = self.game_state.dwarves[0] if self.game_state.dwarves else None

                    if not dwarf:
                        self.game_state.add_debug_message("No dwarf available to enter.")
                        return True

                    path = a_star(self.game_state.map, (dwarf.x, dwarf.y), (entry_x, entry_y), adjacent=True)

                    if path is not None:
                        adjacent_x, adjacent_y = dwarf.x, dwarf.y
                        if len(path) > 0:
                            adjacent_x, adjacent_y = path[-1]
                        
                        task = Task(adjacent_x, adjacent_y, 'enter', entry_x, entry_y)
                        if self.game_state.task_manager.add_task(task):
                            self.game_state.add_debug_message(f"Task assigned: Dwarf entering {entity.name} at ({entry_x}, {entry_y}) via ({adjacent_x}, {adjacent_y})")
                        else:
                            self.game_state.add_debug_message(f"Failed to add 'enter' task (manager full?)")
                    else:
                        self.game_state.add_debug_message(f"Cannot reach entrance of {entity.name} at ({entry_x}, {entry_y}).")

                elif isinstance(entity, Structure) or entity.interactive:
                    # ... (original structure interaction logic) ...
                    tile_at_cursor.interact(self.game_state)
                else:
                    self.game_state.add_debug_message(f"Nothing to interact with: {entity.name}")

            elif in_sub_level:
                # ... (original exit logic) ...
                # --- Existing Exit Logic ---
                active_sub_level_name = None
                for sub_name, sub_data in self.game_state.sub_levels.items():
                    if sub_data.get("active", False):
                         active_sub_level_name = sub_name
                         break

                if active_sub_level_name:
                    self.game_state.sub_levels[active_sub_level_name]["active"] = False
                    self.game_state.map = self.game_state.main_map
                    
                    if self.game_state.nexus_site:
                        self.game_state.mycelial_network = generate_mycelial_network(
                            self.game_state.main_map,
                            self.game_state.nexus_site,
                            self.game_state.magic_fungi_locations
                        )
                    else:
                        self.game_state.mycelial_network = {}
                        self.game_state.add_debug_message("Warning: Nexus site missing on main map, cannot restore network.")
                    self.game_state.network_distances = self.game_state.calculate_network_distances()
                    
                    if self.game_state.entry_x is not None and self.game_state.entry_y is not None:
                        return_x, return_y = self.game_state.entry_x, self.game_state.entry_y
                    elif self.game_state.nexus_site:
                         return_x, return_y = self.game_state.nexus_site
                         self.game_state.add_debug_message("Warning: No entry point saved, returning to Nexus site.")
                    else:
                        return_x, return_y = MAP_WIDTH // 2, MAP_HEIGHT // 2
                        self.game_state.add_debug_message("Warning: No entry point or Nexus site, returning to center.")
                        
                    self.game_state.cursor_x, self.game_state.cursor_y = return_x, return_y
                    for dwarf in self.game_state.dwarves:
                        dwarf.x = max(0, min(MAP_WIDTH - 1, return_x + random.randint(-1, 1)))
                        dwarf.y = max(0, min(MAP_HEIGHT - 1, return_y + random.randint(-1, 1)))
                    self.game_state.player.update_state("location", "Main Level")
                    self.game_state.add_debug_message(f"Returned to main level from {active_sub_level_name}")
                else:
                     self.game_state.add_debug_message("Error: In sub-level but couldn't determine which one.")
        elif key == ord('t'): # Talk / Task Interaction / Toggle Dialog
            # This key now has dual purpose based on context (handled above if dialog is open)
            
            target_x, target_y = self.game_state.cursor_x, self.game_state.cursor_y
            dwarf = self.game_state.dwarves[0] if self.game_state.dwarves else None

            if not dwarf:
                self.game_state.add_debug_message("No dwarf available to talk.")
                return True

            target_oracle: Optional[Oracle] = None
            for char_entity in self.game_state.characters:
                if isinstance(char_entity, Oracle) and \
                   char_entity.x == target_x and \
                   char_entity.y == target_y and \
                   char_entity.alive:
                    target_oracle = char_entity
                    break
            
            if target_oracle:
                # Check for adjacency
                is_adjacent = (abs(dwarf.x - target_oracle.x) <= 1 and \
                               abs(dwarf.y - target_oracle.y) <= 1 and \
                               not (dwarf.x == target_oracle.x and dwarf.y == target_oracle.y))

                if is_adjacent:
                    # Open dialog directly
                    self.game_state.active_oracle_entity_id = target_oracle.name
                    self.game_state.show_oracle_dialog = True
                    self.game_state.paused = True
                    self.game_state.oracle_current_dialogue = []
                    self.game_state.oracle_llm_interaction_history = []
                    self.game_state.oracle_prompt_buffer = ""

                    api_key_value = self.game_state.oracle_config.api_key if self.game_state.oracle_config else "No OracleConfig object"
                    self.game_state.add_debug_message(f"InputHandler (adjacent): API key from config = '{api_key_value}'")

                    if self.game_state.oracle_config and self.game_state.oracle_config.api_key:
                        self.game_state.oracle_interaction_state = "AWAITING_OFFERING"
                        offering_cost_str = ", ".join([f"{qty} {res.replace('_', ' ')}" for res, qty in self.game_state.oracle_offering_cost.items()])
                        self.game_state.oracle_current_dialogue.extend([
                            f"{target_oracle.name} desires an offering to share deeper insights:",
                            f"({offering_cost_str}).",
                            "Will you make this offering? (Y/N)"
                        ])
                    else:
                        self.game_state.oracle_interaction_state = "SHOWING_CANNED_RESPONSE"
                        self.game_state.oracle_current_dialogue = get_canned_response(target_oracle, "no_api_key")
                    self.game_state.add_debug_message(f"Initiated talk with Oracle (adjacent): {target_oracle.name}")
                else:
                    # Not adjacent, create a 'talk' task
                    path = a_star(self.game_state.map, (dwarf.x, dwarf.y), (target_oracle.x, target_oracle.y), adjacent=True)
                    if path is not None: # Path can be empty if already adjacent, but we handled that. So path must have items or be None.
                        if len(path) > 0:
                            adj_x, adj_y = path[-1] # Adjacent tile to work from
                            task = Task(adj_x, adj_y, 'talk', resource_x=target_oracle.x, resource_y=target_oracle.y)
                            if self.game_state.task_manager.add_task(task):
                                self.game_state.add_debug_message(f"'Talk' task assigned for {target_oracle.name} at ({target_oracle.x}, {target_oracle.y}) via ({adj_x}, {adj_y})")
                            else:
                                self.game_state.add_debug_message(f"Failed to add 'talk' task (manager full?) for {target_oracle.name}")
                        else: # Path is empty, means dwarf is already on an adjacent tile (should have been caught by is_adjacent)
                              # This case implies a logic flaw if reached, but defensively open dialog.
                            self.game_state.add_debug_message(f"Warning: Path to adjacent for talk task was empty, but not caught by adjacency check. Opening dialog for {target_oracle.name}.")
                            self.game_state.active_oracle_entity_id = target_oracle.name
                            self.game_state.show_oracle_dialog = True # Open dialog as a fallback
                            # (Simplified dialog setup, can be expanded like above)
                            self.game_state.oracle_interaction_state = "SHOWING_CANNED_RESPONSE" 
                            self.game_state.oracle_current_dialogue = get_canned_response(target_oracle, "greeting")


                    else:
                        self.game_state.add_debug_message(f"No path to talk to Oracle {target_oracle.name} at ({target_oracle.x}, {target_oracle.y})")
            else:
                self.game_state.add_debug_message("No Oracle at cursor to talk to.")
            return True
        elif key == ord('d'): # Enter Shop / Prepare for Descent
            # Calculate default carry state FIRST, excluding gold
            max_carry_weight = self.game_state.player.max_carry_weight
            shop_resources = ['stone', 'wood', 'food', 'crystals', 'fungi', 'magic_fungi'] # Exclude gold
            self.game_state.shop_carry = {k: 0 for k in self.game_state.inventory.resources.keys()} # Reset first
            temp_carry_weight = 0
            for res in shop_resources: # Iterate only non-gold resources
                available = self.game_state.inventory.resources.get(res, 0)
                can_take = max_carry_weight - temp_carry_weight
                take_amount = min(available, can_take)
                if take_amount > 0:
                    self.game_state.shop_carry[res] = take_amount
                    temp_carry_weight += take_amount
                if temp_carry_weight >= max_carry_weight:
                    break 
            
            # Now enter the shop state
            self.game_state.in_shop = True
            self.game_state.shop_confirm = False # Ensure confirm flag is reset
            self.game_state.add_debug_message(f"Descent prep: Default carry ({temp_carry_weight}/{max_carry_weight}). Adjust or confirm (y).")
        # Handle spell hotkeys (1-5)
        elif key_char in SPELL_HOTKEYS:
            slot_index = SPELL_HOTKEYS[key_char]
            spell = self.game_state.player.get_spell_in_slot(slot_index)
            if spell:
                self.game_state.selected_spell = spell
                self.game_state.add_debug_message(f"Selected spell: {spell} (Slot {slot_index + 1})")
            else:
                self.game_state.add_debug_message(f"No spell in slot {slot_index + 1}")
        return True

    def _get_active_oracle(self) -> Optional[Oracle]:
        """Helper to retrieve the active Oracle object from game_state based on its ID/name."""
        if self.game_state.active_oracle_entity_id is None:
            return None
        # Assuming active_oracle_entity_id stores the Oracle's name for now.
        # If map entities list is used, this might search self.game_state.map or self.game_state.characters
        # For simplicity, let's assume Oracles are in self.game_state.characters list
        # This part might need adjustment based on how Oracles are stored and identified.
        # For now, let's assume we need to find it on the map at its known interaction point,
        # or if Oracles are stored in a general character list.
        # Let's refine this if Oracles are spawned dynamically and not always in a fixed list.
        # A simpler way if the entity object itself can be stored, but ID is safer for serialization.
        
        # Search in self.game_state.characters (NPC list which includes Oracles)
        for char_list in [self.game_state.characters]: # Add other lists if Oracles can be elsewhere
            for entity in char_list:
                if isinstance(entity, Oracle) and entity.name == self.game_state.active_oracle_entity_id:
                    return entity
        
        # Fallback: if not in characters list, check entities on map tiles if needed,
        # but this is less efficient. The talk initiation should ideally give us enough info.
        # For now, if not found in characters list, assume an issue.
        self.game_state.add_debug_message(f"Error: Active Oracle '{self.game_state.active_oracle_entity_id}' not found.")
        return None

    def _handle_offering(self, oracle: Oracle) -> bool:
        """Checks if player can afford the offering and deducts it if so."""
        can_afford = True
        for resource, amount_needed in self.game_state.oracle_offering_cost.items():
            if self.game_state.inventory.resources.get(resource, 0) < amount_needed:
                can_afford = False
                break
        
        if can_afford:
            for resource, amount_needed in self.game_state.oracle_offering_cost.items():
                self.game_state.inventory.remove_resource(resource, amount_needed)
            self.game_state.add_debug_message(f"Made offering to {oracle.name}.")
            return True
        else:
            offering_cost_str = ", ".join([f"{qty} {res.replace('_', ' ')}" for res, qty in self.game_state.oracle_offering_cost.items()])
            self.game_state.oracle_current_dialogue = [
                "You lack the required offering.",
                f"(Needs: {offering_cost_str})"
            ] # This will be displayed by renderer
            self.game_state.add_debug_message(f"Cannot afford offering for {oracle.name}.")
            return False

    # Removed find_adjacent_walkable and find_adjacent_tile
