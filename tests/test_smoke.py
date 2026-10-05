"""End-to-end smoke test with real code paths and faked network.

Verifies core gameplay works with XAI provider (not mock) by monkeypatching
openai.OpenAI to return canned responses. Tests both streaming Oracle dialogue
and world generation paths.
"""
import pytest
from unittest.mock import MagicMock, Mock
from fungi_fortress.config_manager import LLMConfig
from fungi_fortress.game_state import GameState
from fungi_fortress.game_logic import GameLogic
from fungi_fortress import world_seed


class FakeStreamChunk:
    """Mock streaming response chunk."""
    def __init__(self, content):
        self.choices = [Mock()]
        self.choices[0].delta = Mock()
        self.choices[0].delta.content = content


class FakeOpenAIClient:
    """Fake OpenAI client that returns canned responses."""
    
    def __init__(self, *args, **kwargs):
        self.chat = Mock()
        self.chat.completions = Mock()
        self.chat.completions.create = self._create_completion
        self.call_log = []  # Track all calls for assertions
    
    def _create_completion(self, **kwargs):
        """Return streamed chunks or JSON body based on stream param."""
        # Log this call
        self.call_log.append(kwargs)
        
        if kwargs.get('stream'):
            # Streaming response: yield chunks with unique phrase
            narrative = "The ancient mycelium speaks of hidden paths and forgotten spores."
            chunks = [FakeStreamChunk(word + " ") for word in narrative.split()]
            return iter(chunks)
        else:
            # Non-streaming JSON response
            response = Mock()
            response.choices = [Mock()]
            response.choices[0].message = Mock()
            
            # Check if response_format indicates structured output (world gen)
            if 'response_format' in kwargs:
                # World generation structured response matching WorldSeedSchema
                response.choices[0].message.content = '''{
                    "title": "The Shadowed Grove",
                    "premise": "A dark forest where corrupted spores threaten the realm",
                    "characters": [
                        {
                            "id": "elder_sage",
                            "name": "Elder Sage",
                            "description": "An ancient oracle who speaks in riddles",
                            "kind": "revealed",
                            "motive": "Guide seekers to truth",
                            "secret": "Knows the source of corruption"
                        }
                    ],
                    "places": [
                        {
                            "id": "corrupted_glade",
                            "name": "Corrupted Glade",
                            "description": "A dark clearing where corrupted spores grow",
                            "kind": "grove"
                        }
                    ],
                    "quests": [
                        {
                            "id": "cleanse_corruption",
                            "title": "Cleanse the Grove",
                            "summary": "Remove corruption from Shadowgrove",
                            "description": "The grove has been tainted by dark spores",
                            "giver_id": "elder_sage",
                            "requirements": [
                                {"kind": "collect", "resource": "fungi", "count": 3}
                            ]
                        }
                    ]
                }'''
            else:
                # Regular Oracle response
                response.choices[0].message.content = '{"narrative": "The spores whisper ancient wisdom.", "actions": []}'
            
            return response


@pytest.fixture
def fake_openai(monkeypatch):
    """Monkeypatch openai.OpenAI to use fake client."""
    import openai
    fake_instance = None
    
    def create_fake(*args, **kwargs):
        nonlocal fake_instance
        fake_instance = FakeOpenAIClient(*args, **kwargs)
        return fake_instance
    
    monkeypatch.setattr('openai.OpenAI', create_fake)
    
    class FakeHolder:
        @property
        def instance(self):
            return fake_instance
    
    return FakeHolder()


def test_end_to_end_oracle_and_world_with_faked_network(fake_openai):
    """Smoke test: Oracle dialogue and world gen work with real code paths.
    
    Uses a fake API key to trigger XAI provider (not mock), monkeypatches
    openai.OpenAI to return canned responses. Verifies:
    1. Oracle streaming dialogue appears in game
    2. World generation produces a seed
    
    No assertions about exact prompts or params - just that the paths work.
    """
    # === Part 1: Oracle dialogue through normal gameplay ===
    
    # Set up config with fake real-looking key (triggers XAI provider)
    llm_config = LLMConfig(
        api_key="xai-test-key-1234567890abcdef",  # Fake but real-looking
        model_name="grok-4.3",
        reasoning_effort="low",
        temperature=0.7,
        context_level="medium"
    )
    
    # Create game state and logic (normal gameplay initialization)
    game_state = GameState(llm_config=llm_config)
    game_logic = GameLogic(game_state)
    
    # Verify we're using XAI provider, not mock
    assert not game_state.llm_config.create_llm_client().is_mock(), \
        "Should use XAI provider with fake key, not mock"
    
    # Open Oracle dialogue (normal player action)
    game_state.show_oracle_dialog = True
    game_state.oracle_interaction_state = "AWAITING_PROMPT"
    
    # Submit Oracle query through normal event queue (how the game works)
    game_state.add_event("ORACLE_QUERY", {
        "query_text": "What should I do?",
        "oracle_name": "The Oracle"
    })
    
    # Process first update to start streaming
    game_logic.update()
    
    # Process game updates to complete streaming (normal game loop)
    max_ticks = 2000
    for tick in range(max_ticks):
        game_logic.update()
        # Check if streaming completed
        if game_state.oracle_interaction_state == "AWAITING_PROMPT":
            break
    else:
        pytest.fail(f"Oracle dialogue did not complete within {max_ticks} ticks")
    
    # Assert real Oracle dialogue appeared with unique phrase from fake
    dialogue_text = "\n".join(
        line[0] if isinstance(line, tuple) else str(line)
        for line in game_state.oracle_current_dialogue
    )
    
    assert dialogue_text, "Oracle dialogue should not be empty"
    # Check for unique phrase from fake response (not random flavor text)
    assert "hidden paths and forgotten" in dialogue_text, \
        f"Should contain exact fake narrative phrase, got: {dialogue_text[:200]}"
    # Verify not error messages
    assert "connection is disrupted" not in dialogue_text.lower(), \
        "Should not show real connection error"
    assert "unclear" not in dialogue_text.lower(), \
        "Should not show mock fallback response"
    
    # Verify history was updated
    assert len(game_state.oracle_llm_interaction_history) > 0, \
        "Oracle interaction should be recorded in history"
    
    # Assert exactly one streaming request reached the fake client
    fake_client = fake_openai.instance
    assert fake_client is not None, "Fake client should have been created"
    streaming_calls = [call for call in fake_client.call_log if call.get('stream')]
    assert len(streaming_calls) == 1, \
        f"Expected exactly 1 streaming call, got {len(streaming_calls)}"
    
    # === Part 2: World generation (if cheap enough) ===
    
    # Create a new game state for world gen
    world_game = GameState(llm_config=llm_config)
    initial_mission = world_game.mission["description"]
    initial_chars = len(world_game.characters)
    
    # Run world generation through normal path
    result_message = world_seed.grow_world(world_game, complete=None)
    
    # Assert world was generated (not fallback)
    assert "prepared grove" not in result_message.lower(), \
        "Should generate world via LLM, not use fallback"
    
    # Check that world content was applied (mission changed, characters added)
    assert world_game.mission["description"] != initial_mission, \
        "World generation should update mission"
    assert len(world_game.characters) > initial_chars, \
        "World generation should add characters"
    
    print(f"✓ End-to-end smoke test passed:")
    print(f"  - Oracle dialogue: {len(game_state.oracle_llm_interaction_history)} interaction(s)")
    print(f"  - World generated: mission updated, {len(world_game.characters) - initial_chars} chars added")
