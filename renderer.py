import curses
import random
import math
from typing import TYPE_CHECKING

# Update constants import to relative
from .constants import (
    MAP_WIDTH, MAP_HEIGHT, UI_WIDTH, LOG_HEIGHT, # Used by Renderer.__init__ and render
    # SIDEBAR_WIDTH, SIDEBAR_X, # Likely unused
    # MIN_SCREEN_WIDTH, MIN_SCREEN_HEIGHT, SIDEBAR_SECTIONS # Likely unused
)

# Use relative imports for sibling modules
from .utils import wrap_text # Seems unused, but keep if description wrapping added back
from .tiles import Tile, ENTITY_REGISTRY
# Removed: from items import special_items
from .entities import GameEntity, Structure, Sublevel, ResourceNode # For legend/hints

if TYPE_CHECKING:
    from .game_state import GameState # For type hints

COLOR_MAP = {
    0: curses.COLOR_BLACK,
    1: curses.COLOR_GREEN,      # Grass, Trees
    2: curses.COLOR_YELLOW,     # Highlight
    3: curses.COLOR_BLUE,       # Water
    4: curses.COLOR_RED,        # Enemy / Danger
    5: curses.COLOR_CYAN,       # Water alt / Ice?
    6: curses.COLOR_MAGENTA,    # Magic / Grotto
    7: curses.COLOR_WHITE,      # Default text
    8: curses.COLOR_BLACK,      # UI Background
    9: curses.COLOR_WHITE,      # Stone Floor (Bright White)
    10: curses.COLOR_YELLOW,    # Stone Wall (Bright Yellow)
    11: curses.COLOR_MAGENTA,   # Mycelium (Bright Magenta)
    12: curses.COLOR_GREEN,     # Animals (Bright Green)
    13: curses.COLOR_MAGENTA,   # Fungi (Pink/Magenta/Purple)
    14: curses.COLOR_RED,       # NPCs (Bright Red)
    15: curses.COLOR_YELLOW,    # Dwarves (Bright Yellow)
    16: curses.COLOR_MAGENTA,   # Magic Fungi / Sporeforge (Bright Magenta)
    17: curses.COLOR_YELLOW,    # Mycelial Nexus (Bright Yellow)
}

def init_colors():
    """Initializes curses color pairs used throughout the game.

    Defines standard color pairs (1-17) based on `COLOR_MAP`,
    special background pairs (100-104) for cursor, designation, and effects,
    and specific foreground pairs (200-203) for fungi variations.
    Assumes curses has been initialized and color is supported.
    """
    curses.start_color()
    curses.use_default_colors()
    for i in range(1, 18): # 1 through 17
        curses.init_pair(i, COLOR_MAP.get(i, curses.COLOR_WHITE), curses.COLOR_BLACK) # Use black background
    # Special pair for cursor
    curses.init_pair(100, curses.COLOR_BLACK, curses.COLOR_WHITE) # Black text on white bg
    # Special pair for designation
    curses.init_pair(101, curses.COLOR_YELLOW, curses.COLOR_RED) # YELLOW text on RED bg
    # Special pair for highlights/flash/pulse
    curses.init_pair(102, curses.COLOR_BLACK, curses.COLOR_CYAN)   # Black text on cyan bg (Flash)
    curses.init_pair(103, curses.COLOR_BLACK, curses.COLOR_GREEN)  # Black text on green bg (Highlight)
    curses.init_pair(104, curses.COLOR_BLACK, curses.COLOR_MAGENTA) # Black text on magenta bg (Pulse)
    
    # Special fungi color pairs (200-203)
    curses.init_pair(200, curses.COLOR_MAGENTA, curses.COLOR_BLACK) # Pink fungi
    curses.init_pair(201, curses.COLOR_RED, curses.COLOR_BLACK)     # Maroon fungi (dark red)
    curses.init_pair(202, curses.COLOR_RED, curses.COLOR_BLACK)     # Red fungi
    curses.init_pair(203, curses.COLOR_MAGENTA, curses.COLOR_BLACK) # Magenta fungi

