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
from typing import List, Dict, Optional, Any, Iterator, Union
import datetime # Added for timestamping logs
from datetime import timezone # Explicitly import timezone
import time # Added for retry delays
from pathlib import Path # Added for file management
import sys # Added for fallback print in _log_oracle_interaction
import logging # MODIFIED: Import logging

# Import the new text streaming engine
from fungi_fortress.text_streaming import text_streaming_engine
from fungi_fortress.config_manager import detect_provider_from_model # ADDED THIS IMPORT

# Get a logger instance for this module
logger = logging.getLogger(__name__) # NEW: Define logger for this module

# Support for multiple LLM providers
try:
    from groq import Groq, RateLimitError, APIConnectionError, APIStatusError
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    RateLimitError = Exception
    APIConnectionError = Exception
    APIStatusError = Exception

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Import GameEvent and GameState if defined elsewhere for type hinting
# from .game_state import GameEvent, GameState # Assuming GameEvent is defined there
# from .config_manager import OracleConfig # For API key access

# --- Logging Setup ---
# LLM_INTERACTIONS_LOG_FILE = "llm_interactions.log" # MODIFIED: No longer directly used by _log_debug_message

def _log_debug_message(category: str, message: str):
    """Internal logging function to write debug messages using the root logger."""
    try:
        # The logger configured in main.py will handle timestamp, level, module, etc.
        logger.info(f"[{category}] {message}") # MODIFIED: Use logger.info
    except Exception as e:
        # Fallback if logger itself fails (highly unlikely if basicConfig worked)
        try:
            print(f"LOGGER_FALLBACK_ERROR: Category: {category}, Message: {message}. Error: {e}", file=sys.stderr)
        except Exception:
            pass # Final fallback

# --- Request Tracking for Cost Control ---
# REMOVED: All API limit logic as requested by user

# --- Streaming Support ---

def _call_xai_api_streaming(prompt: str, api_key: str, model_name: str, max_tokens: int = 500, timeout_seconds: int = 30, use_structured_output: bool = True) -> Iterator[str]:
    """Makes a streaming API call to XAI using the OpenAI SDK with XAI-specific parameters.
    
    Args:
        prompt (str): The complete prompt to send to the LLM.
        api_key (str): The XAI API key.
        model_name (str): The specific XAI model to use.
        max_tokens (int): Maximum tokens in response.
        timeout_seconds (int): Request timeout in seconds.
        use_structured_output (bool): Whether to use XAI's structured output feature.
        
    Yields:
        str: Chunks of the LLM's response as they arrive.
    """
    _log_debug_message("XAI API", "_call_xai_api_streaming entered.")
    if not OPENAI_AVAILABLE:
        _log_debug_message("XAI API", "OPENAI_AVAILABLE is False, yielding error.")
        yield "Error: openai library required for XAI API calls"
        return
    _log_debug_message("XAI API", "OPENAI_AVAILABLE is True, proceeding.")
    
    try:
        # Create XAI client using OpenAI SDK
        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
            timeout=timeout_seconds
        )
        
        # Prepare messages with proper role distinction
        if "You are " in prompt and "\n\nGame Context:" in prompt:
            parts = prompt.split("\n\nGame Context:", 1)
            system_content = parts[0]
            user_content = "Game Context:" + parts[1] if len(parts) > 1 else ""
            
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ]
        else:
            messages = [{"role": "user", "content": prompt}]
        
        # Prepare completion parameters
        completion_params = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max(max_tokens, 500),
            "temperature": 0.7,
            "stream": True  # Enable streaming
        }
        
        # Add reasoning effort for grok-3-mini models
        if "grok-3-mini" in model_name.lower():
            completion_params["reasoning_effort"] = "high"
        
        # Note: Structured output may not work with streaming, so we'll handle it differently
        if use_structured_output:
            # For streaming, we'll need to parse the JSON from the complete response
            # We'll collect the stream and then parse it
            _log_debug_message("XAI API", "Structured output requested with streaming - will parse after collection")
        
        # Make the streaming API call
        _log_debug_message("XAI API", f"Making streaming request to model: {model_name}")
        stream = client.chat.completions.create(**completion_params)
        
        _log_debug_message("XAI API", f"Stream object received: {type(stream)}")

        collected_content = ""
        content_yielded = False
        for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content:
                    content_chunk = delta.content
                    collected_content += content_chunk
                    yield content_chunk
                    content_yielded = True
        
        if not content_yielded:
            _log_debug_message("XAI API", "Stream iteration completed but no content was yielded.")

        # Log final response for debugging
        _log_debug_message("XAI API", f"Streaming complete. Total content: {len(collected_content)} chars")
        
    except Exception as e:
        error_msg = f"Error during streaming: {e}"
        _log_debug_message("XAI API", error_msg)
        yield f"Error: {error_msg}"

