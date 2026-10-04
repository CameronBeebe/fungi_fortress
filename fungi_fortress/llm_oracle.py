"""Oracle LLM integration using the unified client.

Handles Oracle dialogue with proper prompt construction, streaming support,
and graceful error handling.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator, Optional

from . import llm_client

logger = logging.getLogger(__name__)


def build_oracle_messages(
    oracle_name: str,
    player_query: str,
    game_context: dict[str, Any],
    history: list[dict[str, str]],
    enable_structured_outputs: bool = False,
) -> list[dict]:
    """Build message list for Oracle query.
    
    Args:
        oracle_name: Name of the Oracle
        player_query: Player's question
        game_context: Dict with tick, depth, mission, resources, etc.
        history: Recent conversation history
        enable_structured_outputs: Whether to request JSON schema format
        
    Returns:
        List of message dicts for LLM API
    """
    # System message with action instructions
    system_content = (
        f"You are {oracle_name}, a wise, ancient, and somewhat cryptic Oracle "
        f"in the Fungi Fortress. Respond to the player's query with insightful, "
        f"thematic, and sometimes enigmatic guidance. Your responses should be "
        f"a single paragraph."
    )
    
    # Add action instructions based on output format
    if enable_structured_outputs:
        system_content += (
            "\n\nYour entire response MUST be a single JSON object. This JSON object must have two keys: "
            "'narrative' (string) and 'actions' (array). "
            "The 'narrative' should contain your textual response to the player. "
            "The 'actions' array should contain any game actions to execute. Each action in the array "
            "must be an object with 'action_type' (string) and 'details' (object) keys. "
            "Example: "
            '{"narrative": "A strange energy emanates from the east.", "actions": [{"action_type": "add_message", "details": {"text": "Energy pulse detected."}}]} '
            "If no actions are needed, provide an empty array for 'actions'."
        )
    else:
        system_content += (
            "\n\nIf you wish to suggest a game event or action, embed it in your response using the format: "
            "ACTION::action_type::{\"json_key\": \"json_value\"}. For example: "
            "ACTION::add_message::{\"text\": \"A strange energy emanates from the east.\"} or "
            "ACTION::spawn_character::{\"type\": \"Mystic Fungoid\", \"name\": \"Glimmercap\", \"x\": 10, \"y\": 12}. "
            "Use double quotes in JSON and ensure the JSON is valid. Actions are optional - only include them if meaningful to your response."
        )
    
    # Build context string
    context_parts = []
    context_parts.append(f"Tick: {game_context.get('tick', 0)}")
    context_parts.append(f"Depth: {game_context.get('depth', 1)}")
    
    mission = game_context.get('mission')
    if mission:
        context_parts.append(f"Mission: {mission.get('description', 'Unknown')}")
    
    resources = game_context.get('resources')
    if resources:
        context_parts.append(f"Resources: {resources}")
    
    context_str = " | ".join(context_parts)
    
    # Build history string
    # History is already trimmed by caller based on context_level
    if history:
        history_lines = []
        for exchange in history:
            history_lines.append(f"Player: {exchange['player']}")
            history_lines.append(f"Oracle: {exchange['oracle']}")
        history_str = "\n".join(history_lines)
    else:
        history_str = "No previous conversation."
    
    # Construct user message
    user_content = (
        f"Game Context: {context_str}\n\n"
        f"Recent History:\n{history_str}\n\n"
        f"Player Query: {player_query}"
    )
    
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content}
    ]


def query_oracle_streaming(
    client: llm_client.LLMClient,
    oracle_name: str,
    player_query: str,
    game_context: dict[str, Any],
    history: list[dict[str, str]],
    max_tokens: Optional[int] = None,
    enable_structured_outputs: bool = False,
) -> Iterator[str]:
    """Query the Oracle with streaming response.
    
    Args:
        client: LLM client instance
        oracle_name: Name of the Oracle
        player_query: Player's question
        game_context: Game state context
        history: Recent conversation history
        max_tokens: Max tokens to generate
        enable_structured_outputs: Whether to request JSON schema format
        
    Yields:
        Response chunks as they arrive
        
    Raises:
        llm_client.LLMError: On API errors
    """
    messages = build_oracle_messages(oracle_name, player_query, game_context, history, enable_structured_outputs)
    
    logger.info(f"Oracle query (streaming): {player_query[:50]}...")
    
    if client.is_mock():
        logger.info("Using mock provider for Oracle response")
    
    try:
        yield from client.chat_stream(messages, max_tokens, reasoning_effort="high")
    except llm_client.LLMError:
        # Re-raise typed errors
        raise


def query_oracle(
    client: llm_client.LLMClient,
    oracle_name: str,
    player_query: str,
    game_context: dict[str, Any],
    history: list[dict[str, str]],
    max_tokens: Optional[int] = None,
    enable_structured_outputs: bool = False,
) -> str:
    """Query the Oracle with non-streaming response.
    
    Args:
        client: LLM client instance
        oracle_name: Name of the Oracle
        player_query: Player's question
        game_context: Game state context
        history: Recent conversation history
        max_tokens: Max tokens to generate
        enable_structured_outputs: Whether to request JSON schema format
        
    Returns:
        Complete Oracle response
        
    Raises:
        llm_client.LLMError: On API errors
    """
    messages = build_oracle_messages(oracle_name, player_query, game_context, history, enable_structured_outputs)
    
    logger.info(f"Oracle query (non-streaming): {player_query[:50]}...")
    
    if client.is_mock():
        logger.info("Using mock provider for Oracle response")
    
    try:
        return client.chat(messages, max_tokens, reasoning_effort="high", use_json_schema=enable_structured_outputs)
    except llm_client.LLMError:
        # Re-raise typed errors
        raise
