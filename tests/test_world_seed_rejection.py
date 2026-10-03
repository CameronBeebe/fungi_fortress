"""Tests for world seed rejection logging and edge case handling."""

import json
import logging
from unittest.mock import Mock

import pytest

from fungi_fortress.llm_world import _extract_json
from fungi_fortress.world_seed import grow_world, parse_world_seed


def test_extract_json_with_markdown_fences():
    """Test JSON extraction with markdown code fences."""
    json_content = '{"title": "Test", "premise": "A test world"}'
    
    # Standard markdown fence with newlines
    result = _extract_json(f"```json\n{json_content}\n```")
    assert result == {"title": "Test", "premise": "A test world"}
    
    # Markdown fence without language tag
    result = _extract_json(f"```\n{json_content}\n```")
    assert result == {"title": "Test", "premise": "A test world"}
    
    # Markdown fence with uppercase JSON
    result = _extract_json(f"```JSON\n{json_content}\n```")
    assert result == {"title": "Test", "premise": "A test world"}


def test_extract_json_with_prose():
    """Test JSON extraction with explanatory text."""
    json_content = '{"title": "Test", "premise": "A test world"}'
    
    # Prose before JSON
    result = _extract_json(f"Here's your world seed:\n{json_content}")
    assert result == {"title": "Test", "premise": "A test world"}
    
    # Prose after JSON
    result = _extract_json(f"{json_content}\nThis is a great world!")
    assert result == {"title": "Test", "premise": "A test world"}
    
    # Both prose and markdown
    result = _extract_json(f"Here's your seed:\n```json\n{json_content}\n```\nEnjoy!")
    assert result == {"title": "Test", "premise": "A test world"}


def test_extract_json_rejects_invalid():
    """Test that extraction fails gracefully on invalid input."""
    with pytest.raises(ValueError, match="did not contain a JSON object"):
        _extract_json("No JSON here at all")
    
    with pytest.raises(ValueError, match="did not contain a JSON object"):
        _extract_json("```\nNo braces here\n```")


def test_parse_world_seed_accepts_string_counts():
    """Test that numeric strings in count fields are accepted and converted."""
    seed_data = {
        "title": "Test World",
        "premise": "A test premise",
        "characters": [
            {
                "id": "char1",
                "name": "Test Character",
                "description": "A test character",
                "kind": "revealed"
            }
        ],
        "places": [
            {
                "id": "place1",
                "name": "Test Place",
                "description": "A test place"
            }
        ],
        "quests": [
            {
                "id": "quest1",
                "title": "Test Quest",
                "summary": "A test quest",
                "giver_id": "char1",
                "requirements": [
                    {"kind": "collect", "resource": "fungi", "count": "8"}  # String count
                ]
            }
        ]
    }
    
    seed = parse_world_seed(seed_data)
    assert seed.quests[0].requirements[0].count == 8  # Converted to int
    assert isinstance(seed.quests[0].requirements[0].count, int)


def test_parse_world_seed_rejects_invalid_string_counts():
    """Test that non-numeric strings in count fields are rejected."""
    seed_data = {
        "title": "Test World",
        "premise": "A test premise",
        "characters": [
            {
                "id": "char1",
                "name": "Test Character",
                "description": "A test character",
                "kind": "revealed"
            }
        ],
        "places": [
            {
                "id": "place1",
                "name": "Test Place",
                "description": "A test place"
            }
        ],
        "quests": [
            {
                "id": "quest1",
                "title": "Test Quest",
                "summary": "A test quest",
                "giver_id": "char1",
                "requirements": [
                    {"kind": "collect", "resource": "fungi", "count": "many"}  # Invalid string
                ]
            }
        ]
    }
    
    with pytest.raises(ValueError, match="collect count must be an integer.*got string"):
        parse_world_seed(seed_data)


