#!/usr/bin/env python3
"""
Direct test of XAI API integration to diagnose grok-3-mini response issues.
"""

import os
import pytest # For skipping test if API key is not found
from openai import OpenAI

def test_xai_direct():
    """Test XAI API directly using the example format from XAI website."""
    
    api_key = os.environ.get("XAI_API_KEY")
    
    if not api_key:
        pytest.skip("XAI_API_KEY not found in environment variables. Skipping live test.")
    
    print(f"Using API key from environment: {api_key[:10]}...")
    
    # Test messages following XAI example
    messages = [
        {
            "role": "system",
            "content": "You are a highly intelligent AI assistant and mystical Oracle in a fantasy game.",
        },
        {
            "role": "user",
            "content": "What is the meaning of this mysterious mushroom I found?",
        },
    ]

    client = OpenAI(
        base_url="https://api.x.ai/v1",
        api_key=api_key,
    )

    try:
        print("Making XAI API call...")
        completion = client.chat.completions.create(
            model="grok-3-mini", 
            reasoning_effort="high",
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
        )

        print("\n=== API RESPONSE ===")
        
        message = completion.choices[0].message
        
        if hasattr(message, 'reasoning_content') and message.reasoning_content:
            print("Reasoning Content:")
            print(message.reasoning_content)
        else:
            print("No reasoning content found")

        print("\nFinal Response:")
        print(message.content)

        if completion.usage:
            print(f"\nCompletion tokens: {completion.usage.completion_tokens}")
            if hasattr(completion.usage, 'completion_tokens_details') and completion.usage.completion_tokens_details:
                if hasattr(completion.usage.completion_tokens_details, 'reasoning_tokens'):
                    print(f"Reasoning tokens: {completion.usage.completion_tokens_details.reasoning_tokens}")
        
        print("\n=== RAW COMPLETION OBJECT ===")
        print(f"Completion object: {completion}")
        
        # Assertions to make this a proper test
        assert completion is not None, "No completion object received"
        assert message.content is not None and len(message.content) > 0, "No content in response"
        print("✅ XAI direct test passed!")
        
    except Exception as e:
        print(f"ERROR: {e}")
        print(f"Error type: {type(e)}")
        assert False, f"XAI API call failed: {e}"

def test_with_structured_output():
    """Test with structured output like in the game."""
    
    api_key = os.environ.get("XAI_API_KEY")
    
    if not api_key:
        pytest.skip("XAI_API_KEY not found in environment variables. Skipping live test.")

    print(f"\nUsing API key from environment for structured test: {api_key[:10]}...")

    messages = [
        {
            "role": "system",
            "content": "You are Great Oracle, a wise, ancient, and somewhat cryptic Oracle in the Fungi Fortress.",
        },
        {
            "role": "user",
            "content": "Game Context: Tick: 100. Player depth: 5. \n\nPlayer Query: What is the meaning of this mushroom?",
        },
    ]

    client = OpenAI(
        base_url="https://api.x.ai/v1",
        api_key=api_key,
    )

    oracle_schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "oracle_response",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "narrative": {
                        "type": "string",
                        "description": "The Oracle's narrative response to show to the player"
                    },
                    "actions": {
                        "type": "array",
                        "description": "Game actions to execute",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action_type": {"type": "string"},
                                "details": {"type": "object"}
                            },
                            "required": ["action_type", "details"],
                            "additionalProperties": False
                        }
                    }
                },
                "required": ["narrative", "actions"],
                "additionalProperties": False
            }
        }
    }

    try:
        print("\n=== TESTING WITH STRUCTURED OUTPUT ===")
        completion = client.chat.completions.create(
            model="grok-3-mini", 
            reasoning_effort="high",
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
            response_format=oracle_schema
        )

        message = completion.choices[0].message
        
        if hasattr(message, 'reasoning_content') and message.reasoning_content:
            print("Reasoning Content:")
            print(message.reasoning_content)

        print("\nStructured Response:")
        print(message.content)
        
        # Try parsing as JSON
        import json
        parsed = json.loads(message.content)
        print(f"\nParsed JSON:")
        print(f"Narrative: {parsed.get('narrative')}")
        print(f"Actions: {parsed.get('actions')}")
        
        # Assertions to make this a proper test
        assert completion is not None, "No completion object received"
        assert message.content is not None, "No content in response"
        assert "narrative" in parsed, "Missing narrative in structured response"
        assert "actions" in parsed, "Missing actions in structured response"
        assert isinstance(parsed["narrative"], str), "Narrative should be a string"
        assert isinstance(parsed["actions"], list), "Actions should be a list"
        print("✅ Structured output test passed!")

    except json.JSONDecodeError as e:
        print(f"JSON parsing failed: {e}")
        assert False, f"Failed to parse structured JSON response: {e}"
    except Exception as e:
        print(f"ERROR with structured output: {e}")
        assert False, f"Structured output test failed: {e}"

if __name__ == "__main__":
    print("Testing XAI API Direct Integration")
    print("=" * 50)
    
    test_xai_direct()
    test_with_structured_output() 