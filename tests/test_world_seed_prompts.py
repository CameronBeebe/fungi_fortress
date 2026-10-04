"""Tests for world seed prompt validation and dict logging."""

import json
import logging
from unittest.mock import Mock

from fungi_fortress.world_seed import _depth_prompt, _seed_prompt, grow_world


def test_prompts_name_all_required_keys():
    """Both prompts must explicitly name all required top-level keys."""
    # Keys that parse_world_seed requires at top level
    required_keys = ["title", "premise", "characters", "places", "quests"]
    
    world_prompt = _seed_prompt()
    depth_prompt = _depth_prompt()
    
    for key in required_keys:
        assert key in world_prompt, f"World prompt missing required key: {key}"
        assert key in depth_prompt, f"Depth prompt missing required key: {key}"
    
    # Both should explicitly say "top-level keys"
    assert "top-level keys" in world_prompt
    assert "top-level keys" in depth_prompt


def test_dict_reply_missing_title_logs_preview(caplog):
    """Dict reply missing title logs a preview showing the dict's keys."""
    
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
    
    def dict_missing_title(prompt):
        # Return dict with all keys except title
        return {
            "premise": "Test world",
            "characters": [{"id": "c1", "name": "Test", "description": "Test", "kind": "revealed"}],
            "places": [{"id": "p1", "name": "Place", "description": "Test"}],
            "quests": [{
                "id": "q1", "title": "Quest", "summary": "Test", "giver_id": "c1",
                "requirements": [{"kind": "collect", "resource": "fungi", "count": 5}]
            }]
        }
    
    with caplog.at_level(logging.WARNING):
        result = grow_world(game, complete=dict_missing_title)
    
    # Should fall back to prepared seed
    assert "prepared grove" in result.lower()
    
    # Should have logged warnings
    warning_logs = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warning_logs) > 0
    
    # First warning should contain title error and dict preview
    log_message = warning_logs[0].message
    assert "title is required" in log_message
    assert "Response preview:" in log_message
    
    # Preview should show the dict structure with keys present
    assert '"premise"' in log_message or "'premise'" in log_message
    assert '"characters"' in log_message or "'characters'" in log_message
