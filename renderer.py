import curses
import random
import math
from typing import TYPE_CHECKING, List

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
from .characters import Oracle # For type hinting if needed, and for checking entity type
from .oracle_logic import get_canned_response # Though input_handler mostly sets dialogue

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
                    # Use tile.color property which correctly resolves override or entity color
                    is_mycelial_color_val = tile.color # Get the resolved color
                    is_mycelial = (is_mycelial_color_val in [5, 13, 16, 201, 206]) and tile._color_override is not None

                    if is_mycelial:
                        # For mycelial network, use foreground colors only with pulsing effects
                        final_color_pair_index = is_mycelial_color_val
                        
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
                    final_color_pair_index = tile.color # Use the property here, it handles None _color_override
                    # Specific visual treatment for mycelial path highlights (which set _color_override)
                    if tile._color_override in [5, 13, 16, 201, 206]: # Check if it was a mycelial-specific override
                        tick_offset = (self.game_state.tick + tile.x + tile.y) % 20
                        if tick_offset < 10:
                            final_attr = curses.A_BOLD
                        else:
                            final_attr = curses.A_NORMAL
                    # If not a mycelial-specific override, final_color_pair_index is already correctly set
                    # by tile.color (either to another override or entity's default, or fallback like 15 if that logic was there).
                    # The original fallback to 15 if _color_override was None is now handled by tile.color returning entity.color.
                    # If a generic highlight (non-mycelial) needs a *different* default color than entity.color,
                    # that logic would need to be added here, e.g.,
                    # else: final_color_pair_index = 15 # A generic highlight color if not mycelial and no specific override

                # 2. Check for Flicker (Overrides Generic Effects for these entities)
                if entity.is_mycelial: # This applies to entities marked as mycelial, not just paths
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
        # Show quest content hotkey with indicator if new content is available
        quest_hotkey_text = " q: quest content"
        if self.game_state.new_oracle_content_count > 0:
            quest_hotkey_text += f" ({self.game_state.new_oracle_content_count} new!)"
            add_ui_line(quest_hotkey_text, curses.A_BOLD | curses.color_pair(2))  # Highlight when new content available
        else:
            add_ui_line(quest_hotkey_text)
        add_ui_line(" t: talk") 
        add_ui_line(" e: enter/interact")
        add_ui_line(" b: build")
        add_ui_line(" d: descend/shop")
        add_ui_line(" p: pause")
        add_ui_line(" ESC: quit")
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

        # --- Render Oracle Dialog if active ---
        if self.game_state.show_oracle_dialog:
            self.show_oracle_dialog_screen()
        
        # --- Render Active Pulses ---
        self._render_active_pulses()
        
        # --- Refresh Windows --- 
        self.map_win.refresh()
        self.ui_win.refresh()
        self.log_win.refresh()

    def _render_active_pulses(self):
        """Renders all active mycelial pulses on the map."""
        if not hasattr(self.game_state, 'active_pulses') or not self.game_state.active_pulses:
            return

        # Get camera offsets for rendering
        cam_x, cam_y, _, _ = self._get_camera_bounds()

        for pulse in self.game_state.active_pulses:
            pulse_color_pair = curses.color_pair(pulse["pulse_color"]) 
            for r_x, r_y in pulse["tiles_to_render"]:
                # Apply camera offset for rendering
                screen_x, screen_y = r_x - cam_x, r_y - cam_y
                # Check if the tile is within the visible map window
                if 0 <= screen_y < MAP_HEIGHT and 0 <= screen_x < MAP_WIDTH:
                    try:
                        # Get the character currently at that position to overlay the pulse color
                        # If the tile has a specific highlight from path reveal, that takes precedence for char/attr
                        tile_to_pulse = self.game_state.get_tile(r_x, r_y)
                        char_to_draw = tile_to_pulse.entity.char if tile_to_pulse and tile_to_pulse.entity else ' '
                        base_attr = curses.A_NORMAL
                        if tile_to_pulse and tile_to_pulse.highlight_ticks > 0 and tile_to_pulse._color_override is not None:
                             # If still under initial path reveal, use its color but pulse char might dominate
                             # This part might need tweaking based on desired visual layering
                            pass # Color already set by pulse_color_pair
                        
                        # Draw the pulse segment
                        self.map_win.addch(screen_y, screen_x, char_to_draw, pulse_color_pair | base_attr)
                    except curses.error: # Ignore errors if drawing outside window (should be caught by bounds check)
                        pass 

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

    def _get_camera_bounds(self) -> tuple[int, int, int, int]:
        """Returns the current camera bounds (x, y, width, height).
        Assumes no scrolling for now, so camera is at (0,0) and covers the full map window.
        """
        # TODO: Implement actual camera logic if scrolling is added.
        return 0, 0, MAP_WIDTH, MAP_HEIGHT

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

        inv_win.addstr(inv_h - 2, 2, "Press 'i' or ESC to close")
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

        leg_win.addstr(leg_h - 2, 2, "Press 'l' or ESC to close")
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
        """Shows the Oracle dialogue window.

        Displays current dialogue, prompt buffer, and handles scrolling.
        If an LLM response is being streamed, it will show the accumulating text.
        Uses `self.game_state.oracle_current_dialogue` (now List[Tuple[str,str]]) and
        `self.game_state.oracle_prompt_buffer`.
        """
        if not self.ui_win: return 

        dialog_h = 28 # Increased from 22
        dialog_w = 60  
        dialog_y = (self.max_y - dialog_h) // 2
        dialog_x = (self.max_x - dialog_w - UI_WIDTH) // 2 
        
        try:
            dialog_win = curses.newwin(dialog_h, dialog_w, dialog_y, dialog_x)
            dialog_win.erase()
            dialog_win.border()
            dialog_win.nodelay(True) 
        except curses.error:
            self.screen.addstr(0, 0, "Error: Could not create Oracle dialog window.")
            return

        title = f"~ {self.game_state.active_oracle_entity_id or 'The Oracle'} ~"
        title_x = (dialog_w - len(title)) // 2
        dialog_win.addstr(0, title_x, title, curses.A_BOLD)

        content_x = 2
        content_y_start = 2
        content_w = dialog_w - 4 
        max_content_h = (dialog_h - 6)

        current_dialogue_entries = self.game_state.oracle_current_dialogue
        total_lines = len(current_dialogue_entries)
        
        # Cap scroll index (this logic seems fine)
        if self.game_state.oracle_dialogue_page_start_index > total_lines - max_content_h and total_lines > max_content_h:
            self.game_state.oracle_dialogue_page_start_index = total_lines - max_content_h
        if self.game_state.oracle_dialogue_page_start_index < 0:
            self.game_state.oracle_dialogue_page_start_index = 0

        visible_lines = current_dialogue_entries[self.game_state.oracle_dialogue_page_start_index : 
                                                 self.game_state.oracle_dialogue_page_start_index + max_content_h]

        current_draw_y = content_y_start
        # Enumerate visible_lines to get a local index (0 for the first visible entry)
        for local_entry_idx, entry_tuple in enumerate(visible_lines):
            if current_draw_y >= content_y_start + max_content_h: # Safety break
                break
            
            text_line, style_tag = ("", "NORMAL") 
            if isinstance(entry_tuple, tuple) and len(entry_tuple) == 2:
                text_line, style_tag = entry_tuple
            elif isinstance(entry_tuple, str): 
                text_line = entry_tuple 
                if ( "Oracle contemplates" in text_line or
                     "communes with the mycelial network" in text_line or
                     "Ancient knowledge" in text_line or
                     "The Oracle's consciousness" in text_line or
                     ">" in text_line # Player query also often italicized or distinct
                   ):
                    style_tag = "ITALIC"

            attributes = curses.A_NORMAL
            if style_tag == "ITALIC":
                attributes = curses.A_DIM 
            elif style_tag == "BOLD": 
                attributes = curses.A_BOLD

            wrapped_sub_lines = self._wrap_text_for_dialog(text_line, content_w)

            for sub_line_idx, sub_line in enumerate(wrapped_sub_lines):
                if current_draw_y >= content_y_start + max_content_h:
                    break
                
                current_line_text_to_display = sub_line
                current_line_x_offset = 0

                # Check if this is the first sub-line of the first visible (focused) entry
                is_focused_line = (local_entry_idx == 0 and sub_line_idx == 0)

                if is_focused_line:
                    try:
                        # Draw the indicator ">"
                        dialog_win.addstr(current_draw_y, content_x, ">", attributes)
                    except curses.error:
                        pass # Ignore error if indicator can't be drawn
                    current_line_x_offset = 2 # Indent text by 2 characters (for "> ")

                    # If the line was full width, we need to truncate it to fit after the indicator
                    max_len_for_indented_text = content_w - current_line_x_offset
                    if len(sub_line) > max_len_for_indented_text:
                        current_line_text_to_display = sub_line[:max_len_for_indented_text]
                    # else, sub_line is short enough or already fits, use as is.

                try:
                    dialog_win.addstr(current_draw_y, content_x + current_line_x_offset, current_line_text_to_display, attributes)
                except curses.error: 
                    pass 
                current_draw_y += 1
        
        # After rendering historical/committed dialogue, render the live streaming buffer if active
        if self.game_state.oracle_streaming_active and hasattr(self.game_state, 'oracle_streaming_line_buffer'):
            live_text, live_style = self.game_state.oracle_streaming_line_buffer
            if live_text: # Only render if there's text in the live buffer
                live_attributes = curses.A_NORMAL
                if live_style == "ITALIC":
                    live_attributes = curses.A_DIM
                elif live_style == "BOLD":
                    live_attributes = curses.A_BOLD
                
                # Wrap the live text using the renderer's own wrapper
                wrapped_live_sub_lines = self._wrap_text_for_dialog(live_text, content_w)
                
                for sub_line in wrapped_live_sub_lines:
                    if current_draw_y >= content_y_start + max_content_h:
                        break # Stop if we run out of dialogue box space
                    try:
                        dialog_win.addstr(current_draw_y, content_x, sub_line, live_attributes)
                    except curses.error: 
                        pass 
                    current_draw_y += 1

        if total_lines > max_content_h or (self.game_state.oracle_streaming_active and live_text): # Adjust scrollbar logic if live text is also present
            # Determine if scroll up indicator is needed
            if self.game_state.oracle_dialogue_page_start_index > 0:
                dialog_win.addstr(content_y_start, dialog_w - 3, "^", curses.A_REVERSE) 
            # Determine if scroll down indicator is needed
            # Consider live text not yet in total_lines for scroll down indicator
            effective_total_lines = total_lines
            if self.game_state.oracle_streaming_active and self.game_state.oracle_streaming_line_buffer[0]:
                # Estimate lines the live buffer will take, could be 1 or more after wrapping
                # For simplicity, assume it adds at least one more potential line if not empty.
                effective_total_lines += 1 

            if self.game_state.oracle_dialogue_page_start_index < effective_total_lines - max_content_h:
                dialog_win.addstr(content_y_start + max_content_h - 1, dialog_w - 3, "v", curses.A_REVERSE)

        prompt_y = dialog_h - 3
        dialog_win.hline(prompt_y -1, 1, curses.ACS_HLINE, dialog_w - 2)
        
        interaction_state = self.game_state.oracle_interaction_state
        prompt_prefix = ""
        display_prompt_buffer = True

        if interaction_state == "AWAITING_OFFERING":
            prompt_prefix = "Offer? (Y/N): "
        elif interaction_state == "AWAITING_PROMPT":
            prompt_prefix = "Your Query: "
        elif interaction_state == "AWAITING_LLM_RESPONSE":
            prompt_prefix = "Query Sent..."
            display_prompt_buffer = False 
        elif interaction_state == "STREAMING_RESPONSE":
            prompt_prefix = "Oracle Speaks..." 
            display_prompt_buffer = False
        elif interaction_state == "SHOWING_CANNED_RESPONSE" or self.game_state.oracle_no_api_second_stage_pending:
            prompt_prefix = "(Press Enter)"
            display_prompt_buffer = False
        else: 
            prompt_prefix = "Oracle: "
            display_prompt_buffer = False

        dialog_win.addstr(prompt_y, content_x, prompt_prefix)
        
        if display_prompt_buffer:
            prompt_text = self.game_state.oracle_prompt_buffer
            max_prompt_len = content_w - len(prompt_prefix) -1 
            
            if len(prompt_text) > max_prompt_len:
                prompt_text_to_show = "..." + prompt_text[-(max_prompt_len-3):]
            else:
                prompt_text_to_show = prompt_text

            dialog_win.addstr(prompt_y, content_x + len(prompt_prefix), prompt_text_to_show)
            
            if (self.game_state.tick // 5) % 2 == 0: 
                cursor_x_pos = content_x + len(prompt_prefix) + len(prompt_text_to_show)
                if cursor_x_pos < dialog_w -1: 
                    try:
                        dialog_win.addch(prompt_y, cursor_x_pos, '_', curses.A_BLINK)
                    except curses.error: 
                        pass 

        dialog_win.refresh()

    def _wrap_text_for_dialog(self, text: str, max_width: int) -> List[str]:
        """Simple text wrapper for dialog lines."""
        # If the text already fits, and game_logic.py presumably already formatted it,
        # return it as a single line to prevent re-wrapping by the renderer.
        if len(text) <= max_width:
            return [text] if text else [""] # Ensure at least one line even for empty input text

        words = text.split(' ')
        lines = []
        current_line = ""
        for word in words:
            if not current_line:
                current_line = word
            elif len(current_line) + 1 + len(word) <= max_width:
                current_line += " " + word
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        return lines if lines else [""] # Ensure at least one line for empty strings

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

    def show_quest_content_screen(self):
        """Displays the oracle-generated content/quest window.

        Creates a new window centered on the screen. Shows oracle-generated
        quests, characters, items, events, and other content with a summary
        of what was created during oracle interactions.
        Handles cleanup and redraw if the quest menu state changes.
        """
        quest_h, quest_w = 25, 70
        quest_y = (self.max_y - quest_h) // 2
        quest_x = (self.max_x - quest_w) // 2
        quest_win = curses.newwin(quest_h, quest_w, quest_y, quest_x)
        quest_win.erase()
        quest_win.border()
        
        # Show title with new content indicator if applicable
        title = "Oracle-Generated Content"
        if self.game_state.new_oracle_content_count > 0:
            title += f" ({self.game_state.new_oracle_content_count} NEW!)"
        quest_win.addstr(1, (quest_w - len(title)) // 2, title, curses.A_BOLD)

        row = 3
        
        # Check if there's any content to display
        if not self.game_state.oracle_generated_content:
            quest_win.addstr(row, 2, "No oracle-generated content yet.")
            quest_win.addstr(row + 1, 2, "Consult an Oracle to generate quests, characters,")
            quest_win.addstr(row + 2, 2, "items, and events for your game world.")
            quest_win.addstr(row + 4, 2, "Generated content will appear here after successful")
            quest_win.addstr(row + 5, 2, "oracle interactions with structured outputs.")
        else:
            # Show summary statistics first
            total_content = len(self.game_state.oracle_generated_content)
            new_content = self.game_state.new_oracle_content_count
            quest_win.addstr(row, 2, f"Total Generated: {total_content} items")
            if new_content > 0:
                quest_win.addstr(row, 35, f"New since last view: {new_content}", curses.A_BOLD | curses.color_pair(2))  # Yellow/highlight
            row += 2
            
            # Group content by type
            content_by_type = {}
            for content in self.game_state.oracle_generated_content:
                content_type = content.get("type", "other")
                if content_type not in content_by_type:
                    content_by_type[content_type] = []
                content_by_type[content_type].append(content)
            
            # Display content by categories
            for content_type, items in content_by_type.items():
                if row >= quest_h - 4:  # Leave space for close message
                    quest_win.addstr(row, 2, "... (more content available)")
                    break
                    
                # Category header
                category_name = {
                    "quest": "Quests",
                    "character": "Characters", 
                    "item": "Items",
                    "event": "Events",
                    "other": "Other Content"
                }.get(content_type, content_type.title())
                
                quest_win.addstr(row, 2, f"--- {category_name} ({len(items)}) ---")
                row += 1
                
                # List items in this category, highlighting new ones
                current_tick = self.game_state.tick
                for item in items[-6:]:  # Show last 6 items per category (most recent first)
                    if row >= quest_h - 4:
                        break
                        
                    name = item.get("name", "Unknown")
                    tick = item.get("tick", 0)
                    
                    # Calculate how "new" this content is (within last 50 ticks is considered recent)
                    is_recent = (current_tick - tick) < 50
                    
                    # Build display text with more information
                    item_text = f"  • {name}"
                    
                    # Add description preview if available
                    description = item.get("description", "")
                    if description and len(description) > 0:
                        # Add first part of description, truncated
                        preview = description[:30] + "..." if len(description) > 30 else description
                        item_text += f" - {preview}"
                    
                    # Add tick info
                    item_text += f" (tick {tick})"
                    
                    # Truncate if too long
                    if len(item_text) > quest_w - 4:
                        item_text = item_text[:quest_w - 7] + "..."
                    
                    # Display with highlighting for recent content
                    if is_recent:
                        quest_win.addstr(row, 2, item_text, curses.A_BOLD | curses.color_pair(2))  # Highlight recent content
                    else:
                        quest_win.addstr(row, 2, item_text)
                    row += 1
                
                if len(items) > 6:
                    quest_win.addstr(row, 4, f"... and {len(items) - 6} more")
                    row += 1
                
                row += 1  # Add space between categories

        quest_win.addstr(quest_h - 2, 2, "Press ESC to close")
        quest_win.refresh()
        
        # Reset new content counter when window is viewed
        if self.game_state.new_oracle_content_count > 0:
            self.game_state.new_oracle_content_count = 0
        
        if not self.game_state.show_quest_menu:
            # Clean up the overlay window
            quest_win.erase()
            quest_win.refresh()
            del quest_win
            
            # Force a complete redraw
            self.screen.clear()
            self.screen.refresh()
            self.render()
            curses.doupdate()

# Ensure color pairs cover all entity.color values used in ENTITY_REGISTRY
# Ensure tile drawing uses entity.char and entity.color
