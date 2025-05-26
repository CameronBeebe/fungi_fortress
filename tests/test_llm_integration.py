import pytest
from unittest.mock import patch, MagicMock, call

# Use absolute imports for tests relative to the project root
from fungi_fortress.characters import Oracle, NPC, Task, Dwarf
from fungi_fortress.game_state import GameState, GameEvent, InteractionEventDetails
from fungi_fortress.game_logic import GameLogic
from fungi_fortress.input_handler import InputHandler
from fungi_fortress.tiles import Tile, ENTITY_REGISTRY
from fungi_fortress.entities import GameEntity
from fungi_fortress.config_manager import LLMConfig
from fungi_fortress import llm_interface # Import the module itself

# Minimal setup for testing
# Assume constants are available or mock them if needed
from fungi_fortress.constants import MAP_WIDTH, MAP_HEIGHT

# Mock ENTITY_REGISTRY for tests if necessary
# Mock some basic entities needed for tests
ENTITY_REGISTRY["grass"] = GameEntity("grass", ".", 2, True, False, True, "Grass")
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
            # Create a default LLMConfig for the fixture
            default_llm_config = LLMConfig(api_key="fixture_test_key", model_name="fixture_model", context_level="medium")
            gs = GameState(llm_config=default_llm_config)
            gs.dwarves = [Dwarf(1, 1, 0)] # Ensure at least one dwarf exists
            gs.characters = [] # Start with no characters unless added by test
            gs.event_queue = [] # Ensure empty event queue
            gs.tick = 100
            gs.depth = 5
            gs.player_resources = {"wood": 10, "stone": 5}
            gs.mission = {"description": "Test Mission Alpha", "objectives": ["Do something"], "rewards": [], "requirements": {}, "required_npcs": []}
            gs.oracle_llm_interaction_history = [
                {"player": "P_query_1", "oracle": "O_response_1"},
                {"player": "P_query_2", "oracle": "O_response_2"},
                {"player": "P_query_3", "oracle": "O_response_3"},
                {"player": "P_query_4", "oracle": "O_response_4"},
                {"player": "P_query_5", "oracle": "O_response_5"},
                {"player": "P_query_6", "oracle": "O_response_6"},
            ]
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

@pytest.mark.parametrize(
    "context_level, expected_history_len, expect_mission, expect_resources",
    [
        ("low", 1, False, False),
        ("medium", 3, True, False),
        ("high", 5, True, True),
    ]
)
@patch('fungi_fortress.llm_interface._call_llm_api')
def test_llm_prompt_context_levels(
    mock_call_llm_api: MagicMock,
    game_state_fixture: GameState,
    context_level: str,
    expected_history_len: int,
    expect_mission: bool,
    expect_resources: bool
):
    """Tests that the LLM prompt is constructed correctly based on context_level."""
    gs = game_state_fixture
    gs.llm_config.context_level = context_level

    test_player_query = "What is the meaning of this mushroom?"
    event_data: GameEvent = {
        "type": "ORACLE_QUERY",
        "tick": gs.tick,
        "details": {"query_text": test_player_query, "oracle_name": "Great Oracle"}
    }

    # Ensure game state has a mission and resources for high/medium checks if needed
    if not expect_mission:
        gs.mission = None # Explicitly set to None for low context if it shouldn't be there
    
    # Modify history for test predictability if expected_history_len is 0 (though current low is 1)
    # For this test, we assume oracle_llm_interaction_history is already populated in fixture
    # and slicing will handle it. If expected_history_len could be 0:
    # if expected_history_len == 0:
    #     gs.oracle_llm_interaction_history = []

    # Configure the mock to return a valid string response
    mock_call_llm_api.return_value = "The Oracle says... nothing much."

    llm_interface.handle_game_event(event_data, gs)

    mock_call_llm_api.assert_called_once()
    actual_prompt = mock_call_llm_api.call_args[0][0] # prompt is the first positional arg

    # Check for player query
    assert f"Player Query: {test_player_query}" in actual_prompt

    # Check for basic game context
    assert f"Tick: {gs.tick}" in actual_prompt
    assert f"Player depth: {gs.depth}" in actual_prompt

    # Check for mission
    if expect_mission and gs.mission:
        assert f"Mission: {gs.mission['description']}" in actual_prompt
    else:
        assert "Mission:" not in actual_prompt # Or check for a more specific absence if context string changes

    # Check for player resources
    if expect_resources:
        assert f"Player resources: {gs.player_resources}" in actual_prompt
    else:
        assert "Player resources:" not in actual_prompt
    
    # Check interaction history length
    # More specific counting:
    # Count the "Player Query:" line separately
    player_query_line_present = 1 if f"Player Query: {test_player_query}" in actual_prompt else 0
    
    # Count "Player: " from history (note the space for specificity against "Player Query")
    # To isolate history, we can roughly split the prompt
    history_segment = actual_prompt.split("Interaction History:\n")[1].split("\n\nPlayer Query:")[0]
    history_player_mentions = history_segment.count("Player: ") # Note space
    history_oracle_mentions = history_segment.count("Oracle: ") # Note space

    player_mentions_calculated = player_query_line_present + history_player_mentions
    oracle_mentions_calculated = history_oracle_mentions

    try:
        assert player_mentions_calculated == expected_history_len + 1
    except AssertionError as e:
        print(f"Prompt for {context_level} (player_mentions failed):\n--BEGIN PROMPT--\n{actual_prompt}\n--END PROMPT--")
        print(f"Analysis for {context_level}:")
        print(f"  player_query_line_present = {player_query_line_present}")
        print(f"  history_player_mentions = {history_player_mentions}")
        print(f"  player_mentions_calculated = {player_mentions_calculated}")
        print(f"  expected_history_len = {expected_history_len}")
        print(f"  expected total player_mentions = {expected_history_len + 1}")
        raise e
    try:
        assert oracle_mentions_calculated == expected_history_len
    except AssertionError as e:
        print(f"Prompt for {context_level} (oracle_mentions failed):\n--BEGIN PROMPT--\n{actual_prompt}\n--END PROMPT--")
        print(f"Analysis for {context_level}:")
        print(f"  history_oracle_mentions = {history_oracle_mentions}")
        print(f"  oracle_mentions_calculated = {oracle_mentions_calculated}")
        print(f"  expected_history_len = {expected_history_len}")
        raise e

    if expected_history_len == 0: # Though current low is 1
        assert "No interaction history provided for this query." in actual_prompt


# Ensure no if __name__ == "__main__" block here for pytest files normally 