#!/usr/bin/env python
"""Main game application logic for Fungi Fortress.

Contains the main game loop that can be imported and run by entry points.
This module is part of the fungi_fortress package and does not depend on
any files outside the package.
"""
import curses
import time
import sys
import logging
import os
import traceback
import json
from datetime import datetime

from .play_log import start_play_log
from .game_state import GameState
from .renderer import Renderer
from .input_handler import InputHandler
from .game_logic import GameLogic
from .map_generation import generate_map, generate_mycelial_network
from .characters import Dwarf
from .tiles import ENTITY_REGISTRY
from .config_manager import load_llm_config

PLAY_LOG_PATH = start_play_log()
logging.info("--- Fungi Fortress Game Starting ---")


# Set ESC key delay to 25ms instead of default 1000ms (fallback for older Python)
# This must be set before any curses initialization
os.environ.setdefault("ESCDELAY", "25")

def initialize_new_game(game_state: GameState) -> str:
    """Initialize a new game: regenerate map, spawn dwarf, grow world.
    
    This is the canonical new-game setup path that runs after GameState.__init__.
    It regenerates the map (overwriting the initial one from __init__), places the
    dwarf, and calls grow_world to spawn NPCs on the final map.
    
    Args:
        game_state: The GameState instance to initialize (already constructed).
        
    Returns:
        str: The world note from grow_world for logging/display.
    """
    from .constants import MAP_WIDTH, MAP_HEIGHT
    from .characters import Dwarf
    from .tiles import ENTITY_REGISTRY
    from .world_seed import grow_world
    
    map_width, map_height = MAP_WIDTH, MAP_HEIGHT
    logging.info(f"Initializing new game with map dimensions {map_width}x{map_height}.")

    # Regenerate map (replaces the initial map from GameState.__init__)
    initial_map, nexus_site, magic_fungi = generate_map(
        map_width, map_height, game_state.depth, game_state.mission
    )
    game_state.map = initial_map
    game_state.main_map = initial_map
    game_state.nexus_site = nexus_site
    game_state.magic_fungi_locations = magic_fungi
    logging.info("Map regenerated and set in game_state.")

    # Generate mycelial network for the final map
    if nexus_site:
        game_state.mycelial_network = generate_mycelial_network(
            initial_map, nexus_site, magic_fungi if magic_fungi else []
        )
        game_state.network_distances = game_state.calculate_network_distances()
        logging.info(f"Mycelial network generated with {len(game_state.mycelial_network)} nodes.")
    else:
        game_state.mycelial_network = {}
        game_state.network_distances = {}
        logging.warning("Mycelial network NOT generated (no nexus site).")

    # Find spawn point for dwarf
    spawn_x, spawn_y = None, None
    grass_entity = ENTITY_REGISTRY.get("grass")
    if grass_entity:
        for y_coord in range(len(game_state.map)):
            for x_coord in range(len(game_state.map[0])):
                if game_state.map[y_coord][x_coord].entity == grass_entity:
                    spawn_x, spawn_y = x_coord, y_coord
                    break
            if spawn_x is not None:
                break
    
    if spawn_x is None:
        spawn_x, spawn_y = map_width // 2, map_height // 2
        game_state.add_debug_message("Warning: No grass found for spawn, using center.")
        logging.warning("No grass found for spawn, using center coordinates.")

    game_state.dwarves = [Dwarf(spawn_x, spawn_y, 0)]
    game_state.cursor_x, game_state.cursor_y = spawn_x, spawn_y
    game_state.add_debug_message(f"Spawned at ({spawn_x}, {spawn_y})")
    logging.info(f"Dwarf spawned at ({spawn_x}, {spawn_y}).")

    # Grow world (spawns NPCs on the final map)
    world_note = grow_world(game_state)
    game_state.add_debug_message(world_note)
    logging.info(world_note)
    
    return world_note

