# llm_interface.py
"""Interface for connecting game events and actions to an LLM.

This module will contain functions to:
- Process game events.
- Format requests for an LLM.
- Parse LLM responses.
- Translate LLM responses into game actions or data structures.
"""

import json # Added for parsing LLM responses that might include JSON
import os # Added for API key environment variable fallback
from typing import List, Dict, Optional, Any
import datetime # Added for timestamping logs
from datetime import timezone # Explicitly import timezone

from groq import Groq, RateLimitError, APIConnectionError, APIStatusError # Added Groq imports

# Import GameEvent and GameState if defined elsewhere for type hinting
# from .game_state import GameEvent, GameState # Assuming GameEvent is defined there
# from .config_manager import OracleConfig # For API key access

# Placeholder for an actual LLM API call function
# In a real scenario, this would involve libraries like 'requests' or a specific LLM provider's SDK
def _call_llm_api(prompt: str, api_key: str, model_name: Optional[str] = None) -> Optional[str]:
    """Makes an API call to an LLM using the Groq client for X.AI.

    Args:
        prompt (str): The complete prompt to send to the LLM.
        api_key (str): The API key for the LLM service.
        model_name (Optional[str]): The specific model to use.

    Returns:
        Optional[str]: The LLM's response string, or None if an error occurs.
    """
    print(f"[LLM API Call] Sending prompt (first 100 chars): {prompt[:100]}...")
    print(f"[LLM API Call] Using API Key: {'*' * (len(api_key) - 4) + api_key[-4:] if api_key and len(api_key) > 4 else 'KEY_TOO_SHORT_OR_INVALID'}")
    print(f"[LLM API Call] Using Model: {model_name if model_name else 'DEFAULT_MODEL_NOT_SPECIFIED_IN_CONFIG'}")

    if not api_key or api_key == "YOUR_API_KEY_HERE" or api_key == "testkey123": # Basic check
        error_msg = "Error: API key is missing, a placeholder, or the test key. Configure oracle_config.ini."
        print(f"[LLM API Call] {error_msg}")
        # Return a canned response indicating a configuration error
        return f"The Oracle's connection is disrupted. (Error: API Key not configured for LLM. Details: {error_msg})"

    if not model_name:
        error_msg = "Error: Model name not specified in oracle_config.ini."
        print(f"[LLM API Call] {error_msg}")
        return f"The Oracle's connection is unstable. (Error: LLM Model not specified. Details: {error_msg})"

    try:
        # Initialize the Groq client
        # It will automatically look for GROQ_API_KEY environment variable if api_key is None,
        # but we are passing it directly from the config.
        client = Groq(api_key=api_key)

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=model_name,
            # Optional parameters (refer to X.AI/Groq documentation):
            # temperature=0.7, 
            # max_tokens=1024,
            # top_p=1,
            # stream=False, # Set to True if you want to stream responses
        )
        
        response_content = chat_completion.choices[0].message.content
        if response_content:
            # Log the successful response before returning
            # (We'll add more detailed file logging in the next step)
            print(f"[LLM API Call] Successfully received response (first 100 chars): {response_content[:100]}...")
            return response_content
        else:
            print("[LLM API Call] Error: Received an empty response from the LLM.")
            return "The Oracle's thoughts are unusually silent. (Error: Empty response from LLM)"

    except RateLimitError as e:
        print(f"[LLM API Call] RateLimitError: {e}")
        return f"The Oracle is overwhelmed by cosmic energies. (Error: API rate limit exceeded. Details: {e})"
    except APIConnectionError as e:
        print(f"[LLM API Call] APIConnectionError: {e}")
        return f"The Oracle cannot reach the cosmic echoes. (Error: API connection issue. Details: {e})"
    except APIStatusError as e:
        print(f"[LLM API Call] APIStatusError: Status {e.status_code} - {e.message}")
        error_detail = f"Status {e.status_code} - {e.message}"
        if e.status_code == 401: # Unauthorized
             error_detail += " (Check your API key in oracle_config.ini)"
        elif e.status_code == 404: # Model not found
             error_detail += f" (Model '{model_name}' might be incorrect or unavailable)"
        return f"The Oracle's connection is unstable. (Error: API status problem. Details: {error_detail})"
    except Exception as e:
        # Catch any other unexpected errors during the API call
        print(f"[LLM API Call] Unexpected error: {e}")
        return f"A mysterious interference disrupts the Oracle. (Error: Unexpected problem during LLM call. Details: {e})"

# --- LLM Interaction Logging ---
ORACLE_LOG_FILE = "oracle_interactions.log"

