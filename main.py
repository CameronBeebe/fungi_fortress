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

# --- Basic File Logger Setup for Initialization ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # Get the directory of the current script
LOG_FILENAME = os.path.join(SCRIPT_DIR, "llm_interactions.log") # Create an absolute path for the log file
# Ensure the directory for the log file exists if it's not in the current directory
# For now, assume it's in the current directory or a path accessible from it.
logging.basicConfig(
    filename=LOG_FILENAME,
    level=logging.INFO, # Ensure INFO level is captured
    format='%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s', # Changed module to name for clarity
    filemode='w', # Overwrite log each run
    force=True # Add force=True to ensure re-configuration if already configured by another module (Python 3.8+)
)

# Initial log message to confirm logger is working
logging.info("--- Fungi Fortress Game Starting --- Logger Initialized.")
# --- End Logger Setup ---


# Set ESC key delay to 25ms instead of default 1000ms (fallback for older Python)
# This must be set before any curses initialization
os.environ.setdefault("ESCDELAY", "25")

# Use absolute imports from the package
try:
    # Try package imports first (when run as module)
    from fungi_fortress.game_state import GameState
    from fungi_fortress.renderer import Renderer
    from fungi_fortress.input_handler import InputHandler
    from fungi_fortress.game_logic import GameLogic
    from fungi_fortress.map_generation import generate_map, generate_mycelial_network
    from fungi_fortress.characters import Dwarf
    from fungi_fortress.tiles import ENTITY_REGISTRY
    from fungi_fortress.config_manager import load_llm_config, LLMConfig
except ImportError as e:
    logging.error(f"Package import failed: {e}. Falling back to relative imports.")
    # Fall back to relative imports (when run directly)
    from .game_state import GameState
    from .renderer import Renderer
    from .input_handler import InputHandler
    from .game_logic import GameLogic
    from .map_generation import generate_map, generate_mycelial_network
    from .characters import Dwarf
    from .tiles import ENTITY_REGISTRY
    from .config_manager import load_llm_config, LLMConfig