class Renderer:
    """Handles rendering the game state to the terminal using curses.

    Responsible for drawing the map, UI elements (stats, inventory, shop, legend),
    and the debug log. Manages curses windows, colors, and terminal size checks.

    Attributes:
        screen: The main curses window object.
        game_state (GameState): Reference to the current game state.
        is_size_ok (bool): Flag indicating if the terminal size is adequate.
        map_win: The curses window for the main game map.
        ui_win: The curses window for the UI sidebar.
        log_win: The curses window for the debug message log.
        max_y (int): Maximum height of the terminal.
        max_x (int): Maximum width of the terminal.
    """
    def __init__(self, screen, game_state: 'GameState'):
        """Initializes the Renderer.

        Sets up curses mode (no cursor, non-blocking input), initializes colors,
        checks terminal size, and creates the map, UI, and log windows if the
        size is sufficient.

        Args:
            screen: The main curses window object provided by curses.wrapper.
            game_state (GameState): The game state object to render.
        """
        self.screen = screen
        self.game_state = game_state
        self.is_size_ok = False # Flag to indicate if terminal size is sufficient
        self.map_win = None
        self.ui_win = None
        self.log_win = None
        
        curses.curs_set(0) 
        self.screen.nodelay(True)
        init_colors()
        
        # --- Check Terminal Size --- 
        self.max_y, self.max_x = self.screen.getmaxyx()
        required_h = MAP_HEIGHT + LOG_HEIGHT
        required_w = MAP_WIDTH + UI_WIDTH
        
        if self.max_y < required_h or self.max_x < required_w:
            self.is_size_ok = False
            # Don't create windows if size is insufficient
        else:
            self.is_size_ok = True
            # Create windows using FIXED sizes from constants
            try:
                # Map: Top-left, fixed size
                self.map_win = curses.newwin(MAP_HEIGHT, MAP_WIDTH, 0, 0)
                # UI: Top-right, fixed width, full terminal height (up to max_y)
                self.ui_win = curses.newwin(self.max_y, UI_WIDTH, 0, MAP_WIDTH)
                # Log: Bottom-left, fixed height, fixed width
                self.log_win = curses.newwin(LOG_HEIGHT, MAP_WIDTH, MAP_HEIGHT, 0)

                # Optional optimizations
                # self.screen.leaveok(True)
                # self.map_win.scrollok(True)
                # ... etc
            except curses.error as e:
                 # Handle potential error during window creation even if size check passed
                 self.is_size_ok = False
                 # Store error? For now, the render loop will catch is_size_ok being False.
                 pass 

    def _display_resize_message(self):
        """Displays a message asking the user to resize the terminal.

        This is shown when the terminal dimensions are smaller than the required
        size calculated from game constants (MAP_HEIGHT, MAP_WIDTH, LOG_HEIGHT, UI_WIDTH).
        Attempts to center the message on the screen.
        """
        required_h = MAP_HEIGHT + LOG_HEIGHT
        required_w = MAP_WIDTH + UI_WIDTH
        try:
            self.screen.erase()
            msg_lines = [
                f"Terminal Too Small!",
                f"Required: {required_w}w x {required_h}h",
                f"Current:  {self.max_x}w x {self.max_y}h",
                f"Please resize your terminal and restart.",
                f"Press q to quit."
            ]
            start_y = (self.max_y - len(msg_lines)) // 2
            for i, line in enumerate(msg_lines):
                 line_x = (self.max_x - len(line)) // 2
                 self.screen.addstr(start_y + i, max(0, line_x), line)
            self.screen.refresh()
        except curses.error: 
            # Ignore errors if we can't even draw the message
            pass

    def render(self):
        """Renders the main game view (map, UI, log) to the screen.

        Checks if the terminal size is adequate. If not, displays a resize message.
        Otherwise, clears the individual windows and redraws:
        - Map tiles, applying colors and effects (flicker, pulse, highlight, designation).
        - Entities (dwarves, animals, NPCs) on the map.
        - The player cursor.
        - The UI sidebar with game stats, inventory, mission info, spells, and hotkeys.
        - The debug log.
        Finally, refreshes the windows to display the changes.
        """
        # Check size flag first
        if not self.is_size_ok or not all([self.map_win, self.ui_win, self.log_win]):
            self._display_resize_message()
            # We might want main.py to handle exiting in this case
            # For now, just display message and prevent further rendering this frame
            return 
            
        # Erase only the specific windows before drawing
        self.map_win.erase()
        self.ui_win.erase()
        self.log_win.erase()

        # --- Render Map --- 
        # Use FIXED map dimensions for drawing bounds, not getmaxyx()
        map_h, map_w = MAP_HEIGHT, MAP_WIDTH 
        # Only draw up to the actual map height/width
        for y in range(map_h):
            if y >= len(self.game_state.map): continue 
            for x in range(map_w):
                if x >= len(self.game_state.map[y]): continue
                
                tile = self.game_state.map[y][x]
                entity = tile.entity
                char = entity.char
                color_pair_index = entity.color
                attr = curses.A_NORMAL

                # --- Determine Final Color and Attributes with Priority ---
                final_color_pair_index = entity.color # Start with base color
                final_attr = curses.A_NORMAL

                # Special fungi color rendering (applies attributes for more variety)
                if entity.char == 'f' and 200 <= tile.color <= 203:
                    final_color_pair_index = tile.color
                    # Use coordinates to determine attribute - consistent for each fungi
                    if (x + y) % 2 == 0:  # Based on position for consistency
                        final_attr = curses.A_BOLD
                
                # Magic fungi ('F') flickering based on mycelial network distance
                elif entity.char == 'F' and entity.is_mycelial:
                    # Use network distance from nexus or fallback to spatial distance if network not built
                    distance = self._get_mycelial_distance((x, y))
                    
                    # Define flickering patterns based on distance
                    flicker_colors = [16, 6, 14]  # Magenta, Bright-magenta, Bright-red
                    
                    # Phase offset based on distance (organic propagation feel)
                    phase_offset = distance % 10  # Cycle repeats every 10 nodes away
                    
                    # Different flickering speeds based on distance from nexus
                    if distance < 5:
                        flicker_speed = 8  # Faster near nexus
                    elif distance < 10:
                        flicker_speed = 12
                    else:
                        flicker_speed = 16  # Slower far from nexus
                    
                    # Calculate flicker index with phase offset
                    flicker_index = ((self.game_state.tick + phase_offset) // flicker_speed) % len(flicker_colors)
                    
                    # Apply flicker color
                    final_color_pair_index = flicker_colors[flicker_index]
                    
                    # Random bold attribute based on position and time for more visual variety
                    if (x + y + self.game_state.tick // 20) % 3 == 0:
                        final_attr = curses.A_BOLD

                # 1. Check for Generic Effects (Flash/Pulse/Highlight)
                if tile.flash_ticks > 0 and (self.game_state.tick // (tile.flash_ticks // 2 + 1)) % 2 == 0:
                    final_color_pair_index = 102 # Flash background
                elif tile.pulse_ticks > 0:
                    # Enhanced pulsing effect for mycelial visualization
                    # Create a smoother pulse effect with varying colors
                    pulse_phase = (self.game_state.tick % 30) / 30.0  # 0.0 to 1.0
                    
                    # Check if this is part of mycelial network (uses specific colors)
                    is_mycelial = (tile._color_override in [5, 13, 16, 201, 206])
                    
                    if is_mycelial:
                        # For mycelial network, use foreground colors only with pulsing effects
                        final_color_pair_index = tile._color_override
                        
                        # Add visual interest with bold/normal alternation based on game tick
                        if pulse_phase < 0.5:
                            final_attr = curses.A_BOLD
                        else:
                            final_attr = curses.A_NORMAL
                    else:
                        # Standard pulse behavior for non-mycelial entities
                        # (use pulse foreground color instead of background)
                        final_color_pair_index = 13  # Magenta foreground 
                elif tile.highlight_ticks > 0:
                    # Use tile's color_override if set, otherwise use default highlight color
                    if tile._color_override is not None:
                        # For mycelial network path visualization with propagation effect
                        is_mycelial_path = (tile._color_override in [5, 13, 16, 201, 206])
                        
                        if is_mycelial_path:
                            # Always use foreground colors, never background colors for the network
                            final_color_pair_index = tile._color_override
                            
                            # Create wave-like propagation effect based on position and time
                            tick_offset = (self.game_state.tick + tile.x + tile.y) % 20
                            
                            # Add bold attribute for part of the cycle for visual "pulse"
                            if tick_offset < 10:
                                final_attr = curses.A_BOLD
                            else:
                                final_attr = curses.A_NORMAL
                        else:
                            # Non-mycelial highlight - use assigned color
                            final_color_pair_index = tile._color_override
                    else:
                        final_color_pair_index = 15 # Fallback to bright white if no override

                # 2. Check for Flicker (Overrides Generic Effects for these entities)
                if entity.is_mycelial:
                    flicker_colors = [14, 6] # Bright Red, Magenta
                    flicker_speed = 15
                    flicker_index = (self.game_state.tick // flicker_speed) % len(flicker_colors)
                    final_color_pair_index = flicker_colors[flicker_index] # Apply flicker color
                    if final_color_pair_index == 14: # Bright Red
                        final_attr = curses.A_BOLD # Set bold attr
                    else:
                        final_attr = curses.A_NORMAL # Ensure non-bold otherwise

                # 3. Check for Designation (Overrides Flicker and Generic Effects)
                is_designated = tile.designated or \
                                any(d.task is not None and d.task.resource_x == x and d.task.resource_y == y for d in self.game_state.dwarves) or \
                                any(any(t.resource_x == x and t.resource_y == y for t in d.task_queue) for d in self.game_state.dwarves)
                if is_designated:
                    final_color_pair_index = 101 # Yellow text on Red background
                    final_attr = curses.A_NORMAL # Ensure designation isn't bold

                # 4. Check for Cursor (Overrides Everything)
                is_cursor_here = x == self.game_state.cursor_x and y == self.game_state.cursor_y
                if is_cursor_here:
                    final_color_pair_index = 100 # Cursor background (Black on White)
                    final_attr = curses.A_NORMAL # Ensure cursor isn't bold
                
                # --- Get final pair and draw ---
                color_pair = curses.color_pair(final_color_pair_index)

                # Draw the character
                try:
                     self.map_win.addch(y, x, char, color_pair | final_attr)
                except curses.error:
                     pass # Ignore errors trying to draw outside window bounds

        # --- Render Entities (Dwarves, Animals, NPCs) on Map --- 
        dwarf_color = curses.color_pair(15)
        animal_color = curses.color_pair(12)
        npc_color = curses.color_pair(14)
        for dwarf in self.game_state.dwarves:
             if 0 <= dwarf.y < map_h and 0 <= dwarf.x < map_w: # Check bounds
                # DEBUG: Log dwarf position before drawing
                # self.game_state.add_debug_message(f"Renderer drawing D{dwarf.id} at ({dwarf.x},{dwarf.y})") 
                try:
                     self.map_win.addch(dwarf.y, dwarf.x, 'D', dwarf_color)
                except curses.error: pass
        for animal in self.game_state.animals:
             if animal.alive and 0 <= animal.y < map_h and 0 <= animal.x < map_w:
                try:
                    self.map_win.addch(animal.y, animal.x, 'A', animal_color)
                except curses.error: pass
        for npc in self.game_state.characters:
             if npc.alive and 0 <= npc.y < map_h and 0 <= npc.x < map_w:
                try:
                     # Use first letter of NPC name? Or a generic 'C'?
                     npc_char = npc.name[0].upper() if npc.name else 'C'
                     self.map_win.addch(npc.y, npc.x, npc_char, npc_color)
                except curses.error: pass

        # --- Draw Cursor (+) --- 
        cursor_y, cursor_x = self.game_state.cursor_y, self.game_state.cursor_x
        if 0 <= cursor_y < MAP_HEIGHT and 0 <= cursor_x < MAP_WIDTH: # Check bounds
            spore_exposure = self.game_state.player.spore_exposure
            alert_threshold = self.game_state.spore_exposure_threshold # Use threshold from game_state
            cursor_color_pair_index = 10 # Default Yellow (COLOR_YELLOW)
            if spore_exposure >= alert_threshold:
                cursor_color_pair_index = 6 # Magenta (Magic/Grotto)
            if spore_exposure >= alert_threshold * 2:
                cursor_color_pair_index = 14 # Red (COLOR_RED)
            
            cursor_color_pair = curses.color_pair(cursor_color_pair_index)
            try:
                self.map_win.addch(cursor_y, cursor_x, '+', cursor_color_pair)
            except curses.error:
                 pass # Ignore errors drawing cursor (e.g., exactly at edge)

        # --- Render UI --- 
        # UI drawing should use the fixed UI_WIDTH 
        # It can use its actual height (self.max_y) from getmaxyx()
        ui_h, ui_w = self.ui_win.getmaxyx() # Get actual window size for bounds
        current_row = 0
        def add_ui_line(text, *args):
            nonlocal current_row
            if current_row < ui_h:
                try:
                    # Use ui_w (actual window width) for ljust
                    self.ui_win.addstr(current_row, 0, text.ljust(ui_w-1), *args) 
                    current_row += 1
                except curses.error: current_row +=1
        # Restore UI drawing logic
        add_ui_line(f"Tick: {self.game_state.tick}")
        add_ui_line(f"Depth: {self.game_state.depth}")
        add_ui_line(f"Spore Exposure: {self.game_state.player.spore_exposure}") # Add spore exposure display
        add_ui_line(f"Location: {self.game_state.player.location}") # Use property
        add_ui_line(f"Cursor: ({self.game_state.cursor_x},{self.game_state.cursor_y})")
        cursor_tile = self.game_state.get_tile(self.game_state.cursor_x, self.game_state.cursor_y)
        if cursor_tile:
            entity_at_cursor = cursor_tile.entity
            add_ui_line(f"Tile: {entity_at_cursor.name}")
            # Description wrapping (requires utils.wrap_text)
            if hasattr(entity_at_cursor, 'description') and entity_at_cursor.description and current_row < ui_h - 2:
                desc_lines = wrap_text(entity_at_cursor.description, ui_w - 3)
                for line in desc_lines:
                    add_ui_line(f"  {line}")
        else:
            add_ui_line("Tile: Out of Bounds")
        current_row += 1 
        if self.game_state.dwarves:
            dwarf = self.game_state.dwarves[0]
            add_ui_line(f"Dwarf: {dwarf.state}")
            if dwarf.task:
                add_ui_line(f" Task: {dwarf.task.type} @ ({dwarf.target_x},{dwarf.target_y})")
                if dwarf.task.type == 'build': add_ui_line(f"   Building: {dwarf.task.building}")
                if dwarf.task_ticks > 0: add_ui_line(f"   Ticks: {dwarf.task_ticks}")
            if dwarf.task_queue: add_ui_line(f" Queue: {len(dwarf.task_queue)}")
        else: add_ui_line("No Dwarves")
        current_row += 1
        add_ui_line("Inventory:")
        res_str = ", ".join(f"{k[:3]}:{v}" for k, v in self.game_state.inventory.resources.items() if v > 0)
        add_ui_line(f" {res_str}")
        item_str = ", ".join(f"{k}:{v}" for k, v in self.game_state.inventory.special_items.items() if v > 0)
        if item_str: add_ui_line(f" {item_str}")
        current_row += 1
        add_ui_line("Mission:")
        if self.game_state.mission:
             obj_str = ", ".join(self.game_state.mission.get("objectives",["None"]))
             add_ui_line(f" Obj: {obj_str[:ui_w-6]}")
             comp_str = "Complete" if self.game_state.mission_complete else "In Progress"
             add_ui_line(f" Status: {comp_str}")
        else: add_ui_line(" No active mission")
        current_row += 1
        add_ui_line("Spells:")
        if self.game_state.player.spells:
            for slot_index in range(len(self.game_state.player.spell_slots)):
                spell = self.game_state.player.get_spell_in_slot(slot_index)
                if spell:
                    prefix = "*>" if spell == self.game_state.selected_spell else f"{slot_index + 1}>"
                    if spell == self.game_state.selected_spell:
                        # Use bright magenta (16) with bold for selected spell
                        add_ui_line(f" {prefix} {spell}", curses.color_pair(16) | curses.A_BOLD)
                    else:
                        add_ui_line(f" {prefix} {spell}")
                else:
                    add_ui_line(f" {slot_index + 1}> [Empty]", curses.A_DIM)
        else: 
            add_ui_line(" None")

        # --- Hotkeys Section ---
        current_row += 1 # Add a space before hotkeys
        add_ui_line("Hotkeys:")
        add_ui_line(" 1-5: select spell slot")
        add_ui_line(" s: cycle spells")
        add_ui_line(" c: cast spell")
        add_ui_line(" m: move/mine/chop")
        add_ui_line(" f: fish/fight")
        add_ui_line(" i: inventory")
        add_ui_line(" l: legend")
        add_ui_line(" t: talk") 
        add_ui_line(" e: enter/interact")
        add_ui_line(" b: build")
        add_ui_line(" d: descend/shop")
        add_ui_line(" p: pause")
        add_ui_line(" q: quit")
        # Add more hotkeys as needed, ensuring they fit UI_WIDTH

        # --- Render Log --- 
        # Log drawing should use fixed LOG_HEIGHT and MAP_WIDTH
        log_h, log_w = LOG_HEIGHT, MAP_WIDTH # Use constants
        start_line = max(0, len(self.game_state.debug_log) - log_h)
        for i, msg in enumerate(self.game_state.debug_log[start_line:]):
            if i < log_h:
                 try:
                    # Use log_w (MAP_WIDTH) for ljust
                    self.log_win.addstr(i, 0, msg.ljust(log_w-1))
                 except curses.error: pass 

        # --- Refresh Windows --- 
        self.map_win.refresh()
        # Restore refreshing UI and Log windows
        self.ui_win.refresh()
        self.log_win.refresh()

    def clear_screen(self):
        """Force clears the entire terminal screen and all managed windows.

        Useful for ensuring a clean state after closing overlays or major
        state changes.
        """
        # Clear the entire terminal screen first
        self.screen.clear()
        # Clear all sub-windows
        self.map_win.clear()
        self.ui_win.clear()
        self.log_win.clear()
        # Refresh the main screen first
        self.screen.refresh()
        # Then refresh all windows
        self.map_win.refresh()
        self.ui_win.refresh()
        self.log_win.refresh()
        # Force an immediate screen update
        curses.doupdate()

    def show_inventory_screen(self):
        """Displays the inventory overlay window.

        Creates a new window centered on the screen, draws a border, title,
        and lists the player's current resources and special items.
        Includes a message on how to close it.
        Handles cleanup and redraw if the inventory state changes.
        """
        # Simple inventory display overlay (could be a new window)
        inv_h, inv_w = 15, 40
        inv_y = (self.max_y - inv_h) // 2
        inv_x = (self.max_x - inv_w) // 2
        inv_win = curses.newwin(inv_h, inv_w, inv_y, inv_x)
        inv_win.erase()
        inv_win.border()
        inv_win.addstr(1, (inv_w - 9) // 2, "Inventory")

        row = 3
        inv_win.addstr(row, 2, "Resources:") ; row += 1
        for res, qty in self.game_state.inventory.resources.items():
            if row < inv_h - 2: inv_win.addstr(row, 4, f"{res}: {qty}") ; row += 1
        row += 1
        inv_win.addstr(row, 2, "Special Items:") ; row += 1
        for item, qty in self.game_state.inventory.special_items.items():
             if row < inv_h - 2: inv_win.addstr(row, 4, f"{item}: {qty}") ; row += 1

        inv_win.addstr(inv_h - 2, 2, "Press 'i' or 'q' to close")
        inv_win.refresh()
        if not self.game_state.show_inventory:
            # Clean up the overlay window
            inv_win.erase()
            inv_win.refresh()
            del inv_win
            
            # Force a complete redraw
            self.screen.clear()
            self.screen.refresh()
            self.render()
            curses.doupdate()

    def show_shop_screen(self):
        """Displays the shop/descent preparation overlay window.

        Creates a new window centered on the screen. Displays carry weight,
        available resources, currently selected resources to carry, and keybinds
        for adjusting carry amounts, resetting, showing sell value, confirming,
        or cancelling the descent.
        Handles cleanup and redraw if the shop state changes.
        """
        shop_h, shop_w = 20, 60
        shop_y = (self.max_y - shop_h) // 2
        shop_x = (self.max_x - shop_w) // 2
        shop_win = curses.newwin(shop_h, shop_w, shop_y, shop_x)
        shop_win.erase()
        shop_win.border()
        shop_win.addstr(1, (shop_w - 23) // 2, "Prepare for Descent")

        row = 3
        max_weight = self.game_state.player.max_carry_weight
        current_weight = sum(qty for res, qty in self.game_state.shop_carry.items() if res != 'gold') # Exclude gold
        gold_amount = self.game_state.inventory.resources.get("gold", 0)
        
        shop_win.addstr(row, 2, f"Max Carry Weight: {max_weight}") ; row += 1
        shop_win.addstr(row, 2, f"Current Weight: {current_weight} (+ {gold_amount} Gold)") ; row += 2

        shop_win.addstr(row, 2, "Resource")
        shop_win.addstr(row, 20, "Available")
        shop_win.addstr(row, 35, "Carrying")
        shop_win.addstr(row, 50, "(+/-)")
        row +=1
        shop_win.hline(row, 1, '-', shop_w - 2); row += 1

        # Define resources EXCLUDING gold for display
        shop_resources = ['stone', 'wood', 'food', 'crystals', 'fungi', 'magic_fungi'] # Exclude 'gold'
        add_key_chars = '123456'
        remove_key_chars = '!@#$%^'
        
        for i, res in enumerate(shop_resources):
             if row >= shop_h - 4: break # Stop if not enough space
             available = self.game_state.inventory.resources.get(res, 0)
             carrying = self.game_state.shop_carry.get(res, 0)
             shop_win.addstr(row, 2, res.capitalize())
             shop_win.addstr(row, 20, str(available))
             shop_win.addstr(row, 35, str(carrying))
             shop_win.addstr(row, 50, f"({add_key_chars[i]}/{remove_key_chars[i]})")
             row += 1
        
        row = shop_h - 4 # Move to bottom for commands
        shop_win.addstr(row, 2, "Commands: (s) Show Sell Value, (r) Reset Carry")
        row += 1
        if self.game_state.shop_confirm:
             shop_win.addstr(row, 2, "CONFIRM DESCENT? (y/n)".ljust(shop_w-4), curses.A_REVERSE)
        else:
             shop_win.addstr(row, 2, "Press (y) to Descend, (n) to Cancel")

        shop_win.refresh()
        if not self.game_state.in_shop:
            # Clean up the overlay window
            shop_win.erase()
            shop_win.refresh()
            del shop_win
            
            # Force a complete redraw
            self.screen.clear()
            self.screen.refresh()
            self.render()
            curses.doupdate()

    def show_legend_screen(self):
        """Displays the map legend overlay window.

        Creates a new window centered on the screen. Dynamically populates
        the legend by iterating through `ENTITY_REGISTRY`, grouping entities
        by class (Structure, ResourceNode, etc.), and showing their character,
        name, and color. Also includes entries for actors (Dwarf, Animal, NPC).
        Handles cleanup and redraw if the legend state changes.
        """
        leg_h, leg_w = 25, 40
        leg_y = (self.max_y - leg_h) // 2
        leg_x = (self.max_x - leg_w) // 2
        leg_win = curses.newwin(leg_h, leg_w, leg_y, leg_x)
        leg_win.erase()
        leg_win.border()
        leg_win.addstr(1, (leg_w - 6) // 2, "Legend")

        row = 3
        def add_legend_entry(char, name, color_index):
            nonlocal row
            if row < leg_h - 2:
                try:
                     leg_win.addch(row, 4, char, curses.color_pair(color_index))
                     leg_win.addstr(row, 6, f": {name}")
                     row += 1
                except curses.error: row += 1

        # Use ENTITY_REGISTRY to populate legend dynamically
        # Sort for consistency? Maybe group by type?
        sorted_entities = sorted(ENTITY_REGISTRY.items(), key=lambda item: item[1].__class__.__name__)

        current_category = ""
        for name, entity in sorted_entities:
            category = entity.__class__.__name__
            if category != current_category:
                 if row < leg_h - 3: leg_win.addstr(row, 2, f"--- {category}s ---") ; row +=1
                 current_category = category
            
            add_legend_entry(entity.char, entity.name, entity.color)

        # Add non-entity symbols
        if row < leg_h - 3: leg_win.addstr(row, 2, f"--- Actors ---") ; row +=1
        add_legend_entry('D', "Dwarf", 15)
        add_legend_entry('A', "Animal", 12)
        add_legend_entry('C', "Character/NPC", 14)

        leg_win.addstr(leg_h - 2, 2, "Press 'l' to close")
        leg_win.refresh()
        if not self.game_state.show_legend:
            # Clean up the overlay window
            leg_win.erase()
            leg_win.refresh()
            del leg_win
            
            # Force a complete redraw
            self.screen.clear()
            self.screen.refresh()
            self.render()
            curses.doupdate()

    def show_oracle_dialog_screen(self):
        """Displays the Oracle dialogue overlay window.

        Creates a new window centered on the screen, draws a border, title,
        and displays the dialogue content. Includes instructions on how to close it.
        Handles cleanup and redraw if the dialogue state changes.
        """
        dialog_h, dialog_w = 20, 60 # Adjust size as needed
        dialog_y = (self.max_y - dialog_h) // 2
        dialog_x = (self.max_x - dialog_w) // 2
        dialog_win = curses.newwin(dialog_h, dialog_w, dialog_y, dialog_x)
        dialog_win.erase()
        dialog_win.border()
        dialog_win.addstr(1, (dialog_w - 15) // 2, "Oracle Dialogue") # Centered title

        row = 3
        # --- Placeholder Dialogue Content ---
        # In the future, this will display text from the LLM interaction
        placeholder_text = [
            "The Oracle's fungal form pulses gently.",
            "",
            "'Greetings, seeker... What knowledge do you wish to unearth?'",
            "",
            "(Placeholder - LLM interaction will go here)"
        ]
        for line in placeholder_text:
             if row < dialog_h - 2:
                 # Simple word wrap (basic implementation)
                 # A proper implementation might use textwrap.wrap
                 max_line_width = dialog_w - 4 # Account for border and padding
                 if len(line) > max_line_width:
                     words = line.split(' ')
                     current_line = ""
                     for word in words:
                         if len(current_line) + len(word) + 1 <= max_line_width:
                             current_line += word + " "
                         else:
                             if row < dialog_h - 2: dialog_win.addstr(row, 2, current_line.strip()) ; row += 1
                             current_line = word + " "
                     if current_line.strip() and row < dialog_h - 2: dialog_win.addstr(row, 2, current_line.strip()) ; row += 1
                 else:
                     dialog_win.addstr(row, 2, line); row += 1
             else:
                 break # Stop if window is full
        # --- End Placeholder ---
        
        dialog_win.addstr(dialog_h - 2, 2, "Press 't' or 'q' to close")
        dialog_win.refresh()
        
        if not self.game_state.show_oracle_dialog:
            # Clean up the overlay window
            dialog_win.erase()
            dialog_win.refresh()
            del dialog_win
            
            # Force a complete redraw of the underlying screen
            self.screen.clear() 
            self.screen.refresh()
            self.render() # Redraw map, UI, log
            curses.doupdate()

    def _get_mycelial_distance(self, coords):
        """Helper method to get the distance from coordinates to the nexus
        using the pre-calculated distances in GameState.

        Args:
            coords (tuple): The (x, y) coordinates.

        Returns:
            int: The distance calculated by `game_state.get_mycelial_distance`.
        """
        # Use the game state's mycelial network instead of building our own
        return self.game_state.get_mycelial_distance(coords)

# Ensure color pairs cover all entity.color values used in ENTITY_REGISTRY
# Ensure tile drawing uses entity.char and entity.color
