#!/usr/bin/env python3
"""Test various LLM response formats to identify the parsing bug."""

import json
from fungi_fortress.llm_world import _extract_json

# Test cases that might fail
test_cases = [
    # Case 1: Standard markdown fence with newlines (should work)
    (
        "```json\n{\"title\": \"Test\"}\n```",
        "Standard markdown fence with newlines"
    ),
    # Case 2: Markdown fence without newlines (likely fails!)
    (
        "```json{\"title\": \"Test\"}```",
        "Markdown fence WITHOUT newlines"
    ),
    # Case 3: Prose before JSON
    (
        "Here's your world:\n{\"title\": \"Test\"}",
        "Prose before JSON"
    ),
    # Case 4: Prose after JSON
    (
        "{\"title\": \"Test\"}\nThis is a great world!",
        "Prose after JSON"
    ),
    # Case 5: Both fence and prose
    (
        "Here's your world:\n```json\n{\"title\": \"Test\"}\n```\nEnjoy!",
        "Fence and prose"
    ),
    # Case 6: json language tag with capital letters
    (
        "```JSON\n{\"title\": \"Test\"}\n```",
        "JSON in capitals"
    ),
]

print("Testing JSON extraction with various formats...\n")

for i, (test_input, description) in enumerate(test_cases, 1):
    print(f"Test {i}: {description}")
    print(f"Input: {repr(test_input)}")
    try:
        result = _extract_json(test_input)
        print(f"✓ Success: {result}")
    except Exception as e:
        print(f"✗ FAILED: {type(e).__name__}: {e}")
    print()
