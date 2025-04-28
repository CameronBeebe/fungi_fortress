import pytest
from unittest.mock import Mock, patch
import curses # Import curses for key codes

# Adjust imports based on your project structure
from fungi_fortress.game_state import GameState
from fungi_fortress.input_handler import InputHandler
from fungi_fortress.characters import Dwarf, Oracle, Task
from fungi_fortress.tiles import Tile, ENTITY_REGISTRY
from fungi_fortress.constants import MAP_WIDTH, MAP_HEIGHT
from fungi_fortress.game_logic import GameLogic

# Helper function to create a basic GameState with a dwarf and an oracle
def setup_game_state(dwarf_pos=(5, 5), oracle_pos=(6, 5)):
    gs = GameState()
    # Clear default dwarf/characters if necessary
    gs.dwarves = []
    gs.characters = []
    
    # Create a simple map (e.g., all grass)
    grass = ENTITY_REGISTRY.get("grass")
    gs.map = [[Tile(grass, x, y) for x in range(MAP_WIDTH)] for y in range(MAP_HEIGHT)]
    gs.main_map = gs.map # Ensure main_map is also set
    
    # Add dwarf
    if dwarf_pos:
        gs.dwarves.append(Dwarf(dwarf_pos[0], dwarf_pos[1], 0))
        gs.cursor_x, gs.cursor_y = dwarf_pos # Set cursor initially to dwarf pos

    # Add oracle
    if oracle_pos:
        gs.characters.append(Oracle("Whispering Fungus", oracle_pos[0], oracle_pos[1]))
    
    # Ensure task manager is initialized
    gs.task_manager.tasks = [] 
    
    # Reset relevant flags
    gs.show_oracle_dialog = False
    gs.paused = False
    return gs

# --- Input Handler Tests ---

def test_input_talk_assigns_task():
    """Test pressing 't' on Oracle assigns a 'talk' task."""
    gs = setup_game_state(dwarf_pos=(5, 5), oracle_pos=(6, 5))
    input_handler = InputHandler(gs)
    
    # Move cursor to Oracle
    gs.cursor_x, gs.cursor_y = 6, 5 
    
    # Simulate 't' press
    input_handler.handle_input(ord('t'))
    
    # Check if task manager has the talk task
    assert len(gs.task_manager.tasks) == 1
    task = gs.task_manager.tasks[0]
    assert task.type == 'talk'
    assert task.resource_x == 6 # Oracle X
    assert task.resource_y == 5 # Oracle Y
    # The dwarf should move to an adjacent tile, e.g., (5, 5)
    assert task.x == 5 
    assert task.y == 5

def test_input_talk_already_adjacent_assigns_task():
    """Test pressing 't' on Oracle when dwarf is adjacent assigns task."""
    # Dwarf at (5,5), Oracle at (6,5) - already adjacent
    gs = setup_game_state(dwarf_pos=(5, 5), oracle_pos=(6, 5)) 
    input_handler = InputHandler(gs)
    
    # Move cursor to Oracle
    gs.cursor_x, gs.cursor_y = 6, 5 
    
    # Simulate 't' press
    input_handler.handle_input(ord('t'))
    
    # Check task assignment
    assert len(gs.task_manager.tasks) == 1
    task = gs.task_manager.tasks[0]
    assert task.type == 'talk'
    assert task.resource_x == 6
    assert task.resource_y == 5
    assert task.x == 5 # Dwarf stays at (5,5)
    assert task.y == 5

def test_input_talk_no_oracle_at_cursor():
    """Test pressing 't' with cursor not on Oracle does nothing."""
    gs = setup_game_state(dwarf_pos=(5, 5), oracle_pos=(10, 10))
    input_handler = InputHandler(gs)
    
    # Cursor is somewhere else
    gs.cursor_x, gs.cursor_y = 7, 7 
    
    # Simulate 't' press
    input_handler.handle_input(ord('t'))
    
    # Check no task was assigned
    assert len(gs.task_manager.tasks) == 0

def test_input_close_dialog_t():
    """Test pressing 't' closes the Oracle dialog."""
    gs = setup_game_state()
    input_handler = InputHandler(gs)
    
    # Open the dialog
    gs.show_oracle_dialog = True
    gs.paused = True
    
    # Simulate 't' press
    input_handler.handle_input(ord('t'))
    
    # Check dialog is closed and game unpaused
    assert not gs.show_oracle_dialog
    assert not gs.paused

def test_input_close_dialog_q():
    """Test pressing 'q' closes the Oracle dialog."""
    gs = setup_game_state()
    input_handler = InputHandler(gs)
    
    gs.show_oracle_dialog = True
    gs.paused = True
    
    input_handler.handle_input(ord('q'))
    
    assert not gs.show_oracle_dialog
    assert not gs.paused

