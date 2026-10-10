"""Oracle LLM integration using the unified client.

Handles Oracle dialogue with proper prompt construction.
"""

from __future__ import annotations

import logging
from typing import Any

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