def _call_openai_compatible_api_streaming(prompt: str, api_key: str, model_name: str, base_url: str = None, max_tokens: int = 500, timeout_seconds: int = 30) -> Iterator[str]:
    """Makes a streaming API call using OpenAI-compatible format.
    
    Args:
        prompt (str): The complete prompt to send to the LLM.
        api_key (str): The API key for the service.
        model_name (str): The specific model to use.
        base_url (str): Base URL for the API (defaults to OpenAI).
        max_tokens (int): Maximum tokens in response.
        timeout_seconds (int): Request timeout in seconds.
        
    Yields:
        str: Chunks of the LLM's response as they arrive.
    """
    if not OPENAI_AVAILABLE:
        yield "Error: openai library not available for API calls."
        return
        
    try:
        client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds
        )
        
        stream = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model_name,
            max_tokens=max_tokens,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content:
                    yield delta.content
        
    except openai.RateLimitError:
        yield f"OpenAI API Rate Limited: Please wait before making more requests."
    except openai.APITimeoutError:
        yield f"OpenAI API Error: Request timed out after {timeout_seconds} seconds."
    except openai.APIConnectionError:
        yield f"OpenAI API Error: Connection failed."
    except openai.AuthenticationError:
        yield f"OpenAI API Error: Invalid API key or authentication failed."
    except Exception as e:
        yield f"OpenAI-compatible API Error: {str(e)}"

def _call_groq_api_streaming(prompt: str, api_key: str, model_name: str, max_tokens: int = 500, timeout_seconds: int = 30) -> Iterator[str]:
    """Makes a streaming API call to Groq using their SDK.
    
    Args:
        prompt (str): The complete prompt to send to the LLM.
        api_key (str): The Groq API key.
        model_name (str): The specific model to use.
        max_tokens (int): Maximum tokens in response.
        timeout_seconds (int): Request timeout in seconds.
        
    Yields:
        str: Chunks of the LLM's response as they arrive.
    """
    if not GROQ_AVAILABLE:
        yield "Error: Groq library not available."
        return
        
    try:
        client = Groq(api_key=api_key, timeout=timeout_seconds)
        
        stream = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model_name,
            max_tokens=max_tokens,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content:
                    yield delta.content
        
    except RateLimitError:
        yield f"Groq API Rate Limited: Please wait before making more requests."
    except APIConnectionError:
        yield f"Groq API Error: Connection failed."
    except APIStatusError as e:
        yield f"Groq API Error: {e}"
    except Exception as e:
        yield f"Groq API Error: {str(e)}"

def _call_xai_api(prompt: str, api_key: str, model_name: str, max_tokens: int = 500, timeout_seconds: int = 30, use_structured_output: bool = True) -> Optional[str]:
    """Makes an API call to XAI using the OpenAI SDK with XAI-specific parameters.
    
    Args:
        prompt (str): The complete prompt to send to the LLM.
        api_key (str): The XAI API key.
        model_name (str): The specific XAI model to use.
        max_tokens (int): Maximum tokens in response.
        timeout_seconds (int): Request timeout in seconds.
        use_structured_output (bool): Whether to use XAI's structured output feature.
        
    Returns:
        Optional[str]: The LLM's response string, or None if an error occurs.
    """
    if not OPENAI_AVAILABLE:
        return "Error: openai library required for XAI API calls"
    
    try:
        # Create XAI client using OpenAI SDK
        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
            timeout=timeout_seconds
        )
        
        # Prepare messages with proper role distinction
        # Split the prompt into system and user messages for better performance
        if "You are " in prompt and "\n\nGame Context:" in prompt:
            # Extract system message and user content
            parts = prompt.split("\n\nGame Context:", 1)
            system_content = parts[0]
            user_content = "Game Context:" + parts[1] if len(parts) > 1 else ""
            
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ]
        else:
            # Fallback: treat entire prompt as user message
            messages = [{"role": "user", "content": prompt}]
        
        # Prepare completion parameters
        completion_params = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max(max_tokens, 500),  # Ensure at least 500 tokens for grok-3-mini
            "temperature": 0.7  # Use the XAI example temperature
        }
        
        # Add reasoning effort for grok-3-mini models
        if "grok-3-mini" in model_name.lower():
            completion_params["reasoning_effort"] = "high"  # Use high for better responses
        
        # Add structured output schema if enabled
        if use_structured_output:
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
            completion_params["response_format"] = oracle_schema
        
        # Make the API call
        _log_debug_message("XAI API", f"Making request to model: {model_name}")
        completion = client.chat.completions.create(**completion_params)
        
        # Extract response content
        message = completion.choices[0].message
        content = message.content
        
        # For grok-3-mini models, handle reasoning content as per XAI example
        if "grok-3-mini" in model_name.lower():
            # Log reasoning content if available
            if hasattr(message, 'reasoning_content') and message.reasoning_content:
                reasoning = message.reasoning_content
                _log_debug_message("XAI API", f"Reasoning Content: {reasoning[:200]}..." if len(reasoning) > 200 else f"Reasoning Content: {reasoning}")
            
            # Log usage information
            if completion.usage:
                _log_debug_message("XAI API", f"Completion tokens: {completion.usage.completion_tokens}")
                # Log reasoning token usage if available (grok-3-mini specific)
                if hasattr(completion.usage, 'completion_tokens_details') and completion.usage.completion_tokens_details:
                    _log_debug_message("XAI API", f"Reasoning tokens: {completion.usage.completion_tokens_details.reasoning_tokens}")
        
        # Log final response for debugging
        _log_debug_message("XAI API", f"Final Response: {content[:200]}..." if content and len(content) > 200 else f"Final Response: {content}")
        
        if not content:
            _log_debug_message("XAI API", f"Warning: Empty response from {model_name}")
            return "Error: Empty response from LLM"
        
        return content
        
    except RateLimitError as e:
        error_msg = f"Rate limit exceeded: {e}"
        _log_debug_message("XAI API", error_msg)
        return f"Error: {error_msg}"
    except APIConnectionError as e:
        error_msg = f"Connection error: {e}"
        _log_debug_message("XAI API", error_msg)
        return f"Error: {error_msg}"
    except APIStatusError as e:
        error_msg = f"API status error: {e}"
        _log_debug_message("XAI API", error_msg)
        return f"Error: {error_msg}"
    except Exception as e:
        _log_debug_message("XAI API", f"Error: {e}")
        return f"Error: Unexpected error - {e}"

