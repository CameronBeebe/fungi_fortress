"""Interface for connecting game events to LLM using the unified client.

This module provides Oracle dialogue functionality using the new llm_client
infrastructure, maintaining compatibility with existing game_logic expectations.
"""

import datetime
import json as json_lib
import logging
from datetime import timezone
from typing import Any, Dict, Iterator, List, Optional

from . import llm_client, llm_oracle
from .text_streaming import text_streaming_engine
from .npc_reply import validate_npc_reply

logger = logging.getLogger(__name__)

# Context level history limits (single source of truth)
HISTORY_LIMITS = {'low': 1, 'medium': 3, 'high': 5}

# Oracle interaction history limit
MAX_ORACLE_HISTORY = 10


def handle_game_event(event_data: Dict[str, Any], game_state: Any) -> Optional[List[Dict[str, Any]]]:
    """Process a game event, potentially triggering LLM interaction.

    Args:
        event_data: The event data dictionary
        game_state: The current game state

    Returns:
        List of action dictionaries or None
    """
    event_type = event_data.get("type")
    
    # Oracle queries always use non-streaming to get typed actions
    if event_type == "ORACLE_QUERY" and game_state.llm_config:
        return handle_oracle_query_non_streaming(event_data, game_state)
    
    return None


def handle_oracle_query_non_streaming(event_data: Dict[str, Any], game_state: Any) -> Optional[List[Dict[str, Any]]]:
    """Handle Oracle queries with non-streaming responses."""
    details = event_data.get("details", {})
    player_query = details.get("query_text")
    oracle_name = details.get("oracle_name", "The Oracle")
    
    actions_to_execute = []
    
    if not player_query:
        logger.info("No query text in ORACLE_QUERY event")
        return [{
            "action_type": "add_oracle_dialogue",
            "details": {"text": "(You offer your thoughts, but no words escape.)"}
        }]
    
    # Get or create LLM client
    client = game_state.llm_config.create_llm_client()
    
    # Build game context
    game_context = _build_game_context(game_state)
    
    # Trim history based on context level
    history_limit = HISTORY_LIMITS[game_state.llm_config.context_level]
    trimmed_history = game_state.oracle_llm_interaction_history[-history_limit:] if game_state.oracle_llm_interaction_history else []
    
    # Log interaction timestamp
    timestamp_utc = datetime.datetime.now(timezone.utc).isoformat()
    if "+00:00" in timestamp_utc:
        timestamp_utc = timestamp_utc.replace("+00:00", "Z")
    elif not timestamp_utc.endswith("Z"):
        timestamp_utc += "Z"
    
    # Build messages
    messages = llm_oracle.build_oracle_messages(
        oracle_name=oracle_name,
        player_query=player_query,
        game_context=game_context,
        history=trimmed_history,
    )
    
    # Validator wrapper for structured_call
    def validator(reply):
        return validate_npc_reply(reply, game_state)
    
    try:
        reply = llm_client.structured_call(
            client,
            messages,
            llm_oracle.NpcReply,
            schema_name="npc_reply",
            label="Oracle reply",
            convert=validator,
        )
        
        if reply:
            # Add narrative to dialogue
            actions_to_execute.append({
                "action_type": "add_oracle_dialogue",
                "details": {"text": reply.narrative, "is_llm_response": True}
            })
            
            # Add any game actions from the structured reply
            # Convert typed actions to game_logic format (action_type + details)
            for action in reply.actions:
                action_dict = action.model_dump()
                action_type = action_dict.pop("action_type")
                actions_to_execute.append({
                    "action_type": action_type,
                    "details": action_dict
                })
            
            # Update history with narrative only
            game_state.oracle_llm_interaction_history.append({
                "player": player_query,
                "oracle": reply.narrative
            })
            if len(game_state.oracle_llm_interaction_history) > MAX_ORACLE_HISTORY:
                game_state.oracle_llm_interaction_history.pop(0)
            
            # Log interaction
            _log_oracle_interaction(
                timestamp=timestamp_utc,
                player_query=player_query,
                response=reply.narrative,
                is_mock=client.is_mock(),
                error=None,
                parsed_narrative=reply.narrative,
                parsed_actions=[a.model_dump() for a in reply.actions] if reply.actions else [],
            )
        else:
            # Fallback response
            fallback_text = "(The Oracle remains silent, its vision obscured.)"
            actions_to_execute.append({
                "action_type": "add_oracle_dialogue",
                "details": {"text": fallback_text}
            })
            _log_oracle_interaction(
                timestamp=timestamp_utc,
                player_query=player_query,
                response=None,
                is_mock=client.is_mock(),
                error="structured_call returned None",
                parsed_narrative=fallback_text,
                parsed_actions=[],
            )
        
    except llm_client.LLMError as e:
        error_message = e.user_message()
        logger.warning(f"Oracle query failed: {e}")
        
        actions_to_execute.append({
            "action_type": "add_oracle_dialogue",
            "details": {"text": error_message, "is_llm_response": True}
        })
        
        game_state.oracle_llm_interaction_history.append({
            "player": player_query,
            "oracle": error_message
        })
        
        _log_oracle_interaction(
            timestamp=timestamp_utc,
            player_query=player_query,
            response=None,
            is_mock=False,
            error=str(e),
        )
    
    # Return to awaiting prompt state
    actions_to_execute.append({
        "action_type": "set_oracle_state",
        "details": {"state": "AWAITING_PROMPT"}
    })
    
    return actions_to_execute


def _build_game_context(game_state: Any) -> Dict[str, Any]:
    """Build game context dict from game state.
    
    Context level determines what to include:
    - low: tick, depth only
    - medium: + mission
    - high: + mission + resources
    """
    context = {
        'tick': game_state.tick,
        'depth': game_state.depth,
    }
    
    # Get context level from config
    context_level = game_state.llm_config.context_level if game_state.llm_config else "medium"
    
    # Add mission for medium and high
    if context_level in ('medium', 'high'):
        if hasattr(game_state, 'mission') and game_state.mission:
            context['mission'] = game_state.mission
    
    # Add resources only for high
    if context_level == 'high':
        if hasattr(game_state, 'player_resources'):
            context['resources'] = game_state.player_resources
        elif hasattr(game_state, 'inventory'):
            context['resources'] = getattr(game_state.inventory, 'resources', {})
    
    return context


def _log_oracle_interaction(
    timestamp: str,
    player_query: str,
    response: Optional[str],
    is_mock: bool,
    error: Optional[str],
    parsed_narrative: Optional[str] = None,
    parsed_actions: Optional[List[Dict[str, Any]]] = None,
):
    """Log an Oracle LLM interaction."""
    provider_info = "mock" if is_mock else "live API"
    
    log_data = {
        "timestamp": timestamp,
        "query": player_query[:70] + "..." if len(player_query) > 70 else player_query,
        "response_len": len(response) if response else 0,
        "provider": provider_info,
    }
    
    if parsed_actions:
        log_data["action_count"] = len(parsed_actions)
    
    if error:
        log_data["error"] = error
        logger.warning(f"[OracleInteraction] {log_data}")
    else:
        logger.info(f"[OracleInteraction] {log_data}")
