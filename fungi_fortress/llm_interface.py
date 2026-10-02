"""Interface for connecting game events to LLM using the unified client.

This module provides Oracle dialogue functionality using the new llm_client
infrastructure, maintaining compatibility with existing game_logic expectations.
"""

import datetime
import logging
from datetime import timezone
from typing import Any, Dict, Iterator, List, Optional

from . import llm_client, llm_oracle
from .text_streaming import text_streaming_engine

logger = logging.getLogger(__name__)


def handle_game_event(event_data: Dict[str, Any], game_state: Any) -> Optional[List[Dict[str, Any]]]:
    """Process a game event, potentially triggering LLM interaction.

    Args:
        event_data: The event data dictionary
        game_state: The current game state

    Returns:
        List of action dictionaries or None
    """
    event_type = event_data.get("type")
    
    if event_type == "ORACLE_QUERY" and game_state.llm_config:
        # Check if streaming is enabled
        enable_streaming = getattr(game_state.llm_config, 'enable_streaming', True)
        
        if enable_streaming:
            return handle_oracle_query_streaming(event_data, game_state)
        else:
            return handle_oracle_query_non_streaming(event_data, game_state)
    
    return None


def handle_oracle_query_streaming(event_data: Dict[str, Any], game_state: Any) -> Optional[List[Dict[str, Any]]]:
    """Handle Oracle queries with streaming responses."""
    details = event_data.get("details", {})
    player_query = details.get("query_text")
    oracle_name = details.get("oracle_name", "The Oracle")
    
    if not player_query:
        logger.info("No query text in ORACLE_QUERY event")
        return [{
            "action_type": "add_oracle_dialogue",
            "details": {"text": "(You offer your thoughts, but no words escape.)"}
        }]
    
    # Return action to start enhanced streaming
    return [{
        "action_type": "start_enhanced_oracle_streaming",
        "details": {
            "player_query": player_query,
            "oracle_name": oracle_name,
        }
    }]


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
    
    # Log interaction timestamp
    timestamp_utc = datetime.datetime.now(timezone.utc).isoformat()
    if "+00:00" in timestamp_utc:
        timestamp_utc = timestamp_utc.replace("+00:00", "Z")
    elif not timestamp_utc.endswith("Z"):
        timestamp_utc += "Z"
    
    try:
        response = llm_oracle.query_oracle(
            client=client,
            oracle_name=oracle_name,
            player_query=player_query,
            game_context=game_context,
            history=game_state.oracle_llm_interaction_history,
            max_tokens=game_state.llm_config.max_tokens,
        )
        
        # Add response to dialogue
        actions_to_execute.append({
            "action_type": "add_oracle_dialogue",
            "details": {"text": response, "is_llm_response": True}
        })
        
        # Update history
        game_state.oracle_llm_interaction_history.append({
            "player": player_query,
            "oracle": response
        })
        if len(game_state.oracle_llm_interaction_history) > 10:
            game_state.oracle_llm_interaction_history.pop(0)
        
        # Log interaction
        _log_oracle_interaction(
            timestamp=timestamp_utc,
            player_query=player_query,
            response=response,
            is_mock=client.is_mock(),
            error=None,
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


def process_enhanced_oracle_streaming(
    prompt: str,  # Ignored, kept for compatibility
    api_key: str,  # Ignored, kept for compatibility
    model_name: str,  # Ignored, kept for compatibility
    provider_hint: str,  # Ignored, kept for compatibility
    llm_config,
    player_query: str,
    oracle_name: str
) -> Iterator[Dict[str, Any]]:
    """Process enhanced Oracle streaming with the unified client.
    
    This maintains the same interface as the old implementation but uses
    the new llm_client internally.
    
    Args:
        prompt: Unused (kept for compatibility)
        api_key: Unused (kept for compatibility)
        model_name: Unused (kept for compatibility)
        provider_hint: Unused (kept for compatibility)
        llm_config: LLM configuration object
        player_query: The player's question
        oracle_name: Name of the Oracle
        
    Yields:
        Action dictionaries for the game logic to process
    """
    # Get or create LLM client from config
    client = llm_config.create_llm_client()
    
    # Build game context (we need to get this from somewhere)
    # For now, use minimal context - this could be passed in
    game_context = {
        'tick': 0,
        'depth': 1,
        'mission': None,
        'resources': {},
    }
    
    timestamp_utc = datetime.datetime.now(timezone.utc).isoformat()
    if "+00:00" in timestamp_utc:
        timestamp_utc = timestamp_utc.replace("+00:00", "Z")
    elif not timestamp_utc.endswith("Z"):
        timestamp_utc += "Z"
    
    complete_response = ""
    error_for_log = None
    
    try:
        # Create streaming iterator
        def llm_iterator():
            nonlocal complete_response, error_for_log
            
            try:
                for chunk in llm_oracle.query_oracle_streaming(
                    client=client,
                    oracle_name=oracle_name,
                    player_query=player_query,
                    game_context=game_context,
                    history=[],  # History should come from game_state
                    max_tokens=llm_config.max_tokens,
                ):
                    complete_response += chunk
                    yield chunk
            except llm_client.LLMError as e:
                error_for_log = str(e)
                yield e.user_message()
        
        # Use text streaming engine for display
        for action in text_streaming_engine.start_oracle_streaming_sequence(
            oracle_name,
            player_query,
            llm_iterator()
        ):
            yield action
        
        # Log the complete interaction
        _log_oracle_interaction(
            timestamp=timestamp_utc,
            player_query=player_query,
            response=complete_response if complete_response else None,
            is_mock=client.is_mock(),
            error=error_for_log,
        )
        
    except Exception as e:
        error_message = "The Oracle's connection is severely disrupted."
        logger.error(f"Critical error in enhanced streaming: {e}")
        
        yield {
            "action_type": "stream_text_chunk",
            "details": {
                "text": error_message,
                "text_type": "oracle_dialogue",
                "target": "oracle_dialogue",
                "delay_ms": 3,
                "add_newline": True,
                "is_error": True
            }
        }
        
        yield {
            "action_type": "set_oracle_state",
            "details": {"state": "AWAITING_PROMPT"}
        }
        
        _log_oracle_interaction(
            timestamp=timestamp_utc,
            player_query=player_query,
            response=None,
            is_mock=False,
            error=str(e),
        )


def _build_game_context(game_state: Any) -> Dict[str, Any]:
    """Build game context dict from game state."""
    context = {
        'tick': game_state.tick,
        'depth': game_state.depth,
    }
    
    if hasattr(game_state, 'mission') and game_state.mission:
        context['mission'] = game_state.mission
    
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
    error: Optional[str]
):
    """Log an Oracle LLM interaction."""
    provider_info = "mock" if is_mock else "live API"
    
    log_data = {
        "timestamp": timestamp,
        "query": player_query[:70] + "..." if len(player_query) > 70 else player_query,
        "response_len": len(response) if response else 0,
        "provider": provider_info,
    }
    
    if error:
        log_data["error"] = error
        logger.warning(f"[OracleInteraction] {log_data}")
    else:
        logger.info(f"[OracleInteraction] {log_data}")
