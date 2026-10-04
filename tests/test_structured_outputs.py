"""Tests for structured LLM outputs with validation and retry."""

import json
import pytest
from unittest.mock import Mock, patch

from fungi_fortress import llm_client
from fungi_fortress.world_seed import (
    WorldSeedSchema,
    CharacterSchema,
    PlaceSchema,
    QuestSchema,
    CollectRequirement,
    ReachRequirement,
    CharacterKind,
    ResourceEnum,
    _validate_world_seed_schema,
    _world_seed_schema_to_dict,
    grow_world,
)


def test_schema_includes_required_keys():
    """Verify that the generated schema includes required top-level keys."""
    # Generate schema from Pydantic model
    schema_dict = llm_client._schema_from_model(WorldSeedSchema, "test_schema")
    
    assert "json_schema" in schema_dict
    json_schema = schema_dict["json_schema"]
    assert json_schema["name"] == "test_schema"
    assert json_schema["strict"] is True
    
    # Check the schema structure
    schema = json_schema["schema"]
    assert "properties" in schema
    assert "required" in schema
    
    # Verify required top-level keys
    required = schema["required"]
    assert "title" in required
    assert "premise" in required
    assert "characters" in required
    assert "places" in required
    assert "quests" in required


def test_cross_reference_validation_triggers_retry():
    """Verify that a cross-reference violation triggers retry with error text."""
    # Create a mock client that returns invalid then valid responses
    mock_client = Mock(spec=llm_client.LLMClient)
    
    # First response: invalid giver_id
    invalid_seed = {
        "title": "Test World",
        "premise": "A test premise",
        "characters": [
            {
                "id": "char1",
                "name": "Character 1",
                "description": "First character",
                "kind": "revealed"
            }
        ],
        "places": [
            {"id": "place1", "name": "Place 1", "description": "A place"}
        ],
        "quests": [
            {
                "id": "quest1",
                "title": "Test Quest",
                "summary": "A test quest",
                "giver_id": "nonexistent_char",  # Invalid reference
                "requirements": [
                    {"kind": "reach", "place": "place1"}
                ],
                "success": ""
            }
        ]
    }
    
    # Second response: valid
    valid_seed = {
        "title": "Test World",
        "premise": "A test premise",
        "characters": [
            {
                "id": "char1",
                "name": "Character 1",
                "description": "First character",
                "kind": "revealed"
            }
        ],
        "places": [
            {"id": "place1", "name": "Place 1", "description": "A place"}
        ],
        "quests": [
            {
                "id": "quest1",
                "title": "Test Quest",
                "summary": "A test quest",
                "giver_id": "char1",  # Valid reference
                "requirements": [
                    {"kind": "reach", "place": "place1"}
                ],
                "success": ""
            }
        ]
    }
    
    # Mock returns invalid then valid JSON
    mock_client.chat.side_effect = [
        json.dumps(invalid_seed),
        json.dumps(valid_seed)
    ]
    
    # Call structured_call
    messages = [{"role": "user", "content": "Generate a world"}]
    result = llm_client.structured_call(
        mock_client,
        messages,
        WorldSeedSchema,
        validate=_validate_world_seed_schema,
        attempts=2
    )
    
    # Should succeed on second attempt
    assert result is not None
    assert result.title == "Test World"
    assert result.quests[0].giver_id == "char1"
    
    # Verify retry was called with error in conversation
    assert mock_client.chat.call_count == 2
    second_call_messages = mock_client.chat.call_args_list[1][0][0]
    
    # Check that error was appended to conversation
    assert len(second_call_messages) > len(messages)
    error_message = second_call_messages[-1]["content"]
    assert "rejected" in error_message.lower()
    assert "nonexistent_char" in error_message or "giver" in error_message.lower()


def test_final_failure_returns_none():
    """Verify that after all attempts fail, None is returned."""
    # Create a mock client that always returns invalid responses
    mock_client = Mock(spec=llm_client.LLMClient)
    
    # Always return invalid seed (missing title)
    invalid_seed = {
        "premise": "A test premise",
        "characters": [],
        "places": [],
        "quests": []
    }
    
    mock_client.chat.return_value = json.dumps(invalid_seed)
    
    # Call structured_call with 2 attempts
    messages = [{"role": "user", "content": "Generate a world"}]
    result = llm_client.structured_call(
        mock_client,
        messages,
        WorldSeedSchema,
        validate=_validate_world_seed_schema,
        attempts=2
    )
    
    # Should return None after all attempts fail
    assert result is None
    assert mock_client.chat.call_count == 2


