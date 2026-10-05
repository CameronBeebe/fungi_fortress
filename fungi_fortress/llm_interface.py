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

# Context level history limits (single source of truth)
HISTORY_LIMITS = {'low': 1, 'medium': 3, 'high': 5}


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
        if game_state.llm_config.enable_streaming:
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
    
    # Build game context and prompt
    game_context = _build_game_context(game_state)
    
    # Trim history based on context level
    history_limit = HISTORY_LIMITS.get(game_state.llm_config.context_level, 3)
    trimmed_history = game_state.oracle_llm_interaction_history[-history_limit:] if game_state.oracle_llm_interaction_history else []
    
    messages = llm_oracle.build_oracle_messages(
        oracle_name=oracle_name,
        player_query=player_query,
        game_context=game_context,
        history=trimmed_history,
        enable_structured_outputs=enable_structured_outputs,
    )
    
    # Convert messages to a single prompt string for compatibility
    # Format: system message + context + history + query
    prompt_parts = []
    for msg in messages:
        if msg["role"] == "system":
            prompt_parts.append(msg["content"])
        else:
            prompt_parts.append(msg["content"])
    prompt = "\n\n".join(prompt_parts)
    
    # Return action to start enhanced streaming (without API key in details)
    return [{
        "action_type": "start_enhanced_oracle_streaming",
        "details": {
            "prompt": prompt,
            "model_name": game_state.llm_config.model_name,
            "provider_hint": "xai",  # Fixed to XAI provider
            # NOTE: llm_config NOT included here to prevent API key leaks in logs
            "player_query": player_query,
            "oracle_name": oracle_name,
            "game_context": game_context,
            "history": trimmed_history,  # Use trimmed history based on context_level
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
    
    # Trim history based on context level
    history_limit = HISTORY_LIMITS.get(game_state.llm_config.context_level, 3)
    trimmed_history = game_state.oracle_llm_interaction_history[-history_limit:] if game_state.oracle_llm_interaction_history else []
    
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
            history=trimmed_history,
            max_tokens=game_state.llm_config.max_tokens,
            enable_structured_outputs=game_state.llm_config.enable_structured_outputs,
        )
        
        # Parse response for narrative and actions
        parsed_narrative, parsed_actions = _parse_llm_response(response)
        
        # Add narrative to dialogue
        if parsed_narrative:
            actions_to_execute.append({
                "action_type": "add_oracle_dialogue",
                "details": {"text": parsed_narrative, "is_llm_response": True}
            })
        
        # Add any game actions from the response
        if parsed_actions:
            actions_to_execute.extend(parsed_actions)
        
        # Update history with narrative only
        game_state.oracle_llm_interaction_history.append({
            "player": player_query,
            "oracle": parsed_narrative
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
            parsed_narrative=parsed_narrative,
            parsed_actions=parsed_actions,
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
    llm_config,
    player_query: str,
    oracle_name: str,
    game_context: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> Iterator[Dict[str, Any]]:
    """Process enhanced Oracle streaming with the unified client.
    
    Args:
        llm_config: LLM configuration object
        player_query: The player's question
        oracle_name: Name of the Oracle
        game_context: Game state context dict
        history: Conversation history
        
    Yields:
        Action dictionaries for the game logic to process
    """
    # Get or create LLM client from config (API key comes from here)
    client = llm_config.create_llm_client()
    
    # Use provided context or minimal defaults
    if game_context is None:
        game_context = {
            'tick': 0,
            'depth': 1,
            'mission': None,
            'resources': {},
        }
    
    if history is None:
        history = []
    
    timestamp_utc = datetime.datetime.now(timezone.utc).isoformat()
    if "+00:00" in timestamp_utc:
        timestamp_utc = timestamp_utc.replace("+00:00", "Z")
    elif not timestamp_utc.endswith("Z"):
        timestamp_utc += "Z"
    
    complete_response = ""
    error_for_log = None
    parsed_narrative = None
    parsed_actions = None
    
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
                    history=history,
                    max_tokens=llm_config.max_tokens,
                    enable_structured_outputs=llm_config.enable_structured_outputs,
                ):
                    complete_response += chunk
                    yield chunk
            except llm_client.LLMError as e:
                error_for_log = str(e)
                yield e.user_message()
        
        # Use text streaming engine for display
        # Note: The streaming engine already parses and yields actions during streaming,
        # so we don't need to parse the complete_response again (that would execute actions twice)
        for action in text_streaming_engine.start_oracle_streaming_sequence(
            oracle_name,
            player_query,
            llm_iterator()
        ):
            yield action
        
        # Parse the complete response for LOGGING only (not for execution)
        if complete_response and not error_for_log:
            parsed_narrative, parsed_actions = _parse_llm_response(complete_response)
        
        # Log the complete interaction
        _log_oracle_interaction(
            timestamp=timestamp_utc,
            player_query=player_query,
            response=complete_response if complete_response else None,
            is_mock=client.is_mock(),
            error=error_for_log,
            parsed_narrative=parsed_narrative,
            parsed_actions=parsed_actions,
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


def _parse_llm_response(response_text: str) -> tuple[str, List[Dict[str, Any]]]:
    """Parse the LLM's raw response text to separate narrative from structured actions.
    
    Supports both:
    - JSON format: {"narrative": "...", "actions": [...]}
    - Text format with ACTION::action_type::{"json": "data"}
    
    Args:
        response_text: The raw string response from the LLM
        
    Returns:
        Tuple[str, List[Dict[str, Any]]]: (narrative, actions)
    """
    import json as json_lib
    
    # First, try to parse as structured JSON
    try:
        parsed_json = json_lib.loads(response_text.strip())
        if isinstance(parsed_json, dict) and "narrative" in parsed_json and "actions" in parsed_json:
            narrative = parsed_json["narrative"]
            actions = parsed_json["actions"]
            
            # Validate actions structure
            validated_actions = []
            for action in actions:
                if isinstance(action, dict) and "action_type" in action and "details" in action:
                    validated_actions.append(action)
                else:
                    logger.debug(f"Skipping malformed action in structured response: {action}")
            
            logger.debug(f"Successfully parsed structured JSON response with {len(validated_actions)} actions")
            return narrative, validated_actions
    except json_lib.JSONDecodeError:
        pass
    except Exception as e:
        logger.debug(f"Error parsing structured JSON response: {e}, falling back to text parsing")
    
    # Legacy text parsing with ACTION:: markers
    narrative_parts = []
    actions = []
    parts = response_text.split("ACTION::")
    
    if parts:
        narrative_parts.append(parts[0].strip())
        
        for part in parts[1:]:
            try:
                action_def = part.strip()
                # Expecting format: action_type::{"json": "details"}
                action_type, json_details_str = action_def.split("::", 1)
                
                # Try to parse the JSON
                details = None
                try:
                    details = json_lib.loads(json_details_str)
                except json_lib.JSONDecodeError:
                    # Try fixing single quotes to double quotes
                    try:
                        fixed_json = json_details_str.replace("'", '"')
                        details = json_lib.loads(fixed_json)
                        logger.debug(f"Fixed JSON quotes for action: {action_type}")
                    except json_lib.JSONDecodeError as e2:
                        logger.debug(f"Error decoding JSON from LLM action: {json_details_str}. Error: {e2}")
                        # Add error message to narrative
                        narrative_parts.append(f"(The Oracle's words concerning an action were muddled: {action_type}::{json_details_str})")
                        continue
                
                if details is not None:
                    actions.append({"action_type": action_type.strip(), "details": details})
                    
            except ValueError:
                logger.debug(f"Malformed action string from LLM: {part.strip()}")
                narrative_parts.append(f"(The Oracle made an unclear gesture: {part.strip()})")
                continue
    
    return " ".join(narrative_parts).strip(), actions


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