def test_input_other_keys_in_dialog():
    """Test other keys don't close the dialog."""
    gs = setup_game_state()
    input_handler = InputHandler(gs)
    
    gs.show_oracle_dialog = True
    gs.paused = True
    
    # Simulate another key press (e.g., 'm')
    input_handler.handle_input(ord('m'))
    
    # Check dialog is still open and paused
    assert gs.show_oracle_dialog
    assert gs.paused

# We might need more setup/mocking for a_star if it's complex or has side effects
# For now, assume a_star works correctly based on the simple map 

# --- Game Logic Tests ---

# Use patch to temporarily disable mission checks during these logic tests
@patch('fungi_fortress.game_logic.check_mission_completion', return_value=False)
@patch('fungi_fortress.game_logic.complete_mission') # Also patch complete_mission to avoid side effects
def test_logic_talk_triggers_dialog_after_move(mock_complete, mock_check):
    """Test dialogue opens after dwarf completes move for 'talk' task."""
    gs = setup_game_state(dwarf_pos=(1, 1), oracle_pos=(3, 1))
    # input_handler = InputHandler(gs) # Don't need input handler for this specific logic test
    game_logic = GameLogic(gs)
    dwarf = gs.dwarves[0]
    
    # Manually create and assign the task to the dwarf
    # Task: move to (2,1) to talk to Oracle at (3,1)
    talk_task = Task(x=2, y=1, type='talk', resource_x=3, resource_y=1) 
    dwarf.task = talk_task
    dwarf.state = 'moving'
    # Manually set path (assuming a_star would return this)
    dwarf.path = [(2, 1)] 
    dwarf.target_x, dwarf.target_y = 2, 1 # Set target for state machine
    dwarf.resource_x, dwarf.resource_y = 3, 1 # Set resource target

    # Initial state checks
    assert dwarf.task is not None 
    assert dwarf.task.type == 'talk'
    assert dwarf.state == 'moving'
    assert dwarf.x == 1 and dwarf.y == 1
    assert not gs.show_oracle_dialog
    assert not gs.paused
    
    # Simulate game tick for dwarf movement
    game_logic.update() # Tick 1: Dwarf should move from (1,1) to (2,1) and trigger talk
    
    # Check state AFTER movement tick
    assert dwarf.x == 2 and dwarf.y == 1 # Should be at destination now
    assert not dwarf.path # Path should be empty
    assert dwarf.state == 'idle' # Should become idle after talking
    assert dwarf.task is None # Task should be cleared after talking
    
    # Crucially, check if dialogue was triggered
    assert gs.show_oracle_dialog 
    assert gs.paused
    mock_check.assert_called() # Ensure the mock was used

@patch('fungi_fortress.game_logic.check_mission_completion', return_value=False)
@patch('fungi_fortress.game_logic.complete_mission')
def test_logic_talk_triggers_dialog_immediately_if_adjacent(mock_complete, mock_check):
    """Test dialogue opens immediately if dwarf is adjacent when task assigned."""
    gs = setup_game_state(dwarf_pos=(5, 5), oracle_pos=(6, 5))
    input_handler = InputHandler(gs)
    game_logic = GameLogic(gs)
    dwarf = gs.dwarves[0]
    
    # Assign task: Move cursor to Oracle (6,5) and press 't'
    gs.cursor_x, gs.cursor_y = 6, 5
    input_handler.handle_input(ord('t'))
    assert len(gs.task_manager.tasks) == 1
    
    # Update game logic ONCE - should assign task and trigger dialogue immediately
    game_logic.update()
    
    # Check state after the single update
    assert dwarf.x == 5 and dwarf.y == 5 # Still adjacent
    assert dwarf.state == 'idle' # Should be idle immediately
    assert dwarf.task is None # Task should be cleared immediately
    assert not gs.task_manager.tasks # Task manager should be empty
    
    # Dialogue should be triggered
    assert gs.show_oracle_dialog
    assert gs.paused
    mock_check.assert_called() # Ensure the mock was used

# --- Game State Tests --- (Could be in a separate file)

def test_game_state_oracle_flag_default():
    """Test that show_oracle_dialog defaults to False."""
    gs = GameState()
    # Need to handle potential map gen errors during init for a bare GS
    gs.map = [[Tile(ENTITY_REGISTRY["grass"], x, y) for x in range(MAP_WIDTH)] for y in range(MAP_HEIGHT)] 
    gs.main_map = gs.map
    # Minimal setup to avoid init errors
    gs.dwarves = []
    gs.characters = []
    gs.nexus_site = None
    gs.mycelial_network = {}
    gs.network_distances = {}
    gs.task_manager.tasks = []
    gs.debug_log = []
    gs._spawn_initial_oracle("TestOracle") # Ensure oracle spawn logic runs if needed

    assert hasattr(gs, 'show_oracle_dialog')
    assert gs.show_oracle_dialog == False 