def _call_openai_compatible_api(prompt: str, api_key: str, model_name: str, base_url: str = None, max_tokens: int = 500, timeout_seconds: int = 30) -> Optional[str]:
    """Makes an API call using OpenAI-compatible format (works with many providers).
    
    Args:
        prompt (str): The complete prompt to send to the LLM.
        api_key (str): The API key for the service.
        model_name (str): The specific model to use.
        base_url (str): Base URL for the API (defaults to OpenAI).
        max_tokens (int): Maximum tokens in response.
        timeout_seconds (int): Request timeout in seconds.
        
    Returns:
        Optional[str]: The LLM's response string, or None if an error occurs.
    """
    if not OPENAI_AVAILABLE:
        return "Error: openai library not available for API calls."
        
    try:
        client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds
        )
        
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model_name,
            max_tokens=max_tokens
        )
        
        return response.choices[0].message.content
        
    except openai.RateLimitError:
        return f"OpenAI API Rate Limited: Please wait before making more requests."
    except openai.APITimeoutError:
        return f"OpenAI API Error: Request timed out after {timeout_seconds} seconds."
    except openai.APIConnectionError:
        return f"OpenAI API Error: Connection failed."
    except openai.AuthenticationError:
        return f"OpenAI API Error: Invalid API key or authentication failed."
    except Exception as e:
        return f"OpenAI-compatible API Error: {str(e)}"

def _call_groq_api(prompt: str, api_key: str, model_name: str, max_tokens: int = 500, timeout_seconds: int = 30) -> Optional[str]:
    """Makes an API call to Groq using their SDK.
    
    Args:
        prompt (str): The complete prompt to send to the LLM.
        api_key (str): The Groq API key.
        model_name (str): The specific model to use.
        max_tokens (int): Maximum tokens in response.
        timeout_seconds (int): Request timeout in seconds.
        
    Returns:
        Optional[str]: The LLM's response string, or None if an error occurs.
    """
    if not GROQ_AVAILABLE:
        return "Error: Groq library not available."
        
    try:
        client = Groq(api_key=api_key, timeout=timeout_seconds)
        
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model_name,
            max_tokens=max_tokens
        )
        
        return chat_completion.choices[0].message.content
        
    except RateLimitError:
        return f"Groq API Rate Limited: Please wait before making more requests."
    except Exception as e:
        # Handle timeouts and connection errors generically since Groq SDK may not have specific exception types
        error_str = str(e).lower()
        if "timeout" in error_str:
            return f"Groq API Error: Request timed out after {timeout_seconds} seconds."
        elif "connection" in error_str or "network" in error_str:
            return f"Groq API Error: Connection failed."
        else:
            return f"Groq API Error: {str(e)}"