def _log_oracle_interaction(timestamp: str, player_query: str, prompt: str, raw_response: Optional[str], 
                            parsed_narrative: Optional[str], parsed_actions: Optional[List[Dict[str, Any]]],
                            error_message: Optional[str] = None):
    """Logs the details of an Oracle LLM interaction to a file."""
    log_entry = {
        "timestamp": timestamp,
        "player_query": player_query,
        "full_prompt_sent": prompt,
        "raw_response_received": raw_response if raw_response else "N/A",
        "parsed_narrative": parsed_narrative if parsed_narrative else "N/A",
        "parsed_actions": parsed_actions if parsed_actions else [],
        "error_during_interaction": error_message if error_message else "None"
    }
    try:
        with open(ORACLE_LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"[LLM Interface Logging] Critical Error: Could not write to {ORACLE_LOG_FILE}. Error: {e}")

def _parse_llm_response(response_text: str) -> (str, List[Dict[str, Any]]):
    """Parses the LLM's raw response text to separate narrative from structured actions.

    Args:
        response_text (str): The raw string response from the LLM.

    Returns:
        Tuple[str, List[Dict[str, Any]]]: A tuple containing:
            - narrative (str): The textual response to be shown to the player.
            - actions (List[Dict[str, Any]]): A list of game action dictionaries.
    """
    narrative = []
    actions = []
    parts = response_text.split("ACTION::")

    if parts:
        narrative.append(parts[0].strip()) # First part is always narrative (or all of it if no ACTION)
        for part in parts[1:]:
            try:
                action_def = part.strip()
                # Expecting format: action_type::{json_details}
                action_type, json_details_str = action_def.split("::", 1)
                details = json.loads(json_details_str)
                actions.append({"action_type": action_type.strip(), "details": details})
            except json.JSONDecodeError as e:
                print(f"[LLM Interface] Error decoding JSON from LLM action: {json_details_str}. Error: {e}\"")
                narrative.append(f"(The Oracle's words concerning an action were muddled: {part.strip()})\"")
            except ValueError: # Not enough values to unpack (split didn't find "::")
                print(f"[LLM Interface] Malformed action string from LLM: {part.strip()}\"")
                narrative.append(f"(The Oracle made an unclear gesture: {part.strip()})\"")

    return " ".join(narrative).strip(), actions