def test_mock_provider_validates_schema():
    """Verify that the mock provider validates responses against schema."""
    # Create a mock provider
    provider = llm_client.MockLLMProvider()
    
    # Create a response format with required fields
    response_format = {
        "json_schema": {
            "schema": {
                "required": ["narrative", "actions"]
            }
        }
    }
    
    # Valid response should work
    messages = [{"role": "user", "content": "hello"}]
    response = provider.chat(messages, response_format=response_format)
    data = json.loads(response)
    assert "narrative" in data
    assert "actions" in data


def test_grow_world_fallback_on_failure():
    """Verify that grow_world falls back to prepared seed on failure."""
    # Create a mock game object
    game = Mock()
    game.llm_config = None
    
    # Mock the _get_llm_client to return a client that returns invalid responses
    with patch("fungi_fortress.world_seed._get_llm_client") as mock_get_client:
        mock_client = Mock(spec=llm_client.LLMClient)
        # Return invalid JSON that will fail schema validation
        invalid_response = json.dumps({"title": "Test"})  # Missing required fields
        mock_client.chat.return_value = invalid_response
        mock_get_client.return_value = mock_client
        
        # Mock the prepared seed loading
        with patch("fungi_fortress.world_seed._install_prepared") as mock_install:
            result = grow_world(game)
            
            # Should fall back to prepared seed
            assert "unusable" in result.lower() or "prepared" in result.lower()
            mock_install.assert_called_once()


def test_validator_catches_duplicate_ids():
    """Verify validator catches duplicate character IDs."""
    seed = WorldSeedSchema(
        title="Test",
        premise="Test premise",
        characters=[
            CharacterSchema(
                id="char1",
                name="Char 1",
                description="First",
                kind=CharacterKind.kin
            ),
            CharacterSchema(
                id="char1",  # Duplicate ID
                name="Char 2",
                description="Second",
                kind=CharacterKind.revealed
            )
        ],
        places=[PlaceSchema(id="place1", name="Place 1", description="A place")],
        quests=[
            QuestSchema(
                id="quest1",
                title="Quest",
                summary="A quest",
                giver_id="char1",
                requirements=[ReachRequirement(kind="reach", place="place1")]
            )
        ]
    )
    
    errors = _validate_world_seed_schema(seed)
    assert len(errors) > 0
    assert any("duplicate" in e.lower() and "character" in e.lower() for e in errors)


def test_validator_requires_exactly_one_revealed():
    """Verify validator requires exactly one revealed character."""
    # No revealed characters
    seed = WorldSeedSchema(
        title="Test",
        premise="Test premise",
        characters=[
            CharacterSchema(
                id="char1",
                name="Char 1",
                description="First",
                kind=CharacterKind.kin
            )
        ],
        places=[PlaceSchema(id="place1", name="Place 1", description="A place")],
        quests=[
            QuestSchema(
                id="quest1",
                title="Quest",
                summary="A quest",
                giver_id="char1",
                requirements=[ReachRequirement(kind="reach", place="place1")]
            )
        ]
    )
    
    errors = _validate_world_seed_schema(seed)
    assert len(errors) > 0
    assert any("revealed" in e.lower() for e in errors)


def test_schema_to_dict_conversion():
    """Verify schema-to-dict conversion preserves data correctly."""
    seed = WorldSeedSchema(
        title="Test World",
        premise="A test premise",
        characters=[
            CharacterSchema(
                id="char1",
                name="Character 1",
                description="First character",
                kind=CharacterKind.revealed,
                faction="Faction A"
            )
        ],
        places=[PlaceSchema(id="place1", name="Place 1", description="A place")],
        quests=[
            QuestSchema(
                id="quest1",
                title="Test Quest",
                summary="A test quest",
                giver_id="char1",
                requirements=[
                    CollectRequirement(kind="collect", resource=ResourceEnum.fungi, count=5),
                    ReachRequirement(kind="reach", place="place1")
                ],
                success="Quest completed"
            )
        ]
    )
    
    result = _world_seed_schema_to_dict(seed)
    
    assert result["title"] == "Test World"
    assert result["premise"] == "A test premise"
    assert len(result["characters"]) == 1
    assert result["characters"][0]["id"] == "char1"
    assert result["characters"][0]["kind"] == "revealed"
    assert len(result["quests"]) == 1
    assert len(result["quests"][0]["requirements"]) == 2
    assert result["quests"][0]["requirements"][0]["kind"] == "collect"
    assert result["quests"][0]["requirements"][0]["resource"] == "fungi"
    assert result["quests"][0]["requirements"][1]["kind"] == "reach"
