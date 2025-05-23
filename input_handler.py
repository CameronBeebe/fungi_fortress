import curses
import random
from typing import TYPE_CHECKING, Optional, Union

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
            current_oracle = self._get_active_oracle()
            oracle_name = current_oracle.name if current_oracle else "The Oracle"

            # General close keys, checked first
            if key == ord('q'): # 'q' always closes
                self.game_state.show_oracle_dialog = False
                self.game_state.paused = False
                # Reset states only if not in a state that should persist (e.g. AWAITING_LLM_RESPONSE)
                if self.game_state.oracle_interaction_state != "AWAITING_LLM_RESPONSE":
                    self.game_state.oracle_interaction_state = "IDLE"
                    self.game_state.oracle_current_dialogue = []
                    self.game_state.oracle_prompt_buffer = ""
                    self.game_state.active_oracle_entity_id = None
                self.game_state.add_debug_message(f"Oracle dialog closed via 'q'.")
                return True

            if self.game_state.oracle_interaction_state == "AWAITING_OFFERING":
                if key == ord('y'):
                    if current_oracle and self._handle_offering(current_oracle):
                        # Offering successful, now check API key
                        has_real_api_key = False # Default to false
                        if self.game_state.oracle_config:
                            has_real_api_key = self.game_state.oracle_config.is_real_api_key_present

                        if has_real_api_key:
                            self.game_state.oracle_interaction_state = "AWAITING_PROMPT"
                            self.game_state.oracle_current_dialogue = ["The Oracle acknowledges your offering.", "It awaits your query..."]
                            self.game_state.oracle_prompt_buffer = ""
                        else:
                            # API key not valid/placeholder, or LLM disabled - show canned response
                            self.game_state.oracle_interaction_state = "SHOWING_CANNED_RESPONSE"
                            canned_dialogue = get_canned_response(current_oracle, "greeting_offering_no_llm")
                            if not canned_dialogue: # Fallback
                                canned_dialogue = ["The Oracle acknowledges your offering.", "Its connection to the aether is weak today, but it offers these words:"] + get_canned_response(current_oracle, "generic_fallback")
                            self.game_state.oracle_current_dialogue = canned_dialogue
                    else: # _handle_offering returned False (insufficient resources)
                        if current_oracle:
                             # Dialogue for insufficient offering is now set by _handle_offering itself
                             pass # Ensure _handle_offering sets the dialog for insufficient resources
                        # Stays in AWAITING_OFFERING or _handle_offering might change state
                elif key == ord('n'):
                    self.game_state.add_debug_message("Declined Oracle's offering.")
                    if current_oracle:
                        self.game_state.oracle_current_dialogue = get_canned_response(current_oracle, "no_offering_made")
                    self.game_state.oracle_interaction_state = "SHOWING_CANNED_RESPONSE"
                return True 
            
            elif self.game_state.oracle_interaction_state == "SHOWING_CANNED_RESPONSE":
                if key in [curses.KEY_ENTER, 10, 13, ord(' '), ord('t')]: # Exit with Enter, Space, or 't'
                    self.game_state.show_oracle_dialog = False
                    self.game_state.paused = False
                    self.game_state.oracle_interaction_state = "IDLE"
                    self.game_state.oracle_current_dialogue = []
                    self.game_state.oracle_prompt_buffer = ""
                    self.game_state.active_oracle_entity_id = None
                    return True
                return True 

            elif self.game_state.oracle_interaction_state == "AWAITING_PROMPT":
                if key == curses.KEY_ENTER or key == 10 or key == 13: # Enter pressed
                    if self.game_state.oracle_prompt_buffer.strip():
                        query_text = self.game_state.oracle_prompt_buffer
                        self.game_state.add_debug_message(f"Player query: {query_text}")
                        
                        # Add player query to dialogue history immediately for display
                        self.game_state.oracle_current_dialogue.append(f"> {query_text}")

                        # Create and add ORACLE_QUERY event
                        event_details = {
                            "query_text": query_text,
                            "oracle_name": oracle_name,
                             # Add any other relevant details for the LLM context if needed directly from input handler
                        }
                        self.game_state.add_event("ORACLE_QUERY", event_details)
                        
                        self.game_state.oracle_interaction_state = "AWAITING_LLM_RESPONSE"
                        # Dialogue like "Oracle is contemplating..." will be added by GameLogic's action handler for set_oracle_state
                        self.game_state.oracle_prompt_buffer = "" # Clear buffer after sending
                    else:
                        # Empty prompt submitted, perhaps show a message or just do nothing
                        self.game_state.oracle_current_dialogue.append("(You remain silent before the Oracle.)")
                        # Optionally, could revert to AWAITING_PROMPT or close dialog
                elif key == curses.KEY_BACKSPACE or key == 127 or key == 8: # Handle backspace
                    self.game_state.oracle_prompt_buffer = self.game_state.oracle_prompt_buffer[:-1]
                elif 32 <= key <= 126: # Printable ASCII characters
                    # Limit prompt length if necessary
                    if len(self.game_state.oracle_prompt_buffer) < 200: # Example limit
                        self.game_state.oracle_prompt_buffer += chr(key)
                # Other keys (arrows, etc.) are ignored in this state
                return True
            
            elif self.game_state.oracle_interaction_state == "AWAITING_LLM_RESPONSE":
                # Input is generally ignored while waiting for LLM, except perhaps a cancel key (handled by 'q')
                self.game_state.add_debug_message("Input ignored: Awaiting LLM response.")
                return True

            # Fallback for any other Oracle states, absorb key
            return True

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
            # Find adjacent character to talk to
            talk_target = None
            adj_pos = [
                (self.game_state.cursor_x, self.game_state.cursor_y - 1), (self.game_state.cursor_x, self.game_state.cursor_y + 1),
                (self.game_state.cursor_x - 1, self.game_state.cursor_y), (self.game_state.cursor_x + 1, self.game_state.cursor_y)
            ]
            
            # Get the primary dwarf, ensuring dwarves list is not empty
            player_dwarf = self.game_state.dwarves[0] if self.game_state.dwarves else None
            
            # Check if cursor is on an NPC/Oracle
            target_entity_on_cursor: Optional[Union[NPC, Oracle]] = None
            for char in self.game_state.characters:
                if char.x == self.game_state.cursor_x and char.y == self.game_state.cursor_y and isinstance(char, (NPC, Oracle)):
                    target_entity_on_cursor = char
                    break
            
            if target_entity_on_cursor and isinstance(target_entity_on_cursor, (NPC, Oracle)):
                # Check if player dwarf is adjacent to the target on cursor
                is_adjacent = False
                if player_dwarf:
                    for pos_x, pos_y in adj_pos:
                        if player_dwarf.x == pos_x and player_dwarf.y == pos_y and \
                           self.game_state.cursor_x == target_entity_on_cursor.x and \
                           self.game_state.cursor_y == target_entity_on_cursor.y:
                             is_adjacent = True
                             break
                    # A simpler adjacency check if cursor is on the target and dwarf is next to cursor target
                    if not is_adjacent and player_dwarf and \
                       abs(player_dwarf.x - target_entity_on_cursor.x) <=1 and \
                       abs(player_dwarf.y - target_entity_on_cursor.y) <=1 and \
                       (player_dwarf.x != target_entity_on_cursor.x or player_dwarf.y != target_entity_on_cursor.y): # Is adjacent
                           is_adjacent = True
                
                if is_adjacent:
                    talk_target = target_entity_on_cursor
                    if isinstance(talk_target, Oracle):
                        self.game_state.active_oracle_entity_id = talk_target.name
                        self.game_state.show_oracle_dialog = True
                        self.game_state.paused = True
                        # ALWAYS go to AWAITING_OFFERING first
                        self.game_state.oracle_interaction_state = "AWAITING_OFFERING"
                        offering_cost_str = ", ".join([f"{qty} {res.replace('_', ' ')}" for res, qty in self.game_state.oracle_offering_cost.items()])
                        self.game_state.oracle_current_dialogue = [
                            f"{talk_target.name} desires an offering to share deeper insights:",
                            f"({offering_cost_str}).",
                            "Will you make this offering? (Y/N)"
                        ]
                        self.game_state.add_debug_message(f"Initiated Oracle dialog with {talk_target.name}. Awaiting offering.")
                    elif isinstance(talk_target, NPC): # Handle other NPCs
                        # Simple interaction for other NPCs for now
                        self.game_state.add_debug_message(f"You talk to {talk_target.name}. They grunt noncommittally.")
                    return True # Input handled

            # If not adjacent or no direct target, try to assign a 'talk' task
            if player_dwarf and target_entity_on_cursor and isinstance(target_entity_on_cursor, (NPC, Oracle)):
                # Use a_star to find a path to an adjacent tile
                path_to_target = a_star(self.game_state.map, 
                                        (player_dwarf.x, player_dwarf.y), 
                                        (target_entity_on_cursor.x, target_entity_on_cursor.y), 
                                        adjacent=True)
                
                task_assigned_or_msg_sent = False
                if path_to_target is not None:
                    if len(path_to_target) > 0:
                        # Path found, target is the last step in path (adjacent to actual target)
                        task_x, task_y = path_to_target[-1]
                        talk_task = Task(x=task_x, y=task_y, type='talk',
                                         resource_x=target_entity_on_cursor.x,
                                         resource_y=target_entity_on_cursor.y)
                        if self.game_state.task_manager.add_task(talk_task):
                            dwarf_display_name = f"Dwarf {player_dwarf.id}" # Use ID for now
                            self.game_state.add_debug_message(f"{dwarf_display_name} will go talk to {target_entity_on_cursor.name}.")
                            # Ensure no dialog is showing while pathing and clear Oracle state
                            self.game_state.show_oracle_dialog = False
                            self.game_state.oracle_interaction_state = "IDLE"
                            self.game_state.active_oracle_entity_id = None
                            self.game_state.oracle_current_dialogue = []
                        else:
                            self.game_state.add_debug_message("Task list is full. Cannot assign talk task.")
                        task_assigned_or_msg_sent = True
                    elif len(path_to_target) == 0: # Already adjacent (should have been caught by direct adjacency handling)
                         # This case should ideally not be reached if direct adjacency handling is robust.
                         # However, as a fallback, consider if a task should still be made or error.
                         # For now, assume direct adjacency was missed and log it.
                         self.game_state.add_debug_message(f"Path to talk to {target_entity_on_cursor.name} was empty, but not handled by direct adjacency.")
                         # Optionally, could attempt direct dialog opening here if it wasn't, but that might indicate a deeper logic flow issue.
                         task_assigned_or_msg_sent = True # Treat as handled to avoid 'cannot find path' message
                
                if not task_assigned_or_msg_sent: # Path was None or some other issue
                    self.game_state.add_debug_message(f"Cannot find a path to talk to {target_entity_on_cursor.name}.")
                return True
            else: # No specific NPC/Oracle at cursor, or player_dwarf issue
                 self.game_state.add_debug_message("Nothing to talk to there, or no one to send.")
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
        if self.game_state.active_oracle_entity_id:
            # Correctly search for the oracle in game_state.characters
            for char in self.game_state.characters:
                if isinstance(char, Oracle) and char.name == self.game_state.active_oracle_entity_id:
                    return char
        return None

    def _handle_offering(self, oracle: Oracle) -> bool:
        """Checks if player has resources and deducts them if 'Y' is pressed.
        
        Returns:
            bool: True if offering was made successfully, False otherwise (e.g. insufficient items).
        """
        # Use game_state.oracle_offering_cost for universal offering
        required_resources = self.game_state.oracle_offering_cost 
        
        can_afford = True
        for resource, amount_needed in required_resources.items():
            # Correctly access resource count from inventory
            if self.game_state.inventory.resources.get(resource, 0) < amount_needed:
                can_afford = False
                break
        
        if can_afford:
            for resource, amount_to_deduct in required_resources.items():
                self.game_state.inventory.remove_resource(resource, amount_to_deduct)
            self.game_state.add_debug_message(f"Offering made to {oracle.name}: {required_resources}")
            # InteractionEventDetails.log_interaction("player", "offering_made", oracle.name, cost=required_resources)
            return True
        else:
            self.game_state.add_debug_message(f"Insufficient resources for offering to {oracle.name}.")
            # Set dialog for insufficient offering here
            self.game_state.oracle_current_dialogue = get_canned_response(oracle, "insufficient_offering")
            if not self.game_state.oracle_current_dialogue: # Fallback
                self.game_state.oracle_current_dialogue = ["You lack the required items for the offering."]
            self.game_state.oracle_interaction_state = "SHOWING_CANNED_RESPONSE" # Move to show this message
            # InteractionEventDetails.log_interaction("player", "offering_failed_insufficient", oracle.name)
            return False

    # Removed find_adjacent_walkable and find_adjacent_tile