def _detect_provider_and_call_api_streaming(prompt: str, api_key: str, model_name: str, provider_hint: str = None, 
                                           llm_config = None) -> Iterator[str]:
    """Detects the provider based on model name and makes appropriate streaming API call with safety features.
    
    Args:
        prompt (str): The complete prompt to send to the LLM.
        api_key (str): The API key for the LLM service.
        model_name (str): The specific model to use.
        provider_hint (str): Optional hint about which provider to use.
        llm_config: LLM configuration object with safety settings.
        
    Yields:
        str: Chunks of the LLM's response as they arrive.
    """
    _log_debug_message("LLM API Call", f"Sending streaming prompt (first 100 chars): {prompt[:100]}...")
    _log_debug_message("LLM API Call", f"Using API Key: {'*' * (len(api_key) - 4) + api_key[-4:] if api_key and len(api_key) > 4 else 'KEY_TOO_SHORT_OR_INVALID'}")
    _log_debug_message("LLM API Call", f"Using Model: {model_name}")
    _log_debug_message("LLM API Call", f"Provider Hint: {provider_hint}")

    if not api_key or api_key == "YOUR_API_KEY_HERE" or api_key == "testkey123":
        error_msg = "Error: API key is missing, a placeholder, or the test key. Configure llm_config.ini."
        _log_debug_message("LLM API Call", error_msg)
        yield f"The Oracle's connection is disrupted. (Error: API Key not configured for LLM. Details: {error_msg})"
        return

    if not model_name:
        error_msg = "Error: Model name not specified in llm_config.ini."
        _log_debug_message("LLM API Call", error_msg)
        yield f"The Oracle's connection is unstable. (Error: LLM Model not specified. Details: {error_msg})"
        return

    # Get safety settings from config
    max_tokens = 500
    timeout_seconds = 30

    if llm_config:
        max_tokens = getattr(llm_config, 'max_tokens', 500)
        timeout_seconds = getattr(llm_config, 'timeout_seconds', 30)

    # Auto-detect provider if not provided
    if provider_hint == "auto" or not provider_hint:
        _log_debug_message("LLM API Call", f"Before calling detect_provider_from_model. Model: {model_name}")
        provider_hint = detect_provider_from_model(model_name)
        _log_debug_message("LLM API Call", f"After calling detect_provider_from_model. Detected: {provider_hint}")

    # Validate safety limits
    if max_tokens <= 0 or max_tokens > 4000:
        _log_debug_message("LLM API Call", f"max_tokens {max_tokens} outside safe range, using 500")
        max_tokens = 500
    if timeout_seconds <= 0 or timeout_seconds > 120:
        _log_debug_message("LLM API Call", f"timeout_seconds {timeout_seconds} outside safe range, using 30")
        timeout_seconds = 30

    # Determine structured output setting
    use_structured_output = getattr(llm_config, 'enable_structured_outputs', True)

    _log_debug_message("LLM API Dispatch", f"About to enter provider dispatch try block. Provider: {provider_hint}")
    try:
        if provider_hint == "xai":
            _log_debug_message("LLM API Dispatch", "Dispatching to XAI streaming.")
            _log_debug_message("LLM API Dispatch", "Attempting to iterate over _call_xai_api_streaming.")
            xai_stream_iterated = False
            for chunk in _call_xai_api_streaming(prompt, api_key, model_name, max_tokens, timeout_seconds, use_structured_output):
                yield chunk
                xai_stream_iterated = True
            if not xai_stream_iterated:
                _log_debug_message("LLM API Dispatch", "_call_xai_api_streaming loop did not yield any chunks.")
        elif provider_hint == "openai":
            _log_debug_message("LLM API Dispatch", "Dispatching to OpenAI streaming.")
            for chunk in _call_openai_compatible_api_streaming(prompt, api_key, model_name, None, max_tokens, timeout_seconds):
                yield chunk
        elif provider_hint == "groq":
            _log_debug_message("LLM API Dispatch", "Dispatching to Groq streaming.")
            for chunk in _call_groq_api_streaming(prompt, api_key, model_name, max_tokens, timeout_seconds):
                yield chunk
        elif provider_hint == "anthropic":
            _log_debug_message("LLM API Dispatch", "Dispatching to Anthropic (non-streaming fallback).")
            # Anthropic streaming not implemented yet, fall back to non-streaming
            response = _call_anthropic_api(prompt, api_key, model_name, max_tokens, timeout_seconds)
            if response:
                yield response
            else:
                yield "The Oracle's connection to the Anthropic realm has failed."
        elif provider_hint == "together":
            _log_debug_message("LLM API Dispatch", "Dispatching to Together streaming.")
            for chunk in _call_openai_compatible_api_streaming(prompt, api_key, model_name, "https://api.together.xyz/v1", max_tokens, timeout_seconds):
                yield chunk
        elif provider_hint == "perplexity":
            _log_debug_message("LLM API Dispatch", "Dispatching to Perplexity streaming.")
            for chunk in _call_openai_compatible_api_streaming(prompt, api_key, model_name, "https://api.perplexity.ai", max_tokens, timeout_seconds):
                yield chunk
        else:
            error_msg = f"Unknown provider: {provider_hint}"
            _log_debug_message("LLM API Call", error_msg)
            yield f"The Oracle's connection is confused. (Error: {error_msg})"
            
    except Exception as e:
        error_msg = f"Streaming API call failed: {str(e)}"
        _log_debug_message("LLM API Call", error_msg)
        yield f"The Oracle's voice falters... (Error: {error_msg})"

def _call_llm_api_streaming(prompt: str, api_key: str, model_name: Optional[str] = None, provider: str = None, llm_config = None) -> Iterator[str]:
    """Calls the appropriate LLM API for streaming responses.
    
    Args:
        prompt (str): The prompt to send to the LLM.
        api_key (str): The API key for the LLM service.
        model_name (Optional[str]): The model to use.
        provider (str): The provider to use.
        llm_config: LLM configuration object with safety settings.
        
    Yields:
        str: Chunks of the LLM's response as they arrive.
    """
    for chunk in _detect_provider_and_call_api_streaming(prompt, api_key, model_name, provider, llm_config):
        yield chunk

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
    
    _log_debug_message("LLM Interface", f"Received event: {event_type} - Details: {details}")

    actions_to_execute = []
    
    if event_type == "ORACLE_QUERY" and game_state.llm_config:
        # Check if streaming is enabled
        enable_streaming = getattr(game_state.llm_config, 'enable_streaming', True)
        
        if enable_streaming:
            return handle_oracle_query_streaming(event_data, game_state)
        else:
            return handle_oracle_query_non_streaming(event_data, game_state)

    # For other events, or if not an Oracle query, just log and return nothing for now
    return None 

