# llm_interface.py
"""Interface for connecting game events and actions to an LLM.

This module will contain functions to:
- Process game events.
- Format requests for an LLM.
- Parse LLM responses.
- Translate LLM responses into game actions or data structures.
"""

import json # Added for parsing LLM responses that might include JSON
from typing import List, Dict, Optional, Any

# Import GameEvent and GameState if defined elsewhere for type hinting
# from .game_state import GameEvent, GameState # Assuming GameEvent is defined there
# from .config_manager import OracleConfig # For API key access

# Placeholder for an actual LLM API call function
# In a real scenario, this would involve libraries like 'requests' or a specific LLM provider's SDK
def _call_llm_api(prompt: str, api_key: str, model_name: Optional[str] = None) -> Optional[str]:
    """Placeholder for making an API call to an LLM.
    
    Args:
        prompt (str): The complete prompt to send to the LLM.
        api_key (str): The API key for the LLM service.
        model_name (Optional[str]): The specific model to use (if any).

    Returns:
        Optional[str]: The LLM's response string, or None if an error occurs.
    """
    print(f"[LLM API Call] Sending prompt (first 100 chars): {prompt[:100]}...\"")
    print(f"[LLM API Call] Using API Key: {'*' * (len(api_key) - 4) + api_key[-4:] if api_key else 'NOT_CONFIGURED'}\"")
    if not api_key or api_key == "testkey123": # Basic check
        print("[LLM API Call] Error: API key is missing or is a placeholder.\"")
        # In a real scenario, you might return a specific error message or raise an exception
        return "The Oracle\'s connection is disrupted. (Error: API Key not configured for LLM)"

    # --- SIMULATED LLM RESPONSE ---
    # This is where you would make the actual HTTP request to the LLM API.
    # For now, we'll simulate a response based on the prompt.
    if "what is my purpose" in prompt.lower():
        return "The Oracle ponders... \"Your purpose is intertwined with the fate of this fortress. Seek the Shimmering Fungus, and you shall understand more.\""
    elif "rare herb" in prompt.lower():
        return "The Oracle\'s voice resonates: \"The Bloodshroom you seek... it often sprouts near ancient stones. Look to the east. ACTION::add_message::{'text': 'You recall seeing ancient stones to the east.'}}"
    elif "dangers" in prompt.lower() and "mushroom forest" in prompt.lower():
        return "The Oracle whispers: \"The mushroom forest is home to the Spore-Fiends, creatures of shadow and decay. Tread carefully. ACTION::spawn_character::{'type': 'Spore-Fiend', 'name': 'Menacing Spore-Fiend', 'x': 15, 'y': 20} ACTION::add_message::{'text': 'A Spore-Fiend has been disturbed in the mushroom forest!'}}"
    
    # Default simulated response
    return "The Oracle\'s thoughts swirl like mist... \"The patterns of fate are ever-shifting. Your query is noted, but clarity eludes even me at this moment.\""
    # --- END SIMULATED LLM RESPONSE ---

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
        context = f"Current game tick: {game_state.tick}. Player is at depth: {game_state.depth}. "
        if game_state.mission:
             context += f"Current mission: {game_state.mission.get('description', 'Unclear')}. "
        
        # Interaction History (last few exchanges)
        history_context = "\\n".join([f"Player: {h['player']}\\nOracle: {h['oracle']}" for h in game_state.oracle_llm_interaction_history[-3:]]) # Last 3 exchanges

        prompt = f"{system_message}\\n\\nGame Context: {context}\\n\\nInteraction History:\\n{history_context}\\n\\nPlayer Query: {player_query}\""

        # 2. Send prompt to LLM API
        api_key = game_state.oracle_config.api_key
        model_name = game_state.oracle_config.model_name # Assuming model_name is in OracleConfig
        
        llm_response_text = _call_llm_api(prompt, api_key, model_name)

        if llm_response_text:
            # 3. Parse LLM response
            narrative, llm_actions = _parse_llm_response(llm_response_text)
            
            # Add narrative to be displayed in the Oracle dialogue
            if narrative:
                actions_to_execute.append({
                    "action_type": "add_oracle_dialogue", 
                    "details": {"text": narrative, "is_llm_response": True} # Flag for renderer
                })
            
            # Add any game actions suggested by the LLM
            if llm_actions:
                actions_to_execute.extend(llm_actions)
                print(f"[LLM Interface] Parsed actions from LLM: {llm_actions}\"")

            # Update interaction history
            game_state.oracle_llm_interaction_history.append({"player": player_query, "oracle": narrative})
            # Limit history size
            if len(game_state.oracle_llm_interaction_history) > 10:
                game_state.oracle_llm_interaction_history.pop(0)

        else:
            # Handle no response or API error
            error_message = "The Oracle seems unable to connect to the cosmic echoes at this moment."
            actions_to_execute.append({
                "action_type": "add_oracle_dialogue", 
                "details": {"text": error_message, "is_llm_response": True}
            })
            game_state.oracle_llm_interaction_history.append({"player": player_query, "oracle": error_message})


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