"""Tests for structured LLM outputs with validation and retry."""

import json
from unittest.mock import Mock

from fungi_fortress import llm_client
from fungi_fortress.world_seed import WorldSeedSchema


def test_schema_contains_required_keys():
    """Verify response_format contains schema with required top-level keys."""
    schema_dict = llm_client._schema_from_model(WorldSeedSchema, "test")
    
    json_schema = schema_dict["json_schema"]
    assert json_schema["strict"] is True
    
    required = json_schema["schema"]["required"]
    assert "title" in required
    assert "premise" in required
    assert "characters" in required
    assert "places" in required
    assert "quests" in required


def test_semantic_failure_triggers_retry_with_error():
    """Verify semantic validation failure triggers retry with error text in messages."""
    from fungi_fortress.config_manager import LLMConfig
    
    mock_client = Mock(spec=llm_client.LLMClient)
    mock_client.config = LLMConfig()
    
    call_count = [0]
    
    def mock_chat(messages, **kwargs):
        call_count[0] += 1
        
        # First call: invalid giver_id (semantic error)
        if call_count[0] == 1:
            return json.dumps({
                "title": "Test",
                "premise": "Premise",
                "characters": [{"id": "c1", "name": "C1", "description": "Desc", "kind": "revealed"}],
                "places": [{"id": "p1", "name": "P1", "description": "Desc"}],
                "quests": [{
                    "id": "q1",
                    "title": "Quest",
                    "summary": "Summary",
                    "giver_id": "bad_id",
                    "requirements": [{"kind": "reach", "place": "p1"}]
                }]
            })
        # Second call: valid
        else:
            return json.dumps({
                "title": "Test",
                "premise": "Premise",
                "characters": [{"id": "c1", "name": "C1", "description": "Desc", "kind": "revealed"}],
                "places": [{"id": "p1", "name": "P1", "description": "Desc"}],
                "quests": [{
                    "id": "q1",
                    "title": "Quest",
                    "summary": "Summary",
                    "giver_id": "c1",
                    "requirements": [{"kind": "reach", "place": "p1"}]
                }]
            })
    
    mock_client.chat = Mock(side_effect=mock_chat)
    
    def converter(schema):
        # Simulate parse_world_seed validation
        data = schema.model_dump(mode="json")
        if data["quests"][0]["giver_id"] not in [c["id"] for c in data["characters"]]:
            raise ValueError(f"giver_id {data['quests'][0]['giver_id']} not found")
        return data
    
    result = llm_client.structured_call(
        mock_client,
        [{"role": "user", "content": "Generate"}],
        WorldSeedSchema,
        convert=converter,
    )
    
    assert result is not None
    assert result["quests"][0]["giver_id"] == "c1"
    assert mock_client.chat.call_count == 2
    
    # Check retry included error
    retry_messages = mock_client.chat.call_args_list[1][0][0]
    assert any("rejected" in str(m.get("content", "")).lower() for m in retry_messages)


def test_final_failure_returns_none_and_logs_warning(caplog):
    """Verify final failure returns None and logs WARNING with preview."""
    import logging
    from fungi_fortress.config_manager import LLMConfig
    
    mock_client = Mock(spec=llm_client.LLMClient)
    mock_client.config = LLMConfig()
    mock_client.chat.return_value = json.dumps({"title": "Bad"})  # Missing fields
    
    with caplog.at_level(logging.WARNING):
        result = llm_client.structured_call(
            mock_client,
            [{"role": "user", "content": "Generate"}],
            WorldSeedSchema,
        )
    
    assert result is None
    assert mock_client.chat.call_count == 3  # max_validation_retries=2 means 3 total attempts
    
    # Check warning was logged
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) > 0
    assert "rejected" in warnings[0].message.lower()