def main(stdscr: curses.window):
    """Initializes and runs the main game loop.

    Sets up the curses environment, initializes game state, renderer,
    input handler, and game logic components. Enters the main loop which
    handles user input, updates game logic at a fixed rate, and renders
    the game screen until the user quits.

    Args:
        stdscr: The main curses window object provided by curses.wrapper.
    """
    logging.info("Curses main function started.") # Log start of main

    # Set ESC key delay to 25ms for faster ESC key response (Python 3.9+)
    if hasattr(curses, 'set_escdelay'):
        curses.set_escdelay(25)

    # Set a very low timeout for input polling (1ms)
    stdscr.timeout(1)

    # Load LLM configuration first
    logging.info("Loading LLM configuration...")
    llm_config = load_llm_config()
    
    # Log the loaded LLMConfig, masking the API key
    if llm_config:
        masked_api_key = "'****'" if llm_config.api_key and llm_config.is_real_api_key_present else f"'{llm_config.api_key}'"
        logging.info(f"Loaded llm_config. API Key: {masked_api_key}, Model: {llm_config.model_name}, Provider: {llm_config.provider}, Real Key Present: {llm_config.is_real_api_key_present}, Type: {type(llm_config)}")
    else:
        logging.error("LLM configuration loading returned None. LLM features will be impaired.")

    logging.info("Fungi Fortress initialization starting...")
    
    stdscr.nodelay(True)  # Non-blocking input
    game_state = GameState(llm_config=llm_config)
    renderer: Renderer = Renderer(stdscr, game_state)
    input_handler: InputHandler = InputHandler(game_state)
    game_logic: GameLogic = GameLogic(game_state)
    logging.info("Core game components initialized.")

    # Initialize map and first dwarf/player state if needed
    try:
        from fungi_fortress.constants import MAP_WIDTH, MAP_HEIGHT
    except ImportError:
        logging.warning("Failed to import constants from package, trying direct import.")
        from constants import MAP_WIDTH, MAP_HEIGHT
    map_width, map_height = MAP_WIDTH, MAP_HEIGHT
    logging.info(f"Map dimensions set to {map_width}x{map_height}.")

    initial_map, nexus_site, magic_fungi = generate_map(
        map_width, map_height, game_state.depth, game_state.mission
    )
    game_state.map = initial_map
    game_state.main_map = initial_map # Keep a reference
    game_state.nexus_site = nexus_site
    game_state.magic_fungi_locations = magic_fungi
    logging.info("Initial map generated and set in game_state.")

    # Generate and set the mycelial network for the main map
    if nexus_site: # Only generate if a nexus site exists
        game_state.mycelial_network = generate_mycelial_network(initial_map, nexus_site, magic_fungi if magic_fungi else [])
        game_state.network_distances = game_state.calculate_network_distances() # Calculate distances for the new network
        logging.info(f"Initial mycelial network generated for the main map with {len(game_state.mycelial_network)} nodes.")
    else:
        game_state.mycelial_network = {} # Ensure it's an empty dict if no nexus
        game_state.network_distances = {}
        logging.warning("Initial mycelial network NOT generated for the main map as nexus_site is None.")

    # Find initial spawn point
    spawn_x, spawn_y = None, None
    grass_entity = ENTITY_REGISTRY.get("grass") # Use .get for safety
    if grass_entity:
        for y_coord in range(len(game_state.map)):
            for x_coord in range(len(game_state.map[0])):
                 # Spawn on grass if possible
                if game_state.map[y_coord][x_coord].entity == grass_entity:
                     spawn_x, spawn_y = x_coord, y_coord
                     break
            if spawn_x is not None: break
    
    # Fallback spawn
    if spawn_x is None:
         spawn_x, spawn_y = map_width // 2, map_height // 2
         game_state.add_debug_message("Warning: No grass found for spawn, using center.")
         logging.warning("No grass found for spawn, using center coordinates.")

    game_state.dwarves = [Dwarf(spawn_x, spawn_y, 0)]  # Only spawn one dwarf
    game_state.cursor_x, game_state.cursor_y = spawn_x, spawn_y
    game_state.add_debug_message(f"Spawned at ({spawn_x}, {spawn_y})")
    logging.info(f"Player character spawned at ({spawn_x}, {spawn_y}).")

    # Target 10 FPS for game logic updates
    target_logic_time = 1.0 / 10.0
    # Target 30 FPS for rendering
    target_render_time = 1.0 / 30.0
    
    last_logic_time: float = time.monotonic()
    last_render_time: float = last_logic_time
    
    # Track if we need to render this frame
    needs_render: bool = True
    logging.info("Entering main game loop...")

    while True:
        current_time: float = time.monotonic()
        
        # Always handle input with minimal delay
        key_pressed: int = stdscr.getch()
        if key_pressed != -1:  # Key was pressed
            logging.debug(f"Key pressed: {key_pressed}")
            if not input_handler.handle_input(key_pressed):
                logging.info("Input handler returned False. Exiting game loop.")
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
                # logging.debug("Updating game logic...") # This can be very verbose
                game_logic.update()
                needs_render = True
            # else:
                # logging.debug("Game logic update skipped due to pause/overlay.")
            last_logic_time = current_time - (elapsed_since_logic % target_logic_time)  # Maintain fixed timestep
        
        # Render at higher framerate, but only if needed
        elapsed_since_render = current_time - last_render_time
        if elapsed_since_render >= target_render_time and needs_render:
            # logging.debug("Rendering game screen...") # This can be very verbose
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
    
    logging.info("--- Fungi Fortress Game Exiting --- Flushing logs.")
    logging.shutdown() # Ensure all logs are flushed

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except Exception as e:
        logging.exception("Unhandled exception in curses.wrapper or main function.")
        print(f"FATAL ERROR: {e}", file=sys.stderr)
        # Attempt to shutdown logging gracefully even on fatal error
        logging.shutdown()
        sys.exit(1)

# Comments:
# - Removed redundant curses setup.
# - Passed stdscr to Renderer.
# - Called renderer.render().
# - Added basic initial map generation and dwarf placement.
# - Added logic to handle overlay states (inventory, shop, legend).
# - Removed sys.path manipulation.
# - Added type hints for stdscr and key variables.
# - Removed try/except block around constants import.