def handle_oracle_query_streaming(event_data: Dict[str, Any], game_state: Any) -> Optional[List[Dict[str, Any]]]:
    """Handles Oracle queries with streaming responses using the new text streaming engine."""
    details = event_data.get("details", {})
    player_query = details.get("query_text")
    oracle_name = details.get("oracle_name", "The Oracle")
    
    actions_to_execute = []

    if not player_query:
        _log_debug_message("LLM Interface", "[LLM Interface] No query text found in ORACLE_QUERY event.")
        actions_to_execute.append({
            "action_type": "add_oracle_dialogue", 
            "details": {"text": "(You offer your thoughts, but no words escape.)"}
        })
        return actions_to_execute

    # Construct the prompt
    base_system_message = (
        f"You are {oracle_name}, a wise, ancient, and somewhat cryptic Oracle in the Fungi Fortress. "
        "Respond to the player's query with insightful, thematic, and sometimes enigmatic guidance. "
        "Your responses should be a single paragraph. "
    )

    action_instructions = ""
    if game_state.llm_config and getattr(game_state.llm_config, 'enable_structured_outputs', False):
        action_instructions = (
            "Your entire response MUST be a single JSON object. This JSON object must have two keys: "
            "\\'narrative\\' (string) and \\'actions\\' (array). "
            "The 'narrative' should contain your textual response to the player. "
            "The 'actions' array should contain any game actions to execute. Each action in the array "
            "must be an object with 'action_type' (string) and 'details' (object) keys. "
            "Example of a complete response: "
            '{"narrative": "A strange energy emanates from the east.", "actions": [{"action_type": "add_message", "details": {"text": "Energy pulse detected."}}]} '
            "If no actions are needed, provide an empty array for 'actions'. Do not use any other format."
        )
    else:
        action_instructions = (
            "If you wish to suggest a game event or action, embed it in your response using the format: "
            "ACTION::action_type::{{\\\"json_key\\\": \\\"json_value\\\"}}. For example: "
            "ACTION::add_message::{{\\\"text\\\": \\\"A strange energy emanates from the east.\\\"}} or "
            "ACTION::spawn_character::{{\\\"type\\\": \\\"Mystic Fungoid\\\", \\\"name\\\": \\\"Glimmercap\\\", \\\"x\\\": 10, \\\"y\\\": 12}}. "
            "Use double quotes in JSON and ensure the JSON is valid. Actions are optional - only include them if meaningful to your response."
        )
    
    system_message = base_system_message + action_instructions

    # Build context (same logic as before)
    context = ""
    history_context = ""
    history_slice = 0

    if game_state.llm_config:
        level = game_state.llm_config.context_level
        if level == "low":
            context = f"Tick: {game_state.tick}. Player depth: {game_state.depth}. "
            history_slice = 1 
        elif level == "high":
            context = f"Tick: {game_state.tick}. Player depth: {game_state.depth}. "
            if game_state.mission:
                context += f"Mission: {game_state.mission.get('description', 'Unclear')}. "
            context += f"Player resources: {game_state.player_resources}. "
            history_slice = 5
        else: # Medium or default
            context = f"Tick: {game_state.tick}. Player depth: {game_state.depth}. "
            if game_state.mission:
                context += f"Mission: {game_state.mission.get('description', 'Unclear')}. "
            history_slice = 3
    else:
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

    # Get API configuration
    api_key = game_state.llm_config.api_key
    model_name = game_state.llm_config.model_name
    provider_hint = game_state.llm_config.provider if hasattr(game_state.llm_config, 'provider') else None

    # Start the new streaming system with flavor text and proper separation
    actions_to_execute.append({
        "action_type": "start_enhanced_oracle_streaming",
        "details": {
            "prompt": prompt,
            "api_key": api_key,
            "model_name": model_name,
            "provider_hint": provider_hint,
            "llm_config": game_state.llm_config,
            "player_query": player_query,
            "oracle_name": oracle_name
        }
    })

    return actions_to_execute

def handle_oracle_query_non_streaming(event_data: Dict[str, Any], game_state: Any) -> Optional[List[Dict[str, Any]]]:
    """Handles Oracle queries with non-streaming responses (original implementation)."""
    details = event_data.get("details", {})
    player_query = details.get("query_text")
    oracle_name = details.get("oracle_name", "The Oracle")
    
    actions_to_execute = []

    if not player_query:
        _log_debug_message("LLM Interface", "[LLM Interface] No query text found in ORACLE_QUERY event.")
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
        "ACTION::action_type::{{\"json_key\": \"json_value\"}}. For example: "
        "ACTION::add_message::{{\"text\": \"A strange energy emanates from the east.\"}} or "
        "ACTION::spawn_character::{{\"type\": \"Mystic Fungoid\", \"name\": \"Glimmercap\", \"x\": 10, \"y\": 12}}. "
        "Use double quotes in JSON and ensure the JSON is valid. Actions are optional - only include them if meaningful to your response."
    )

    # Game Context (Simplified for now, expand as needed)
    # TODO: Selectively add more game state details for better LLM context
    context = ""
    history_context = ""
    history_slice = 0

    if game_state.llm_config:
        level = game_state.llm_config.context_level
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
    api_key = game_state.llm_config.api_key
    model_name = game_state.llm_config.model_name # Assuming model_name is in LLMConfig
    
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
        provider_hint = game_state.llm_config.provider if hasattr(game_state.llm_config, 'provider') else None
        llm_response_text = _call_llm_api(prompt, api_key, model_name, provider_hint, game_state.llm_config)

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
                _log_debug_message("LLM Interface", f"Parsed actions from LLM: {llm_actions}")

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
        _log_debug_message("LLM Interface", f"Critical error during LLM call processing: {e}")
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

