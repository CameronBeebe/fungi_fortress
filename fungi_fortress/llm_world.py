"""World seed generation using the unified LLM client.

Wraps the unified client for world seed generation, replacing the urllib-based
_chat function in world_seed.py.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from . import llm_client

logger = logging.getLogger(__name__)


def generate_world_seed(
    client: llm_client.LLMClient,
    prompt: str,
    max_tokens: int = 4000,
) -> dict[str, Any]:
    """Generate a world seed using the LLM client.
    
    Args:
        client: LLM client instance
        prompt: World generation prompt
        max_tokens: Maximum tokens to generate
        
    Returns:
        Parsed JSON world seed dict
        
    Raises:
        ValueError: If response is invalid or cannot be parsed
        llm_client.LLMError: On API errors
    """
    messages = [
        {"role": "system", "content": "You write one JSON object and nothing else."},
        {"role": "user", "content": prompt},
    ]
    
    logger.info("Generating world seed with LLM")
    
    try:
        response = client.chat(messages, max_tokens, use_json_schema=False)
    except llm_client.LLMError as e:
        # Convert LLM errors to ValueError for compatibility with existing error handling
        raise ValueError(f"LLM error: {e}") from e
    
    if not response or not response.strip():
        raise ValueError("LLM returned empty world seed")
    
    # Extract JSON from response (handle code fences)
    parsed = _extract_json(response)
    return parsed


def _extract_json(raw: str) -> dict[str, Any]:
    """Extract JSON object from LLM response.
    
    Handles markdown code fences and other formatting.
    """
    text = raw.strip()
    
    # Remove markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
    
    # Find JSON object boundaries
    start = text.find("{")
    end = text.rfind("}")
    
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Response did not contain a JSON object")
    
    # Parse JSON
    parsed = json.loads(text[start : end + 1])
    
    if not isinstance(parsed, dict):
        raise ValueError("World seed must be a JSON object")
    
    return parsed
