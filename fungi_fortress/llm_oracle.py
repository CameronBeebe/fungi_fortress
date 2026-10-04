"""Oracle LLM integration using the unified client.

Handles Oracle dialogue with proper prompt construction, streaming support,
and graceful error handling.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator, Optional

from . import llm_client
from .world_seed import NpcReply

logger = logging.getLogger(__name__)


def build_oracle_messages(
    oracle_name: str,
    player_query: str,
    game_context: dict[str, Any],
    history: list[dict[str, str]],
) -> list[dict]:
    """Build message list for Oracle query.
    
    Args:
        oracle_name: Name of the Oracle
        player_query: Player's question
        game_context: Dict with tick, depth, mission, resources, etc.
        history: Recent conversation history
        
    Returns:
        List of message dicts for LLM API
    """
    # System message
    system_content = (
        f"You are {oracle_name}, a wise, ancient, and somewhat cryptic Oracle "
        f"in the Fungi Fortress. Respond to the player's query with insightful, "
        f"thematic, and sometimes enigmatic guidance. Your responses should be "
        f"a single paragraph."
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
    reasoning_effort: str = "high",
) -> Iterator[str]:
    """Query the Oracle with streaming response (narrative only, no structured actions).
    
    Note: xAI structured outputs don't support streaming, so this function streams
    raw narrative text without typed actions. For structured replies with actions,
    use query_oracle() instead.
    
    Args:
        client: LLM client instance
        oracle_name: Name of the Oracle
        player_query: Player's question
        game_context: Game state context
        history: Recent conversation history
        max_tokens: Max tokens to generate
        reasoning_effort: Reasoning effort level (from config)
        
    Yields:
        Response chunks as they arrive
        
    Raises:
        llm_client.LLMError: On API errors
    """
    messages = build_oracle_messages(oracle_name, player_query, game_context, history)
    
    logger.info(f"Oracle query (streaming): {player_query[:50]}...")
    
    if client.is_mock():
        logger.info("Using mock provider for Oracle response")
    
    try:
        # No structured output for streaming
        yield from client.chat_stream(messages, max_tokens, reasoning_effort)
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
    reasoning_effort: str = "high",
) -> Optional[NpcReply]:
    """Query the Oracle with non-streaming response using structured output.
    
    Args:
        client: LLM client instance
        oracle_name: Name of the Oracle
        player_query: Player's question
        game_context: Game state context
        history: Recent conversation history
        max_tokens: Max tokens to generate
        reasoning_effort: Reasoning effort level (from config)
        
    Returns:
        Validated NpcReply or None on failure
        
    Raises:
        llm_client.LLMError: On API errors
    """
    messages = build_oracle_messages(oracle_name, player_query, game_context, history)
    
    logger.info(f"Oracle query (non-streaming): {player_query[:50]}...")
    
    if client.is_mock():
        logger.info("Using mock provider for Oracle response")
    
    # Use structured_call with validation
    return llm_client.structured_call(
        client,
        messages,
        NpcReply,
        schema_name="npc_reply",
        label="Oracle reply",
        max_tokens=max_tokens or 1000,
        reasoning_effort=reasoning_effort,
        attempts=2,
    )