def test_grow_world_logs_rejection_warnings(caplog):
    """Test that world seed rejections are logged at WARNING level."""
    
    class MockGame:
        def __init__(self):
            self.map = [[Mock(walkable=True) for _ in range(5)] for _ in range(5)]
            self.dwarves = [Mock(x=0, y=0)]
            self.characters = []
            self.messages = []
        
        def get_tile(self, x, y):
            return self.map[y][x] if 0 <= y < len(self.map) and 0 <= x < len(self.map[0]) else None
        
        def add_debug_message(self, msg):
            self.messages.append(msg)
    
    game = MockGame()
    
    # Complete function that returns invalid JSON twice
    call_count = [0]
    
    def bad_complete(prompt):
        call_count[0] += 1
        # Return JSON with invalid resource name
        return json.dumps({
            "title": "Bad World",
            "premise": "This will fail",
            "characters": [{"id": "c1", "name": "Test", "description": "Test", "kind": "revealed"}],
            "places": [{"id": "p1", "name": "Place", "description": "Test"}],
            "quests": [{
                "id": "q1",
                "title": "Quest",
                "summary": "Test",
                "giver_id": "c1",
                "requirements": [{"kind": "collect", "resource": "invalid_resource", "count": 5}]
            }]
        })
    
    with caplog.at_level(logging.WARNING):
        result = grow_world(game, complete=bad_complete)
    
    # Should fall back to prepared seed
    assert "prepared grove" in result.lower()
    
    # Should have logged warnings for both attempts
    warning_logs = [rec for rec in caplog.records if rec.levelname == "WARNING"]
    assert len(warning_logs) == 2
    
    # Each warning should contain attempt number, exception type, and response preview
    for i, log in enumerate(warning_logs, 1):
        assert f"attempt {i}" in log.message.lower()
        assert "ValueError" in log.message
        assert "unknown resource" in log.message
        assert "Response preview:" in log.message
        assert '"title": "Bad World"' in log.message


def test_grow_world_logs_json_parse_errors(caplog):
    """Test that JSON parse errors are logged with response preview."""
    
    class MockGame:
        def __init__(self):
            self.map = [[Mock(walkable=True) for _ in range(5)] for _ in range(5)]
            self.dwarves = [Mock(x=0, y=0)]
            self.characters = []
            self.messages = []
        
        def get_tile(self, x, y):
            return self.map[y][x] if 0 <= y < len(self.map) and 0 <= x < len(self.map[0]) else None
        
        def add_debug_message(self, msg):
            self.messages.append(msg)
    
    game = MockGame()
    
    # Complete function that returns malformed JSON
    def bad_json_complete(prompt):
        return '{"title": "Test", invalid json here}'
    
    with caplog.at_level(logging.WARNING):
        result = grow_world(game, complete=bad_json_complete)
    
    # Should fall back to prepared seed
    assert "prepared grove" in result.lower()
    
    # Should have logged warnings for both attempts
    warning_logs = [rec for rec in caplog.records if rec.levelname == "WARNING"]
    assert len(warning_logs) == 2
    
    # Each warning should mention JSONDecodeError
    for log in warning_logs:
        assert "JSONDecodeError" in log.message
        assert "Response preview:" in log.message


def test_grow_world_succeeds_on_second_attempt(caplog):
    """Test that rejection feedback helps on retry."""
    
    class MockGame:
        def __init__(self):
            self.map = [[Mock(walkable=True) for _ in range(5)] for _ in range(5)]
            self.dwarves = [Mock(x=0, y=0)]
            self.characters = []
            self.messages = []
        
        def get_tile(self, x, y):
            return self.map[y][x] if 0 <= y < len(self.map) and 0 <= x < len(self.map[0]) else None
        
        def add_debug_message(self, msg):
            self.messages.append(msg)
    
    game = MockGame()
    
    # First call fails, second succeeds
    call_count = [0]
    
    def retry_complete(prompt):
        call_count[0] += 1
        if call_count[0] == 1:
            # First attempt: bad resource
            return json.dumps({
                "title": "Bad World",
                "premise": "This will fail",
                "characters": [{"id": "c1", "name": "Test", "description": "Test", "kind": "revealed"}],
                "places": [{"id": "p1", "name": "Place", "description": "Test"}],
                "quests": [{
                    "id": "q1",
                    "title": "Quest",
                    "summary": "Test",
                    "giver_id": "c1",
                    "requirements": [{"kind": "collect", "resource": "bad", "count": 5}]
                }]
            })
        else:
            # Second attempt: valid seed
            # Check that rejection reason is in the prompt
            assert "rejected" in prompt.lower()
            assert "unknown resource" in prompt.lower()
            return json.dumps({
                "title": "Good World",
                "premise": "This will work",
                "characters": [{"id": "c1", "name": "Test", "description": "Test", "kind": "revealed"}],
                "places": [{"id": "p1", "name": "Place", "description": "Test"}],
                "quests": [{
                    "id": "q1",
                    "title": "Quest",
                    "summary": "Test",
                    "giver_id": "c1",
                    "requirements": [{"kind": "collect", "resource": "fungi", "count": 5}]
                }]
            })
    
    with caplog.at_level(logging.WARNING):
        result = grow_world(game, complete=retry_complete)
    
    # Should succeed with the good world
    assert "Good World" in result
    
    # Should have logged only one warning (first attempt)
    warning_logs = [rec for rec in caplog.records if rec.levelname == "WARNING"]
    assert len(warning_logs) == 1
    assert "attempt 1" in warning_logs[0].message.lower()