def _call_with_retries(api_func, *args, max_retries: int = 2, retry_delay: float = 1.0, **kwargs) -> Optional[str]:
    """Wrapper to call API functions with retry logic and exponential backoff.
    
    Args:
        api_func: The API function to call
        *args: Arguments to pass to the API function
        max_retries: Maximum number of retry attempts
        retry_delay: Base delay between retries in seconds
        **kwargs: Keyword arguments to pass to the API function
        
    Returns:
        Optional[str]: The API response or error message
    """
    last_error = None
    
    for attempt in range(max_retries + 1):  # +1 for initial attempt
        try:
            result = api_func(*args, **kwargs)
            
            # Check if result indicates a rate limit or temporary error
            if result and isinstance(result, str):
                if "Rate Limited" in result or "timed out" in result or "Connection failed" in result:
                    if attempt < max_retries:
                        delay = retry_delay * (2 ** attempt)  # Exponential backoff
                        _log_debug_message("API Retry", f"Attempt {attempt + 1} failed with: {result[:100]}...")
                        _log_debug_message("API Retry", f"Waiting {delay:.1f} seconds before retry {attempt + 2}/{max_retries + 1}")
                        time.sleep(delay)
                        continue
                    else:
                        _log_debug_message("API Retry", f"Max retries ({max_retries}) exceeded. Final error: {result[:100]}...")
                        return result
            
            # Success or non-retryable error
            if attempt > 0:
                _log_debug_message("API Retry", f"Success on attempt {attempt + 1}")
            return result
            
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                delay = retry_delay * (2 ** attempt)
                _log_debug_message("API Retry", f"Attempt {attempt + 1} raised exception: {last_error}")
                _log_debug_message("API Retry", f"Waiting {delay:.1f} seconds before retry {attempt + 2}/{max_retries + 1}")
                time.sleep(delay)
            else:
                _log_debug_message("API Retry", f"Max retries ({max_retries}) exceeded. Final exception: {last_error}")
                return f"API Error after {max_retries + 1} attempts: {last_error}"
    
    return f"API Error after {max_retries + 1} attempts: {last_error}" 

def _detect_provider_and_call_api(prompt: str, api_key: str, model_name: str, provider_hint: str = None, 
                                  llm_config = None) -> Optional[str]:
    """Detects the provider based on model name and makes appropriate API call with safety features.
    
    Args:
        prompt (str): The complete prompt to send to the LLM.
        api_key (str): The API key for the LLM service.
        model_name (str): The specific model to use.
        provider_hint (str): Optional hint about which provider to use.
        llm_config: LLM configuration object with safety settings.
        
    Returns:
        Optional[str]: The LLM's response string, or None if an error occurs.
    """
    _log_debug_message("LLM API Call", f"Sending prompt (first 100 chars): {prompt[:100]}...")
    _log_debug_message("LLM API Call", f"Using API Key: {'*' * (len(api_key) - 4) + api_key[-4:] if api_key and len(api_key) > 4 else 'KEY_TOO_SHORT_OR_INVALID'}")
    _log_debug_message("LLM API Call", f"Using Model: {model_name}")
    _log_debug_message("LLM API Call", f"Provider Hint: {provider_hint}")

    if not api_key or api_key == "YOUR_API_KEY_HERE" or api_key == "testkey123":
        error_msg = "Error: API key is missing, a placeholder, or the test key. Configure llm_config.ini."
        _log_debug_message("LLM API Call", error_msg)
        return f"The Oracle's connection is disrupted. (Error: API Key not configured for LLM. Details: {error_msg})"

    if not model_name:
        error_msg = "Error: Model name not specified in llm_config.ini."
        _log_debug_message("LLM API Call", error_msg)
        return f"The Oracle's connection is unstable. (Error: LLM Model not specified. Details: {error_msg})"

    # Get safety settings from config
    max_tokens = 500
    timeout_seconds = 30
    max_retries = 2
    retry_delay = 1.0
    
    if llm_config:
        max_tokens = getattr(llm_config, 'max_tokens', 500)
        timeout_seconds = getattr(llm_config, 'timeout_seconds', 30)
        max_retries = getattr(llm_config, 'max_retries', 2)
        retry_delay = getattr(llm_config, 'retry_delay_seconds', 1.0)
    
    _log_debug_message("LLM API Call", f"Safety limits: max_tokens={max_tokens}, timeout={timeout_seconds}s, retries={max_retries}")

    # Determine provider based on model name or hint
    if provider_hint and provider_hint.lower() != "auto":
        provider = provider_hint.lower()
    elif model_name.startswith(("grok", "grok-")):
        provider = "xai"
    elif model_name.startswith(("gpt-", "text-", "davinci", "curie", "babbage", "ada")):
        provider = "openai"
    elif model_name.startswith(("claude-", "claude")):
        provider = "anthropic"
    elif model_name.startswith(("llama", "mixtral", "gemma")):
        provider = "groq"
    else:
        provider = "openai"
    
    _log_debug_message("LLM API Call", f"Detected provider: {provider}")
    
    try:
        if provider == "xai":
            use_structured_output = getattr(llm_config, 'enable_structured_outputs', True)
            return _call_with_retries(
                _call_xai_api, prompt, api_key, model_name, 
                max_tokens=max_tokens, timeout_seconds=timeout_seconds, 
                use_structured_output=use_structured_output,
                max_retries=max_retries, retry_delay=retry_delay
            )
        elif provider == "groq":
            return _call_with_retries(
                _call_groq_api, prompt, api_key, model_name, 
                max_tokens=max_tokens, timeout_seconds=timeout_seconds,
                max_retries=max_retries, retry_delay=retry_delay
            )
        elif provider == "anthropic":
            return _call_with_retries(
                _call_openai_compatible_api, prompt, api_key, model_name, 
                "https://api.anthropic.com/v1",
                max_tokens=max_tokens, timeout_seconds=timeout_seconds,
                max_retries=max_retries, retry_delay=retry_delay
            )
        elif provider == "openai":
            return _call_with_retries(
                _call_openai_compatible_api, prompt, api_key, model_name, 
                "https://api.openai.com/v1",
                max_tokens=max_tokens, timeout_seconds=timeout_seconds,
                max_retries=max_retries, retry_delay=retry_delay
            )
        else:
            return f"Unsupported provider: {provider}"
            
    except Exception as e:
        _log_debug_message("LLM API Call", f"Unexpected error: {e}")
        return f"A mysterious interference disrupts the Oracle. (Error: Unexpected problem during LLM call. Details: {e})"