def handle_game_event(event_data: Dict[str, Any], game_state: Any) -> Optional[List[Dict[str, Any]]]: # Added game_state
    """Processes a single game event, potentially triggering LLM interaction.

    Args:
        event_data (Dict[str, Any]): The event data dictionary.
        game_state (GameState): The current game state, providing context and API config.

    Returns:
        Optional[List[Dict[str, Any]]]: A list of action dictionaries or None.
    """
    event_type = event_data.get("type")
    details = event_data.get("details", {})
    
    print(f"[LLM Interface] Received event: {event_type} - Details: {details}")

    actions_to_execute = []
    
    if event_type == "ORACLE_QUERY" and game_state.oracle_config:
        player_query = details.get("query_text")
        oracle_name = details.get("oracle_name", "The Oracle") # Get oracle name if available

        if not player_query:
            print("[LLM Interface] No query text found in ORACLE_QUERY event.\"")
            # Optionally, return an action to display a message to the player
            actions_to_execute.append({
                "action_type": "add_oracle_dialogue", 
                "details": {"text": "(You offer your thoughts, but no words escape.)"}
            })
            return actions_to_execute

        # 1. Construct the prompt
        # System Message / Preamble
        system_message = (
            f"You are {oracle_name}, a wise, ancient, and somewhat cryptic Oracle in the Fungi Fortress. "
            "Respond to the player's query with insightful, thematic, and sometimes enigmatic guidance. "
            "Your responses should be a single paragraph. "
            "If you wish to suggest a game event or action, embed it in your response using the format: "
            "ACTION::action_type::{'json_key': 'json_value'}. For example: "
            "ACTION::add_message::{'text': 'A strange energy emanates from the east.'} or "
            "ACTION::spawn_character::{'type': 'Mystic Fungoid', 'name': 'Glimmercap', 'x': 10, 'y': 12}. "
            "Ensure the JSON is valid."
        )

        # Game Context (Simplified for now, expand as needed)
        # TODO: Selectively add more game state details for better LLM context
        context = ""
        history_context = ""
        history_slice = 0

        if game_state.oracle_config:
            level = game_state.oracle_config.context_level
            if level == "low":
                context = f"Tick: {game_state.tick}. Player depth: {game_state.depth}. "
                # Minimal history, e.g., last 1 exchange or specific event
                history_slice = 1 
            elif level == "high":
                context = f"Tick: {game_state.tick}. Player depth: {game_state.depth}. "
                if game_state.mission:
                    context += f"Mission: {game_state.mission.get('description', 'Unclear')}. "
                context += f"Player resources: {game_state.player_resources}. "
                # Potentially add: game_state.get_visible_entities_summary() etc.
                # Potentially add: game_state.recent_significant_events_summary()
                history_slice = 5
            else: # Medium or default
                context = f"Tick: {game_state.tick}. Player depth: {game_state.depth}. "
                if game_state.mission:
                    context += f"Mission: {game_state.mission.get('description', 'Unclear')}. "
                history_slice = 3
        else: # Should not happen if called via ORACLE_QUERY due to earlier check, but as a fallback
            context = f"Tick: {game_state.tick}. Player depth: {game_state.depth}. "
            history_slice = 3

        # Interaction History
        if history_slice > 0:
            history_context = "\n".join([
                f"Player: {h['player']}\nOracle: {h['oracle']}" 
                for h in game_state.oracle_llm_interaction_history[-history_slice:]
            ])
        else:
            history_context = "No interaction history provided for this query."


        prompt = f"{system_message}\n\nGame Context: {context}\n\nInteraction History:\n{history_context}\n\nPlayer Query: {player_query}\""

        # 2. Send prompt to LLM API
        api_key = game_state.oracle_config.api_key
        model_name = game_state.oracle_config.model_name # Assuming model_name is in OracleConfig
        
        timestamp_utc = datetime.datetime.now(timezone.utc).isoformat()
        # Ensure Z is added if not present, isoformat for timezone.utc often ends with +00:00
        if "+00:00" in timestamp_utc:
            timestamp_utc = timestamp_utc.replace("+00:00", "Z")
        elif not timestamp_utc.endswith("Z"): # Fallback if isoformat is different
            timestamp_utc += "Z"

        llm_response_text = None
        parsed_narrative_for_log = None
        parsed_actions_for_log = None
        error_for_log = None

        try:
            llm_response_text = _call_llm_api(prompt, api_key, model_name)

            if llm_response_text:
                # 3. Parse LLM response
                narrative, llm_actions = _parse_llm_response(llm_response_text)
                parsed_narrative_for_log = narrative
                parsed_actions_for_log = llm_actions
                
                # Add narrative to be displayed in the Oracle dialogue
                if narrative:
                    actions_to_execute.append({
                        "action_type": "add_oracle_dialogue", 
                        "details": {"text": narrative, "is_llm_response": True} # Flag for renderer
                    })
                
                # Add any game actions suggested by the LLM
                if llm_actions:
                    actions_to_execute.extend(llm_actions)
                    print(f"[LLM Interface] Parsed actions from LLM: {llm_actions}")

                # Update interaction history (only on successful parse)
                game_state.oracle_llm_interaction_history.append({"player": player_query, "oracle": narrative})
                if len(game_state.oracle_llm_interaction_history) > 10: # Limit history size
                    game_state.oracle_llm_interaction_history.pop(0)

            else: # Handles cases where _call_llm_api returns None or an empty string implicitly treated as an error/no meaningful response
                error_message = "The Oracle seems unable to connect to the cosmic echoes at this moment (empty or no response from API)."
                error_for_log = error_message # Log this specific situation
                actions_to_execute.append({
                    "action_type": "add_oracle_dialogue", 
                    "details": {"text": error_message, "is_llm_response": True}
                })
                game_state.oracle_llm_interaction_history.append({"player": player_query, "oracle": error_message})
        
        except Exception as e: # Catch unexpected errors from _call_llm_api itself if it raises one
            error_message = f"A critical error occurred while communicating with the Oracle. Details: {str(e)}"
            error_for_log = error_message # Log this exception
            print(f"[LLM Interface] Critical error during LLM call processing: {e}")
            actions_to_execute.append({
                "action_type": "add_oracle_dialogue",
                "details": {"text": "The Oracle's connection is severely disrupted. Please check the logs.", "is_llm_response": True}
            })
            # Optionally, add a placeholder to history or handle as per game design
            game_state.oracle_llm_interaction_history.append({"player": player_query, "oracle": "Severe connection disruption."})

        # Log the interaction details
        _log_oracle_interaction(
            timestamp=timestamp_utc,
            player_query=player_query,
            prompt=prompt,
            raw_response=llm_response_text, # This will be the error message string if _call_llm_api returned one
            parsed_narrative=parsed_narrative_for_log, # Will be None if parsing didn't happen
            parsed_actions=parsed_actions_for_log,   # Will be None if parsing didn't happen
            error_message=error_for_log
        )

        # Transition Oracle state back to awaiting prompt or similar, via an action if needed
        # This might be handled by game_logic after processing these actions
        actions_to_execute.append({"action_type": "set_oracle_state", "details": {"state": "AWAITING_PROMPT"}})
        return actions_to_execute

    # For other events, or if not an Oracle query, just log and return nothing for now
    return None 

# Example of how this might be called from game_logic.py:
#
# import llm_interface
# ...
# game_events = game_state.consume_events()
# all_llm_actions = []
# for event in game_events:
#     # Pass game_state to handle_game_event
#     llm_actions = llm_interface.handle_game_event(event, self.game_state) 
#     if llm_actions:
#         all_llm_actions.extend(llm_actions)
# 
# # Process all_llm_actions in game logic... 