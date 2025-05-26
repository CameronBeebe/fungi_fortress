"""
Text Streaming Engine for Fungi Fortress

This module provides a general-purpose text streaming system that can be used
for all text-based interactions in the game, including Oracle dialogues, 
character interactions, events, and narrative text.

The system separates narrative text (which should be streamed) from structured
data/actions (which should be processed immediately) to provide a smooth
user experience while maintaining game mechanics integration.
"""

import time
import random
from typing import Iterator, Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class StreamingTextType(Enum):
    """Types of text that can be streamed."""
    ORACLE_DIALOGUE = "oracle_dialogue"
    CHARACTER_DIALOGUE = "character_dialogue"
    NARRATIVE = "narrative"
    EVENT_DESCRIPTION = "event_description"
    FLAVOR_TEXT = "flavor_text"
    SYSTEM_MESSAGE = "system_message"

@dataclass
class StreamingTextChunk:
    """Represents a chunk of text to be streamed."""
    text: str
    text_type: StreamingTextType
    delay_ms: int = 50  # Delay between characters in milliseconds
    is_complete: bool = False
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class TextStreamingEngine:
    """
    General-purpose text streaming engine for the game.
    
    This engine can handle multiple concurrent streams and provides
    different streaming speeds and effects for different types of text.
    """
    
    def __init__(self):
        self.active_streams: Dict[str, Iterator[str]] = {}
        self.stream_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Single master delay for all character-by-character streaming
        self.default_character_delay_ms: int = 30 # You can adjust this single value
        
        # Pause duration between larger text blocks (e.g., flavor text lines)
        self.inter_chunk_pause_ms: int = 800 # Formerly oracle_flavor_pause_ms

        # Default delays dictionary - simplified, primarily for non-character-streamed types or future use
        # For character streamed text, default_character_delay_ms is the source of truth.
        self.default_delays = {
            StreamingTextType.ORACLE_DIALOGUE: self.default_character_delay_ms,
            StreamingTextType.CHARACTER_DIALOGUE: self.default_character_delay_ms,
            StreamingTextType.NARRATIVE: self.default_character_delay_ms,
            StreamingTextType.EVENT_DESCRIPTION: self.default_character_delay_ms,
            StreamingTextType.FLAVOR_TEXT: self.default_character_delay_ms,
            StreamingTextType.SYSTEM_MESSAGE: 10, # System messages can remain very fast
        }
    
    def create_character_stream(self, text: str, char_delay_ms: int = 30) -> Iterator[str]:
        """Create a character-by-character streaming iterator."""
        for char in text:
            yield char
            # Note: Actual delay timing is handled by the game loop, not here
    
    def create_word_stream(self, text: str, word_delay_ms: int = 100) -> Iterator[str]:
        """Create a word-by-word streaming iterator."""
        words = text.split()
        for i, word in enumerate(words):
            if i == 0:
                yield word
            else:
                yield " " + word
    
    def create_sentence_stream(self, text: str, sentence_delay_ms: int = 500) -> Iterator[str]:
        """Create a sentence-by-sentence streaming iterator."""
        sentences = text.split('. ')
        for i, sentence in enumerate(sentences):
            if i == 0:
                yield sentence
            else:
                yield ". " + sentence
    
    def separate_narrative_from_actions(self, llm_response: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Separate narrative text from structured actions in an LLM response.
        
        This handles both structured JSON responses and legacy text format with ACTION:: markers.
        Returns the narrative text (for streaming) and a list of actions (for immediate processing).
        """
        import json
        
        # First, try to parse as structured JSON (XAI structured outputs)
        try:
            parsed_json = json.loads(llm_response.strip())
            if isinstance(parsed_json, dict) and "narrative" in parsed_json and "actions" in parsed_json:
                narrative = parsed_json["narrative"]
                actions = parsed_json["actions"]
                
                # Validate actions structure
                validated_actions = []
                for action in actions:
                    if isinstance(action, dict) and "action_type" in action and "details" in action:
                        validated_actions.append(action)
                
                return narrative, validated_actions
        except json.JSONDecodeError:
            # Not JSON, fall back to legacy text parsing
            pass
        except Exception:
            # Error parsing structured JSON, fall back to text parsing
            pass
        
        # Legacy text parsing for ACTION:: format
        narrative_parts = []
        actions = []
        parts = llm_response.split("ACTION::")
        
        if parts:
            narrative_parts.append(parts[0].strip())  # First part is always narrative
            
            for part in parts[1:]:
                try:
                    action_def = part.strip()
                    # Expecting format: action_type::{json_details}
                    action_type, json_details_str = action_def.split("::", 1)
                    
                    # Try to parse the JSON
                    details = None
                    try:
                        details = json.loads(json_details_str)
                    except json.JSONDecodeError:
                        # Try fixing single quotes to double quotes
                        try:
                            fixed_json = json_details_str.replace("'", '"')
                            details = json.loads(fixed_json)
                        except json.JSONDecodeError:
                            # Skip malformed action, add error to narrative
                            narrative_parts.append(f"(The Oracle's words concerning an action were muddled: {action_type}::{json_details_str})")
                            continue
                    
                    if details is not None:
                        actions.append({"action_type": action_type.strip(), "details": details})
                        
                except ValueError:
                    # Malformed action string
                    narrative_parts.append(f"(The Oracle made an unclear gesture: {part.strip()})")
                    continue
        
        narrative = " ".join(narrative_parts).strip()
        return narrative, actions
    
    def create_oracle_flavor_text(self, oracle_name: str, player_action: str = "consultation", 
                                 environment: str = "ancient chamber") -> List[str]:
        """
        Generate flavor text for Oracle interactions to entertain the player while waiting.
        
        Args:
            oracle_name: Name of the Oracle being consulted
            player_action: What the player is doing (consultation, offering, etc.)
            environment: Description of the environment
            
        Returns:
            List of flavor text strings to be streamed before the LLM response
        """
        flavor_templates = [
            f"You approach {oracle_name} with reverence, seeking wisdom in this {environment}.",
            f"The air grows thick with ancient spores as {oracle_name} prepares to commune with the mycelial network.",
            f"Bioluminescent fungi pulse gently around the chamber, responding to {oracle_name}'s presence.",
            f"{oracle_name} inhales deeply, drawing knowledge from the vast fungal consciousness.",
            f"The {environment} falls silent except for the soft whisper of spores in the air.",
            f"You sense the weight of countless ages as {oracle_name} connects to the ancient wisdom.",
            f"Tendrils of mycelium beneath your feet seem to vibrate with anticipation.",
            f"The Oracle's eyes begin to glow with an otherworldly light as the connection strengthens.",
        ]
        
        # Select 2-3 random flavor texts
        selected_count = random.randint(2, 3)
        selected_texts = random.sample(flavor_templates, min(selected_count, len(flavor_templates)))
        
        return selected_texts
    
    def create_oracle_waiting_text(self, oracle_name: str) -> List[str]:
        """
        Generate text to show while waiting for LLM response.
        
        Returns:
            List of waiting text strings with varying delays
        """
        waiting_texts = [
            f"{oracle_name} communes with the vast mycelial network...",
            "Ancient knowledge flows through fungal pathways...",
            "The Oracle's consciousness expands across the underground realm...",
            "Whispers of wisdom echo through the spore-filled air...",
            "The fungal network pulses with ancient memories...",
        ]
        
        return [random.choice(waiting_texts)]
    
    def _create_stream_chunk_action(self, text: str, text_type: StreamingTextType, 
                                    delay_ms: Optional[int] = None, # Allow override, but default to master
                                    add_newline: bool = True, 
                                    is_error: bool = False, target: str = "oracle_dialogue") -> Dict[str, Any]:
        """Helper to create a \'stream_text_chunk\' action dictionary."""
        
        current_delay = delay_ms if delay_ms is not None else self.default_character_delay_ms
        
        details = {
            "text": text,
            "text_type": text_type.value,
            "target": target,
            "delay_ms": current_delay,
            "add_newline": add_newline
        }
        if is_error:
            details["is_error"] = True
        return {"action_type": "stream_text_chunk", "details": details}

    def start_oracle_streaming_sequence(self, oracle_name: str, player_query: str, 
                                      llm_response_iterator: Iterator[str]) -> Iterator[Dict[str, Any]]:
        """
        Create a complete Oracle streaming sequence with flavor text, waiting text, and LLM response.
        All character-streamed text will use default_character_delay_ms.
        """
        # Phase 1: Stream flavor text character by character
        flavor_texts = self.create_oracle_flavor_text(oracle_name)
        for flavor_line in flavor_texts:
            for char in flavor_line:
                yield self._create_stream_chunk_action(
                    text=char,
                    text_type=StreamingTextType.FLAVOR_TEXT,
                    add_newline=False
                )
            # Add newline after the full flavor line (acts like another character)
            yield self._create_stream_chunk_action(
                text='\n', 
                text_type=StreamingTextType.FLAVOR_TEXT,
                add_newline=False # The text itself is the newline
            )
            yield {"action_type": "stream_pause", "details": {"duration_ms": self.inter_chunk_pause_ms}}
        
        # Phase 2: Show waiting text character by character
        waiting_texts = self.create_oracle_waiting_text(oracle_name)
        for waiting_line in waiting_texts:
            for char in waiting_line:
                yield self._create_stream_chunk_action(
                    text=char,
                    text_type=StreamingTextType.ORACLE_DIALOGUE,
                    add_newline=False
                )
            # Add newline after the full waiting line
            yield self._create_stream_chunk_action(
                text='\n', 
                text_type=StreamingTextType.ORACLE_DIALOGUE,
                add_newline=False
            )
        
        # Phase 3: Collect complete LLM response
        collected_response = ""
        try:
            for chunk in llm_response_iterator:
                if chunk and not chunk.startswith("Error:"):
                    collected_response += chunk
                elif chunk and chunk.startswith("Error:"):
                    error_message_text = "The Oracle\'s connection wavers... Please try again."
                    for char in error_message_text:
                        yield self._create_stream_chunk_action(
                            text=char,
                            text_type=StreamingTextType.ORACLE_DIALOGUE,
                            add_newline=False,
                            is_error=True
                        )
                    yield self._create_stream_chunk_action(text='\n', text_type=StreamingTextType.ORACLE_DIALOGUE, add_newline=False, is_error=True)
                    return # End sequence on LLM error
            
            if collected_response:
                narrative, actions = self.separate_narrative_from_actions(collected_response)
                
                if narrative:
                    # Phase 4: Stream the narrative response character by character
                    # Stream "\nOracle speaks:" first, char by char
                    prefix_text = f"\n{oracle_name} speaks:"
                    for char in prefix_text:
                        yield self._create_stream_chunk_action(
                            text=char,
                            text_type=StreamingTextType.ORACLE_DIALOGUE,
                            add_newline=False
                        )
                    # Add newline after the prefix
                    yield self._create_stream_chunk_action(
                        text='\n',
                        text_type=StreamingTextType.ORACLE_DIALOGUE,
                        add_newline=False
                    )
                    
                    # Stream the actual LLM narrative character by character
                    for char in narrative: 
                        yield self._create_stream_chunk_action(
                            text=char,
                            text_type=StreamingTextType.ORACLE_DIALOGUE,
                            add_newline=False
                        )
                    
                    # Add final newline for the main narrative (explicit 0 delay)
                    yield self._create_stream_chunk_action( 
                        text='\n', 
                        text_type=StreamingTextType.ORACLE_DIALOGUE,
                        delay_ms=0, # Ensure this final newline is fast
                        add_newline=False
                    )
                
                    # Phase 5: Execute game actions
                    for action in actions:
                        yield action
                    
                    # Phase 6: Update interaction history
                    yield {
                        "action_type": "update_oracle_history",
                        "details": {"player_query": player_query, "oracle_response": narrative}
                    }
                else: # Empty LLM response
                    empty_response_text = "The Oracle remains silent, its wisdom beyond words..."
                    for char in empty_response_text:
                        yield self._create_stream_chunk_action(
                            text=char,
                            text_type=StreamingTextType.ORACLE_DIALOGUE,
                            add_newline=False,
                            is_error=True
                        )
                    yield self._create_stream_chunk_action(text='\n', text_type=StreamingTextType.ORACLE_DIALOGUE, add_newline=False, is_error=True)
            else: # Empty LLM response
                empty_response_text = "The Oracle remains silent, its wisdom beyond words..."
                for char in empty_response_text:
                    yield self._create_stream_chunk_action(
                        text=char,
                        text_type=StreamingTextType.ORACLE_DIALOGUE,
                        add_newline=False,
                        is_error=True
                    )
                yield self._create_stream_chunk_action(text='\n', text_type=StreamingTextType.ORACLE_DIALOGUE, add_newline=False, is_error=True)
                
        except Exception as e: # Catch-all for other errors during streaming/parsing
            exception_message_text = "The Oracle\'s connection is disrupted by mysterious forces..."
            for char in exception_message_text:
                yield self._create_stream_chunk_action(
                    text=char,
                    text_type=StreamingTextType.ORACLE_DIALOGUE,
                    add_newline=False,
                    is_error=True
                )
            yield self._create_stream_chunk_action(text='\n', text_type=StreamingTextType.ORACLE_DIALOGUE, add_newline=False, is_error=True)
        
        # Phase 7: Return to awaiting prompt state
        yield {"action_type": "set_oracle_state", "details": {"state": "AWAITING_PROMPT"}}

# Global instance for the game to use
text_streaming_engine = TextStreamingEngine() 