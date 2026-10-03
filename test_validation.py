#!/usr/bin/env python3
"""Test world seed validation with realistic LLM responses."""

import json
from fungi_fortress.world_seed import parse_world_seed
from fungi_fortress.llm_world import _extract_json

# Load the example seed as a baseline
with open("fungi_fortress/seeds/example_world.json") as f:
    valid_seed = json.load(f)

# Test cases that might fail validation
test_cases = []

# Case 1: Character with invalid kind (common LLM mistake)
bad_kind = json.loads(json.dumps(valid_seed))
bad_kind["characters"][0]["kind"] = "human"
test_cases.append(("Invalid character kind 'human'", bad_kind))

# Case 2: Missing kind field (should default to kin)
missing_kind = json.loads(json.dumps(valid_seed))
del missing_kind["characters"][0]["kind"]
test_cases.append(("Missing 'kind' field", missing_kind))

# Case 3: All characters are "kin" (should auto-promote last to revealed)
all_kin = json.loads(json.dumps(valid_seed))
for char in all_kin["characters"]:
    char["kind"] = "kin"
test_cases.append(("All characters are 'kin'", all_kin))

# Case 4: Multiple revealed characters (should auto-demote extras)
multi_revealed = json.loads(json.dumps(valid_seed))
for char in multi_revealed["characters"]:
    char["kind"] = "revealed"
test_cases.append(("Multiple 'revealed' characters", multi_revealed))

# Case 5: Invalid requirement kind
bad_req_kind = json.loads(json.dumps(valid_seed))
bad_req_kind["quests"][0]["requirements"][0]["kind"] = "fetch"
test_cases.append(("Invalid requirement kind 'fetch'", bad_req_kind))

# Case 6: Invalid resource name
bad_resource = json.loads(json.dumps(valid_seed))
bad_resource["quests"][0]["requirements"][0]["resource"] = "mushrooms"
test_cases.append(("Invalid resource 'mushrooms'", bad_resource))

# Case 7: Wrapped in markdown fences with explanatory text
wrapped = f"""Here's a world seed for Fungi Fortress:

```json
{json.dumps(valid_seed, indent=2)}
```

This should work nicely!"""
test_cases.append(("Wrapped in markdown with prose", wrapped))

# Case 8: Count as string instead of int (common LLM mistake)
count_str = json.loads(json.dumps(valid_seed))
count_str["quests"][0]["requirements"][0]["count"] = "8"
test_cases.append(("Count as string '8' instead of int", count_str))

print("Testing world seed validation...\n")

for description, test_input in test_cases:
    print(f"Test: {description}")
    try:
        # If test_input is a string, extract JSON first
        if isinstance(test_input, str):
            test_input = _extract_json(test_input)
        
        seed = parse_world_seed(test_input)
        print(f"✓ Success: {seed.title}")
        print(f"  Characters: {[c.name for c in seed.characters]}")
        print(f"  Kinds: {[c.kind for c in seed.characters]}")
    except Exception as e:
        print(f"✗ FAILED: {type(e).__name__}: {e}")
    print()
