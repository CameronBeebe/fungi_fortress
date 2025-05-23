import pytest
from unittest.mock import patch, MagicMock, call

# Use absolute imports for tests relative to the project root
from fungi_fortress.characters import Oracle, NPC, Task, Dwarf
from fungi_fortress.game_state import GameState, GameEvent, InteractionEventDetails
from fungi_fortress.game_logic import GameLogic
from fungi_fortress.input_handler import InputHandler
from fungi_fortress.tiles import Tile, ENTITY_REGISTRY
from fungi_fortress.entities import GameEntity
from fungi_fortress.config_manager import OracleConfig
from fungi_fortress import llm_interface # Import the module itself

# Minimal setup for testing
# Assume constants are available or mock them if needed
from fungi_fortress.constants import MAP_WIDTH, MAP_HEIGHT

# Mock ENTITY_REGISTRY for tests if necessary
# Mock some basic entities needed for tests
# ENTITY_REGISTRY["grass"] = GameEntity("grass", ".", 2, True, False, True, "Grass")
# ENTITY_REGISTRY["stone_floor"] = GameEntity("stone_floor", ".", 7, True, False, True, "Stone Floor")


@pytest.fixture
def game_state_fixture() -> GameState:
    """Provides a basic GameState instance for testing."""
    # Patch generate_map to avoid complex map generation during test setup
    with patch('fungi_fortress.game_state.generate_map') as mock_gen_map:
        # Return a simple walkable map
        dummy_map = [[Tile(ENTITY_REGISTRY['grass'], x, y) for x in range(MAP_WIDTH)] for y in range(MAP_HEIGHT)]
        mock_gen_map.return_value = (dummy_map, (MAP_WIDTH // 2, MAP_HEIGHT // 2), []) # Map, nexus_site, fungi_locs
        
        # Patch network generation as well
        with patch('fungi_fortress.game_state.generate_mycelial_network') as mock_gen_net:
            mock_gen_net.return_value = {} # Empty network
            # Create a default OracleConfig for the fixture
            default_oracle_config = OracleConfig(api_key="fixture_test_key", model_name="fixture_model", context_level="medium")
            gs = GameState(oracle_config=default_oracle_config)
            gs.dwarves = [Dwarf(1, 1, 0)] # Ensure at least one dwarf exists
            gs.characters = [] # Start with no characters unless added by test
            gs.event_queue = [] # Ensure empty event queue
            gs.tick = 0
            gs.depth = 0 # Ensure starting at surface for relevant tests
            # Ensure map is the dummy map
            gs.map = dummy_map 
            gs.main_map = dummy_map
            gs._spawn_initial_oracle = MagicMock() # Prevent automatic oracle spawn in fixture
            return gs

def test_oracle_class_exists():
    """Tests that the Oracle class exists and inherits from NPC."""
    oracle = Oracle("Test Oracle", 10, 10)
    assert isinstance(oracle, Oracle)
    assert isinstance(oracle, NPC)
    assert oracle.name == "Test Oracle"
    assert oracle.x == 10
    assert oracle.y == 10

def test_oracle_interaction_triggers_event(game_state_fixture: GameState):
    """Tests that interacting with an Oracle using 'e' adds an event."""
    gs = game_state_fixture
    oracle_x, oracle_y = 5, 5
    oracle_name = "Test Oracle"
    oracle = Oracle(oracle_name, oracle_x, oracle_y)
    gs.characters.append(oracle)
    
    # Ensure the tile the oracle is on is known (though interaction checks adjacency)
    # gs.map[oracle_y][oracle_x] = Tile(...) # Might not be needed if only adjacency matters

    input_handler = InputHandler(gs)

    # Position cursor adjacent to the Oracle
    gs.cursor_x = oracle_x + 1
    gs.cursor_y = oracle_y

    # Simulate 'e' key press
    input_handler.handle_input(ord('e'))

    # Assert event queue has one event
    assert len(gs.event_queue) == 1
    
    event = gs.event_queue[0]
    assert event["type"] == "interaction"
    details = event["details"]
    assert details["actor_id"] == "player"
    assert details["target_type"] == "Oracle"
    assert details["target_id"] == oracle_name
    assert details["location"] == (oracle_x, oracle_y)


# Patch the target function within the module where it's LOOKED UP
@patch('fungi_fortress.game_logic.llm_interface.handle_game_event') 
def test_game_logic_consumes_events_and_calls_interface(mock_handle_event, game_state_fixture: GameState):
    """Tests that GameLogic.update consumes events and calls the LLM interface handler."""
    gs = game_state_fixture
    
    # Add a dummy event to the queue
    dummy_event: GameEvent = {
        "type": "ORACLE_QUERY",
        "tick": 0,
        "details": {"query_text": "Test query", "oracle_name": "Test Oracle"}
    }
    gs.event_queue.append(dummy_event)
    
    # Set the mock return value (optional, default is None)
    mock_handle_event.return_value = None 
    
    game_logic = GameLogic(gs)
    
    # Run a game logic update tick
    game_logic.update()
    
    # Assert the event queue is now empty
    assert len(gs.event_queue) == 0
    
    # Assert the mock handler was called once with the dummy event and game_state
    mock_handle_event.assert_called_once_with(dummy_event, gs)
    
    # Test case where LLM returns actions (optional)
    mock_handle_event.reset_mock()
    dummy_event_2: GameEvent = {"type": "ORACLE_QUERY", "tick": 1, "details": {"query_text": "Another query"}}
    dummy_action = {"action_type": "add_message", "details": {"text": "LLM says hi!"}}
    gs.event_queue.append(dummy_event_2)
    mock_handle_event.return_value = [dummy_action]
    
    # Patch GameState.add_debug_message to check for the processed action message
    with patch.object(gs, 'add_debug_message') as mock_add_debug_message:
         game_logic.update()
         mock_handle_event.assert_called_once_with(dummy_event_2, gs)
         # Check if the specific message for the processed action was logged
         expected_log_message = f"LLM: {dummy_action['details']['text']}"
         # Also check the generic processing message
         generic_processing_message = f"[GameLogic] Processing Action: {dummy_action['action_type']} - Details: {dummy_action['details']}"
         
         # Check if both messages were called
         calls = [call(generic_processing_message), call(expected_log_message)]
         mock_add_debug_message.assert_has_calls(calls, any_order=True)

# Ensure no if __name__ == "__main__" block here for pytest files normally 