def game_loop(stdscr: curses.window):
    """Initializes and runs the main game loop.

    Sets up the curses environment, initializes game state, renderer,
    input handler, and game logic components. Enters the main loop which
    handles user input, updates game logic at a fixed rate, and renders
    the game screen until the user quits.

    Args:
        stdscr: The main curses window object provided by curses.wrapper.
        
    Returns:
        Tuple of (game_logic, input_handler) for crash snapshot access
    """
    logging.info("Curses main function started.")

    # Set ESC key delay to 25ms for faster ESC key response (Python 3.9+)
    if hasattr(curses, 'set_escdelay'):
        curses.set_escdelay(25)

    # Set a very low timeout for input polling (1ms)
    stdscr.timeout(1)

    # Load LLM configuration first
    logging.info("Loading LLM configuration...")
    llm_config = load_llm_config()
    
    # Log the loaded  masking the API key
    if llm_config:
        masked_api_key = "'****'" if llm_config.api_key and llm_config.is_real_api_key_present else f"'{llm_config.api_key}'"
        logging.info(f"Loaded llm_config. API Key: {masked_api_key}, Model: {llm_config.model_name}, Real Key Present: {llm_config.is_real_api_key_present}, Type: {type(llm_config)}")
    else:
        logging.error("LLM configuration loading returned None. LLM features will be impaired.")

    logging.info("Fungi Fortress initialization starting...")
    
    stdscr.nodelay(True)  # Non-blocking input
    game_state = GameState(llm_config=llm_config)
    renderer: Renderer = Renderer(stdscr, game_state)
    input_handler: InputHandler = InputHandler(game_state)
    game_logic: GameLogic = GameLogic(game_state)
    logging.info("Core game components initialized.")

    # Initialize new game (map, dwarf, NPCs)
    stdscr.erase()
    stdscr.addstr(0, 0, "Growing a world...")
    stdscr.refresh()
    world_note = initialize_new_game(game_state)

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
    
    logging.info("--- Fungi Fortress Game Exiting --- Flushing logs.")
    logging.shutdown() # Ensure all logs are flushed
    
    # Return references for crash snapshot
    return game_logic, input_handler


def main():
    """Main entry point with error handling and crash logging."""
    # Store references for crash snapshot access
    game_logic_ref = None
    input_handler_ref = None
    
    def crash_wrapper(stdscr):
        """Wrapper that captures references for crash snapshots."""
        nonlocal game_logic_ref, input_handler_ref
        result = game_loop(stdscr)
        if result:
            game_logic_ref, input_handler_ref = result
        return result
    
    try:
        curses.wrapper(crash_wrapper)
    except Exception as e:
        # Ensure curses cleanup happens
        try:
            curses.endwin()
        except:
            pass
        
        # Write full traceback to crash log
        # Use FUNGI_LOG_DIR env var if set, otherwise ./logs in current working directory
        log_dir = os.environ.get("FUNGI_LOG_DIR", "logs")
        os.makedirs(log_dir, exist_ok=True)
        crash_log_path = os.path.join(log_dir, "fungi_crash.log")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamp_file = datetime.now().strftime("%Y%m%d-%H%M%S")
        tb_str = traceback.format_exc()
        
        # Write traceback log
        with open(crash_log_path, "a") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"CRASH at {timestamp}\n")
            f.write(f"{'='*80}\n")
            f.write(tb_str)
            f.write(f"\n{'='*80}\n\n")
        
        # Write crash state snapshot if available
        crash_state_path = None
        try:
            # Use direct references captured from game_loop
            snapshot_data = None
            
            if game_logic_ref and hasattr(game_logic_ref, 'penultimate_state_snapshot'):
                snapshot_data = game_logic_ref.penultimate_state_snapshot
            
            # If no penultimate snapshot (crash before first tick), capture current state
            if not snapshot_data and game_logic_ref:
                try:
                    snapshot_data = game_logic_ref._capture_state_snapshot()
                except:
                    pass  # Capture might fail if game state is incomplete
            
            # Always try to write snapshot if we have any data
            if snapshot_data or input_handler_ref:
                crash_state_path = os.path.join(log_dir, f"crash-{timestamp_file}.json")
                crash_data = {
                    "timestamp": timestamp,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "penultimate_state": snapshot_data if snapshot_data else {"note": "No snapshot available (crash before first tick)"},
                    "recent_keys": list(input_handler_ref.key_buffer) if input_handler_ref and hasattr(input_handler_ref, 'key_buffer') else []
                }
                
                with open(crash_state_path, "w") as f:
                    json.dump(crash_data, f, indent=2)
        except Exception as snapshot_error:
            # Don't let snapshot errors hide the original crash
            logging.error(f"Failed to write crash snapshot: {snapshot_error}")
            # Try to at least log the error details
            try:
                if not crash_state_path:
                    crash_state_path = os.path.join(log_dir, f"crash-{timestamp_file}.json")
                with open(crash_state_path, "w") as f:
                    json.dump({
                        "timestamp": timestamp,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "snapshot_error": str(snapshot_error)
                    }, f, indent=2)
            except:
                pass  # Give up on snapshot
        
        # Print error info to stderr after curses ends
        print(f"\n{'='*80}", file=sys.stderr)
        print(f"FATAL ERROR: {e}", file=sys.stderr)
        print(f"{'='*80}", file=sys.stderr)
        print(f"\nFull crash log written to: {crash_log_path}", file=sys.stderr)
        if crash_state_path:
            print(f"Crash state snapshot written to: {crash_state_path}", file=sys.stderr)
        print("\nLast traceback frames:", file=sys.stderr)
        print("".join(traceback.format_tb(sys.exc_info()[2])[-3:]), file=sys.stderr)
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        print(f"{'='*80}\n", file=sys.stderr)
        
        logging.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