# Placeholder for an actual LLM API call function
# In a real scenario, this would involve libraries like 'requests' or a specific LLM provider's SDK
def _call_llm_api(prompt: str, api_key: str, model_name: Optional[str] = None, provider: str = None, llm_config = None) -> Optional[str]:
    """Makes an API call to an LLM using the most appropriate provider.

    Args:
        prompt (str): The complete prompt to send to the LLM.
        api_key (str): The API key for the LLM service.
        model_name (Optional[str]): The specific model to use.
        provider (str): Optional provider hint (xai, groq, openai, anthropic, etc.).
        llm_config: LLM configuration object with safety settings.

    Returns:
        Optional[str]: The LLM's response string, or None if an error occurs.
    """
    return _detect_provider_and_call_api(prompt, api_key, model_name, provider, llm_config)

# --- LLM Interaction Logging ---

def _log_oracle_interaction(timestamp: str, player_query: str, prompt: str, raw_response: Optional[str], 
                            parsed_narrative: Optional[str], parsed_actions: Optional[List[Dict[str, Any]]],
                            error_message: Optional[str] = None):
    """Logs the details of an Oracle LLM interaction using the root logger."""
    # MODIFIED: Log a summary string using logger.info
    # The full JSON dump could be logged at DEBUG level if needed.
    log_data_summary = {
        "player_query_snippet": player_query[:70] + "..." if player_query and len(player_query) > 70 else player_query,
        "raw_response_snippet": raw_response[:100] + "..." if raw_response and len(raw_response) > 100 else raw_response,
        "parsed_narrative_snippet": parsed_narrative[:100] + "..." if parsed_narrative and len(parsed_narrative) > 100 else parsed_narrative,
        "action_count": len(parsed_actions) if parsed_actions else 0,
    }

    full_log_message = (
        f"[OracleInteraction] Query: '{log_data_summary['player_query_snippet']}', "
        f"Narrative: '{log_data_summary['parsed_narrative_snippet']}', "
        f"Actions: {log_data_summary['action_count']}, "
        f"RawResp: '{log_data_summary['raw_response_snippet']}', " # Added raw response snippet for better context
        f"Error: {error_message if error_message else 'None'}"
    )
    
    try:
        logger.info(full_log_message)
        # For very detailed debugging, one might log the full prompt or full raw_response at DEBUG level
        # logger.debug(f"[OracleInteractionDetails] Timestamp: {timestamp}, Full Prompt: {prompt}, Full Raw Response: {raw_response}")
    except Exception as e:
        try:
            print(f"LOGGER_FALLBACK_ERROR: Failed to log Oracle interaction. Error: {e}", file=sys.stderr)
            # Avoid printing potentially huge log_data here, just the error.
        except Exception:
            pass


def _parse_llm_response(response_text: str) -> (str, List[Dict[str, Any]]):
    """Parses the LLM's raw response text to separate narrative from structured actions.
    Handles both structured JSON responses (from XAI structured outputs) and legacy text format.

    Args:
        response_text (str): The raw string response from the LLM.

    Returns:
        Tuple[str, List[Dict[str, Any]]]: A tuple containing:
            - narrative (str): The textual response to be shown to the player.
            - actions (List[Dict[str, Any]]): A list of game action dictionaries.
    """
    # First, try to parse as structured JSON (XAI structured outputs)
    try:
        parsed_json = json.loads(response_text.strip())
        if isinstance(parsed_json, dict) and "narrative" in parsed_json and "actions" in parsed_json:
            narrative = parsed_json["narrative"]
            actions = parsed_json["actions"]
            
            # Validate actions structure
            validated_actions = []
            for action in actions:
                if isinstance(action, dict) and "action_type" in action and "details" in action:
                    validated_actions.append(action)
                else:
                    _log_debug_message("LLM Interface", f"Skipping malformed action in structured response: {action}")
            
            _log_debug_message("LLM Interface", f"Successfully parsed structured JSON response with {len(validated_actions)} actions")
            return narrative, validated_actions
    except json.JSONDecodeError:
        # Not JSON, fall back to legacy text parsing
        pass
    except Exception as e:
        _log_debug_message("LLM Interface", f"Error parsing structured JSON response: {e}, falling back to text parsing")
    
    # Legacy text parsing (original implementation)
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
                
                # Try to parse the JSON - first as-is, then with fixed quotes
                details = None
                try:
                    details = json.loads(json_details_str)
                except json.JSONDecodeError:
                    # Try fixing single quotes to double quotes
                    try:
                        fixed_json = json_details_str.replace("'", '"')
                        details = json.loads(fixed_json)
                        _log_debug_message("LLM Interface", f"Fixed JSON quotes for action: {action_type}")
                    except json.JSONDecodeError as e2:
                        _log_debug_message("LLM Interface", f"Error decoding JSON from LLM action: {json_details_str}. Error: {e2}")
                        # Add error message to narrative as expected by tests
                        error_msg = f"(The Oracle's words concerning an action were muddled: {action_type}::{json_details_str})"
                        narrative.append(error_msg)
                        continue  # Skip this malformed action
                
                if details is not None:
                    actions.append({"action_type": action_type.strip(), "details": details})
                    
            except ValueError: # Not enough values to unpack (split didn't find "::")
                _log_debug_message("LLM Interface", f"Malformed action string from LLM: {part.strip()}")
                # Add error message to narrative as expected by tests
                error_msg = f"(The Oracle made an unclear gesture: {part.strip()})"
                narrative.append(error_msg)
                continue  # Skip this malformed action

    return " ".join(narrative).strip(), actions 

