"""Tests for world seed rejection logging."""

import json
import logging
from unittest.mock import Mock

from fungi_fortress.world_seed import grow_depth, grow_world


class MockGame:
    """Mock game object for testing."""
    def __init__(self):
        self.map = [[Mock(walkable=True) for _ in range(5)] for _ in range(5)]
        self.dwarves = [Mock(x=0, y=0)]
        self.characters = []
        self.messages = []
    
    def get_tile(self, x, y):
        if 0 <= y < len(self.map) and 0 <= x < len(self.map[0]):
            return self.map[y][x]
        return None
    
    def add_debug_message(self, msg):
        self.messages.append(msg)


def test_grow_world_logs_rejection_warnings(caplog):
    """Test that world seed rejections are logged at WARNING level."""
    game = MockGame()
    
    def bad_complete(prompt):
        # Return JSON with invalid giver_id (semantic error caught by parse_world_seed)
        return json.dumps({
            "title": "Bad World",
            "premise": "Test",
            "characters": [{"id": "c1", "name": "Test", "description": "Test", "kind": "revealed"}],
            "places": [{"id": "p1", "name": "Place", "description": "Test"}],
            "quests": [{
                "id": "q1", "title": "Quest", "summary": "Test", "giver_id": "invalid_id",
                "requirements": [{"kind": "reach", "place": "p1"}]
            }]
        })
    
    with caplog.at_level(logging.WARNING):
        result = grow_world(game, complete=bad_complete)
    
    assert "prepared grove" in result.lower()
    warning_logs = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warning_logs) == 2
    
    for i, log in enumerate(warning_logs, 1):
        assert f"attempt {i}" in log.message.lower()
        assert "ValueError" in log.message
        assert "Response preview:" in log.message
        # Verify preview is truncated to ~300 chars
        assert len(log.message.split("Response preview:")[-1]) <= 350


def test_grow_depth_logs_rejection_warnings(caplog):
    """Test that depth seed rejections are also logged."""
    game = MockGame()
    
    def bad_complete(prompt):
        # Missing at least one quest
        return json.dumps({"title": "Bad", "premise": "Test", "characters": [], "places": [], "quests": []})
    
    with caplog.at_level(logging.WARNING):
        result = grow_depth(game, complete=bad_complete)
    
    assert "prepared depth" in result.lower()
    warning_logs = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warning_logs) == 2
    
    for log in warning_logs:
        assert "rejected" in log.message.lower()
        assert "ValueError" in log.message
        assert "Response preview:" in log.message


def test_grow_world_logs_json_parse_errors(caplog):
    """Test that JSON parse errors are logged with response preview."""
    game = MockGame()
    
    def bad_json_complete(prompt):
        return '{"title": "Test", invalid json here}'
    
    with caplog.at_level(logging.WARNING):
        result = grow_world(game, complete=bad_json_complete)
    
    assert "prepared grove" in result.lower()
    warning_logs = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warning_logs) == 2
    
    for log in warning_logs:
        # Pydantic wraps JSON errors as ValidationError
        assert "ValidationError" in log.message
        assert "Response preview:" in log.message

