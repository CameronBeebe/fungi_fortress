#!/usr/bin/env python
"""Main entry point for the Fungi Fortress game.

Initializes the curses environment, sets up the core game components
(GameState, Renderer, InputHandler, GameLogic), and runs the main game loop.
Uses curses.wrapper to ensure proper terminal cleanup.
"""
import curses
import time
import sys # Import sys for stdout/stderr
import logging # Import logging
import os # Import os for environment variables

# Set ESC key delay to 25ms instead of default 1000ms (fallback for older Python)
# This must be set before any curses initialization
os.environ.setdefault("ESCDELAY", "25")

# Use absolute imports from the package
from fungi_fortress.game_state import GameState
from fungi_fortress.renderer import Renderer
from fungi_fortress.input_handler import InputHandler
from fungi_fortress.game_logic import GameLogic
# These can also be imported at the top level now
from fungi_fortress.map_generation import generate_map
from fungi_fortress.characters import Dwarf
from fungi_fortress.tiles import ENTITY_REGISTRY
from .config_manager import load_oracle_config, OracleConfig

# --- Basic File Logger Setup for Initialization ---
LOG_FILENAME = "ff_init_debug.log"
logging.basicConfig(
    filename=LOG_FILENAME,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s',
    filemode='w' # Overwrite log each run for this specific init debug
)
# --- End Logger Setup ---

def main(stdscr: curses.window):
    """Initializes and runs the main game loop.

    Sets up the curses environment, initializes game state, renderer,
    input handler, and game logic components. Enters the main loop which
    handles user input, updates game logic at a fixed rate, and renders
    the game screen until the user quits.

    Args:
        stdscr: The main curses window object provided by curses.wrapper.
    """
    logging.info("Main function started.") # Log start of main

    # Set ESC key delay to 25ms for faster ESC key response (Python 3.9+)
    if hasattr(curses, 'set_escdelay'):
        curses.set_escdelay(25)

    # Set a very low timeout for input polling (1ms)
    stdscr.timeout(1)

    # Load Oracle configuration first
    oracle_config = load_oracle_config()
    
    # Log the loaded OracleConfig, masking the API key
    masked_api_key = "'****'" if oracle_config.api_key and oracle_config.is_real_api_key_present else f"'{oracle_config.api_key}'"
    logging.info(f"[MAIN.PY] Loaded oracle_config. API Key: {masked_api_key}, Model: {oracle_config.model_name}, Real Key Present: {oracle_config.is_real_api_key_present}, Type: {type(oracle_config)}")

    logging.info("[MAIN.PY] Fungi Fortress initialization complete.")
    
    stdscr.nodelay(True)  # Non-blocking input
    game_state = GameState(oracle_config=oracle_config)
    renderer: Renderer = Renderer(stdscr, game_state)
    input_handler: InputHandler = InputHandler(game_state)
    game_logic: GameLogic = GameLogic(game_state)

    # Initialize map and first dwarf/player state if needed
    from fungi_fortress.constants import MAP_WIDTH, MAP_HEIGHT
    map_width, map_height = MAP_WIDTH, MAP_HEIGHT

    initial_map, nexus_site, magic_fungi = generate_map(
        map_width, map_height, game_state.depth, game_state.mission
    )
    game_state.map = initial_map
    game_state.main_map = initial_map # Keep a reference
    game_state.nexus_site = nexus_site
    game_state.magic_fungi_locations = magic_fungi

    # Find initial spawn point
    spawn_x, spawn_y = None, None
    grass_entity = ENTITY_REGISTRY.get("grass") # Use .get for safety
    if grass_entity:
        for y in range(len(game_state.map)):
            for x in range(len(game_state.map[0])):
                 # Spawn on grass if possible
                if game_state.map[y][x].entity == grass_entity:
                     spawn_x, spawn_y = x, y
                     break
            if spawn_x is not None: break
    
    # Fallback spawn
    if spawn_x is None:
         spawn_x, spawn_y = map_width // 2, map_height // 2
         game_state.add_debug_message("Warning: No grass found for spawn, using center.")

    game_state.dwarves = [Dwarf(spawn_x, spawn_y, 0)]  # Only spawn one dwarf
    game_state.cursor_x, game_state.cursor_y = spawn_x, spawn_y
    game_state.add_debug_message(f"Spawned at ({spawn_x}, {spawn_y})")

    # Target 10 FPS for game logic updates
    target_logic_time = 1.0 / 10.0
    # Target 30 FPS for rendering
    target_render_time = 1.0 / 30.0
    
    last_logic_time: float = time.monotonic()
    last_render_time: float = last_logic_time
    
    # Track if we need to render this frame
    needs_render: bool = True

    while True:
        current_time: float = time.monotonic()
        
        # Always handle input with minimal delay
        key: int = stdscr.getch()
        if key != -1:  # Key was pressed
            if not input_handler.handle_input(key):
                break  # Exit if handler returns False (e.g., on 'q')
            needs_render = True  # Ensure we render after input changes
        
        # Update game logic at fixed rate
        elapsed_since_logic = current_time - last_logic_time
        if elapsed_since_logic >= target_logic_time:
            # Allow logic update when Oracle dialogue is active (for API calls)
            # Skip logic update only if paused without Oracle dialogue, or other overlays are active
            oracle_dialogue_active = game_state.show_oracle_dialog
            paused_without_oracle = game_state.paused and not oracle_dialogue_active
            other_overlays_active = game_state.show_inventory or game_state.in_shop or game_state.show_legend
            
            if not (paused_without_oracle or other_overlays_active):
                game_logic.update()
                needs_render = True
            last_logic_time = current_time - (elapsed_since_logic % target_logic_time)  # Maintain fixed timestep
        
        # Render at higher framerate, but only if needed
        elapsed_since_render = current_time - last_render_time
        if elapsed_since_render >= target_render_time and needs_render:
            # Don't clear the entire screen, let the renderer handle its windows
            if game_state.show_inventory:
                renderer.show_inventory_screen()
            elif game_state.in_shop:
                renderer.show_shop_screen()
            elif game_state.show_legend:
                renderer.show_legend_screen()
            elif game_state.show_oracle_dialog:
                renderer.show_oracle_dialog_screen()
            elif game_state.show_quest_menu:
                renderer.show_quest_content_screen()
            else:
                renderer.render()
            
            # Use curses.doupdate() to synchronize all window updates at once
            curses.doupdate()
            
            last_render_time = current_time
            needs_render = False  # Reset the render flag
        
        # Small sleep to prevent CPU spinning
        time.sleep(0.001)  # 1ms sleep

if __name__ == "__main__":
    curses.wrapper(main)

# Comments:
# - Removed redundant curses setup.
# - Passed stdscr to Renderer.
# - Called renderer.render().
# - Added basic initial map generation and dwarf placement.
# - Added logic to handle overlay states (inventory, shop, legend).
# - Removed sys.path manipulation.
# - Added type hints for stdscr and key variables.
# - Removed try/except block around constants import.