def process_enhanced_oracle_streaming(prompt: str, api_key: str, model_name: str, provider_hint: str, 
                                    llm_config, player_query: str, oracle_name: str) -> Iterator[Dict[str, Any]]:
    """Process enhanced Oracle streaming with flavor text and proper narrative/action separation.
    
    This function uses the new text streaming engine to provide a more immersive experience
    with flavor text while waiting for the LLM response, and properly separates narrative
    text from JSON actions to prevent streaming issues.
    
    Args:
        prompt: The complete prompt to send to the LLM
        api_key: API key for the LLM service
        model_name: Model name to use
        provider_hint: Provider hint (xai, groq, etc.)
        llm_config: LLM configuration object
        player_query: The original player query
        oracle_name: Name of the Oracle
        
    Yields:
        Dict[str, Any]: Action dictionaries for game logic to process
    """
    timestamp_utc = datetime.datetime.now(timezone.utc).isoformat()
    if "+00:00" in timestamp_utc:
        timestamp_utc = timestamp_utc.replace("+00:00", "Z")
    elif not timestamp_utc.endswith("Z"):
        timestamp_utc += "Z"

    complete_llm_response = ""
    parsed_narrative_for_log = None
    parsed_actions_for_log = None
    error_for_log = None
    
    try:
        # Create the LLM response iterator
        _log_debug_message("LLM Interface", "Creating LLM response iterator...")
        llm_response_iterator = _call_llm_api_streaming(prompt, api_key, model_name, provider_hint, llm_config)
        
        # Create a wrapper iterator that collects chunks for logging while yielding them for streaming
        def logging_llm_iterator():
            nonlocal complete_llm_response, error_for_log
            _log_debug_message("LLM Interface", "Starting real-time LLM streaming...")
            
            chunk_count = 0
            stream_healthy = True
            for chunk in llm_response_iterator:
                chunk_count += 1
                
                if chunk is None: # Skip None chunks often used as keep-alives or metadata carriers
                    _log_debug_message("LLM Interface", f"Received None chunk {chunk_count}. Skipping.")
                    continue

                if not isinstance(chunk, str):
                    _log_debug_message("LLM Interface", f"WARNING: Received non-string chunk {chunk_count}: type={type(chunk)}, value='{str(chunk)[:100]}...'")
                    try:
                        chunk = str(chunk) # Attempt to convert to string
                    except Exception as conversion_e:
                        _log_debug_message("LLM Interface", f"ERROR: Failed to convert non-string chunk to string: {conversion_e}")
                        error_for_log = f"Error: LLM stream sent unconvertible non-string data: {type(chunk)}"
                        yield error_for_log # Yield specific error
                        stream_healthy = False
                        break
                
                _log_debug_message("LLM Interface", f"Received chunk {chunk_count}: '{chunk[:30]}...' (length: {len(chunk)})")
                
                if chunk.startswith("Error:"):
                    error_for_log = chunk
                    _log_debug_message("LLM Interface", f"Error chunk received directly from LLM call: {chunk}")
                    # Do not yield this error directly, let the main try-except in start_oracle_streaming_sequence handle it
                    # or let the finally block log it.
                    stream_healthy = False
                    break # Stop processing further chunks from LLM
                
                complete_llm_response += chunk
                yield chunk
            
            if stream_healthy:
                _log_debug_message("LLM Interface", f"LLM streaming completed. Total chunks: {chunk_count}, total response length: {len(complete_llm_response)}")
            else:
                _log_debug_message("LLM Interface", f"LLM streaming interrupted or ended with error. Total chunks processed: {chunk_count}, collected response length: {len(complete_llm_response)}")
        
        # Use the text streaming engine to create the complete Oracle experience
        _log_debug_message("LLM Interface", "Starting Oracle streaming sequence...")
        action_count = 0
        for action in text_streaming_engine.start_oracle_streaming_sequence(
            oracle_name, player_query, logging_llm_iterator()
        ):
            action_count += 1
            _log_debug_message("LLM Interface", f"Yielding streaming action {action_count}: {action.get('action_type')}")
            yield action
        
        _log_debug_message("LLM Interface", f"Oracle streaming sequence completed with {action_count} actions")
        
        # Parse the complete response for logging (after streaming is complete)
        if complete_llm_response:
            parsed_narrative_for_log, parsed_actions_for_log = _parse_llm_response(complete_llm_response)
            _log_debug_message("LLM Interface", f"Parsed narrative length: {len(parsed_narrative_for_log) if parsed_narrative_for_log else 0}")
        
    except Exception as e:
        error_message = f"A critical error occurred while communicating with the Oracle. Details: {str(e)}"
        error_for_log = error_message
        _log_debug_message("LLM Interface", f"Critical error during enhanced streaming LLM call: {e}")
        
        # Use the streaming engine to show error
        yield {
            "action_type": "stream_text_chunk",
            "details": {
                "text": "The Oracle's connection is severely disrupted. Please check the logs.",
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
    
    finally:
        # Log the interaction details with the complete response
        _log_oracle_interaction(
            timestamp=timestamp_utc,
            player_query=player_query,
            prompt=prompt,
            raw_response=complete_llm_response if complete_llm_response else "N/A",
            parsed_narrative=parsed_narrative_for_log,
            parsed_actions=parsed_actions_for_log,
            error_message=error_for_log
        ) 