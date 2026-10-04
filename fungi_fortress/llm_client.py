"""Unified LLM client for Fungi Fortress.

Provides a single, typed interface for LLM API calls with streaming support,
error handling, and a mock provider for offline play and testing.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Optional, Type, TypeVar, Union

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar('T')


# === Typed Exceptions ===


class LLMError(Exception):
    """Base exception for all LLM client errors."""
    
    def user_message(self) -> str:
        """Player-facing message for this error."""
        return "The Oracle's connection is disrupted."


class AuthenticationError(LLMError):
    """API key is invalid or missing."""
    
    def user_message(self) -> str:
        return "The Oracle's connection is disrupted. (Authentication failed)"


class RateLimitError(LLMError):
    """API rate limit exceeded."""
    
    def user_message(self) -> str:
        return "The Oracle is overwhelmed by queries. Please wait."


class TimeoutError(LLMError):
    """API request timed out."""
    
    def user_message(self) -> str:
        return "The Oracle's response faded into silence."


class ConnectionError(LLMError):
    """Network connection failed."""
    
    def user_message(self) -> str:
        return "The Oracle's connection cannot be established."


class BadResponseError(LLMError):
    """API returned malformed or unexpected response."""
    
    def user_message(self) -> str:
        return "The Oracle's words are unclear."


# === Configuration ===


@dataclass
class LLMClientConfig:
    """Configuration for XAI LLM client."""
    
    model: str
    api_key: Optional[str] = None
    max_tokens: int = 1000
    timeout_seconds: int = 60
    temperature: float = 0.7


# === Schema Helpers ===


def _schema_from_model(model_cls: Type[BaseModel], schema_name: str) -> dict[str, Any]:
    """Convert a Pydantic model to a JSON schema dict for XAI structured outputs.
    
    Args:
        model_cls: Pydantic model class
        schema_name: Name for the schema
        
    Returns:
        Schema dict suitable for XAI response_format
    """
    schema = model_cls.model_json_schema()
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema_name,
            "strict": True,
            "schema": schema
        }
    }


def _schema_from_dict(schema: dict[str, Any], schema_name: str) -> dict[str, Any]:
    """Wrap a JSON schema dict for XAI structured outputs.
    
    Args:
        schema: JSON schema dict
        schema_name: Name for the schema
        
    Returns:
        Schema dict suitable for XAI response_format
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema_name,
            "strict": True,
            "schema": schema
        }
    }


# === Mock Provider ===


class MockLLMProvider:
    """Deterministic mock provider for offline play and testing."""
    
    # In-character responses for common query patterns
    RESPONSES = {
        "greeting": "Greetings, seeker. The mycelial network pulses with ancient knowledge. What wisdom do you seek?",
        "quest": "Your path winds through shadowed groves. Gather what the forest offers, and the way forward shall reveal itself.",
        "fungi": "The sacred fungi hold memories of ages past. They grow in places of deep magic, where stone and root intertwine.",
        "help": "Trust in the network. Its threads connect all living things. What seems lost may yet be found through patience.",
        "default": "The spores whisper... but their meaning is obscured. Perhaps your question needs a different shape.",
    }
    
    def __init__(self):
        self._call_count = 0
    
    def chat(self, messages: list[dict], max_tokens: int = 1000, response_format: Optional[dict[str, Any]] = None) -> str:
        """Non-streaming mock response."""
        self._call_count += 1
        user_content = self._extract_user_content(messages)
        return self._mock_response(user_content)
    
    def chat_stream(self, messages: list[dict], max_tokens: int = 1000) -> Iterator[str]:
        """Streaming mock response."""
        self._call_count += 1
        user_content = self._extract_user_content(messages)
        response = self._mock_response(user_content)
        
        # Yield in chunks to simulate streaming
        chunk_size = 8
        for i in range(0, len(response), chunk_size):
            yield response[i:i + chunk_size]
    
    def _extract_user_content(self, messages: list[dict]) -> str:
        """Extract user query from messages."""
        # Find the last user message and extract the actual query
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                # Look for "Player Query:" in the content
                if "Player Query:" in content:
                    query_part = content.split("Player Query:")[-1].strip()
                    return query_part.lower()
                return content.lower()
        return ""
    
    def _mock_response(self, user_content: str) -> str:
        """Generate deterministic response based on query (whole-word matching)."""
        import re
        
        # Normalize content for matching
        normalized = user_content.lower()
        
        # Use word boundary matching to avoid substring issues (e.g., "hi" in "this")
        def has_word(pattern: str) -> bool:
            return bool(re.search(r'\b' + re.escape(pattern) + r'\b', normalized))
        
        # Select narrative based on query patterns
        if any(has_word(word) for word in ["hello", "hi", "greet"]):
            narrative = self.RESPONSES["greeting"]
        elif any(has_word(word) for word in ["quest", "mission", "goal"]):
            narrative = self.RESPONSES["quest"]
        elif any(has_word(word) for word in ["fungi", "mushroom", "spore"]):
            narrative = self.RESPONSES["fungi"]
        elif any(has_word(word) for word in ["help", "aid", "assist"]):
            narrative = self.RESPONSES["help"]
        else:
            narrative = self.RESPONSES["default"]
        
        # Return structured JSON response matching NpcReply schema
        import json
        return json.dumps({
            "narrative": narrative,
            "actions": []
        })


# === XAI Provider ===


class XAIProvider:
    """Provider for XAI (Grok) API."""
    
    def __init__(self, config: LLMClientConfig):
        self.config = config
        self._openai_available = self._check_openai()
    
    def _check_openai(self) -> bool:
        """Check if OpenAI library is available (used for XAI API calls)."""
        try:
            import openai
            return True
        except ImportError:
            logger.warning("openai library not available (required for XAI)")
            return False
    
    def chat(
        self,
        messages: list[dict],
        max_tokens: int = 1000,
        reasoning_effort: str = "high",
        response_format: Optional[dict[str, Any]] = None
    ) -> str:
        """Non-streaming chat completion with XAI.
        
        Args:
            messages: List of message dicts
            max_tokens: Maximum tokens to generate
            reasoning_effort: XAI reasoning effort for grok-3-mini models
            response_format: Per-call response format schema
        """
        if not self._openai_available:
            raise ConnectionError("OpenAI library not installed (required for XAI API)")
        
        import openai
        
        try:
            client = openai.OpenAI(
                api_key=self.config.api_key,
                base_url="https://api.x.ai/v1",
                timeout=self.config.timeout_seconds
            )
            
            # Build completion parameters
            completion_params = {
                "model": self.config.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": self.config.temperature,
            }
            
            # Add reasoning_effort for grok-3-mini models
            if "grok-3-mini" in self.config.model.lower():
                completion_params["reasoning_effort"] = reasoning_effort
            
            # Add response format if provided
            if response_format:
                completion_params["response_format"] = response_format
            
            completion = client.chat.completions.create(**completion_params)
            
            content = completion.choices[0].message.content
            if not content:
                raise BadResponseError("Empty response from XAI API")
            
            return content
            
        except openai.AuthenticationError as e:
            raise AuthenticationError(f"Invalid XAI API key: {e}") from e
        except openai.RateLimitError as e:
            raise RateLimitError(f"XAI rate limit exceeded: {e}") from e
        except openai.APITimeoutError as e:
            raise TimeoutError(f"XAI request timed out: {e}") from e
        except openai.APIConnectionError as e:
            raise ConnectionError(f"XAI connection failed: {e}") from e
        except Exception as e:
            raise BadResponseError(f"Unexpected XAI error: {e}") from e
    
    def chat_stream(self, messages: list[dict], max_tokens: int = 1000, reasoning_effort: str = "high") -> Iterator[str]:
        """Streaming chat completion with XAI."""
        if not self._openai_available:
            raise ConnectionError("OpenAI library not installed (required for XAI API)")
        
        import openai
        
        try:
            client = openai.OpenAI(
                api_key=self.config.api_key,
                base_url="https://api.x.ai/v1",
                timeout=self.config.timeout_seconds
            )
            
            # Build completion parameters
            completion_params = {
                "model": self.config.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": self.config.temperature,
                "stream": True
            }
            
            # Add reasoning_effort for grok-3-mini models
            if "grok-3-mini" in self.config.model.lower():
                completion_params["reasoning_effort"] = reasoning_effort
            
            stream = client.chat.completions.create(**completion_params)
            
            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        yield delta.content
                        
        except openai.AuthenticationError as e:
            raise AuthenticationError(f"Invalid XAI API key: {e}") from e
        except openai.RateLimitError as e:
            raise RateLimitError(f"XAI rate limit exceeded: {e}") from e
        except openai.APITimeoutError as e:
            raise TimeoutError(f"XAI request timed out: {e}") from e
        except openai.APIConnectionError as e:
            raise ConnectionError(f"XAI connection failed: {e}") from e
        except Exception as e:
            raise BadResponseError(f"Unexpected XAI error: {e}") from e


# === Main Client ===


class LLMClient:
    """LLM client supporting XAI (Grok) and mock provider."""
    
    def __init__(self, config: Optional[LLMClientConfig] = None, use_mock: bool = False):
        """Initialize client.
        
        Args:
            config: Client configuration. If None, uses mock provider.
            use_mock: Force use of mock provider even if config is provided.
        """
        # Check if we should use mock
        should_mock = (
            use_mock 
            or config is None 
            or not config.api_key 
            or config.api_key in ("YOUR_API_KEY_HERE", "testkey123")
        )
        self._use_mock = should_mock
        
        if self._use_mock:
            self._provider = MockLLMProvider()
            logger.info("Using mock LLM provider (offline mode)")
        else:
            self._provider = XAIProvider(config)
            logger.info(f"Using XAI API (https://api.x.ai/v1) with model {config.model}")
    
    def is_mock(self) -> bool:
        """Check if using mock provider."""
        return self._use_mock
    
    def chat(
        self,
        messages: list[dict],
        max_tokens: Optional[int] = None,
        reasoning_effort: str = "high",
        response_format: Optional[dict[str, Any]] = None
    ) -> str:
        """Send a chat completion request (non-streaming).
        
        Args:
            messages: List of message dicts with 'role' and 'content'.
            max_tokens: Override default max tokens.
            reasoning_effort: XAI reasoning effort ("low", "medium", "high") for grok-3-mini models.
            response_format: Per-call response format schema.
            
        Returns:
            Complete response text.
            
        Raises:
            LLMError subclasses for various failure modes.
        """
        if max_tokens is None:
            max_tokens = 1000
        
        try:
            if self._use_mock:
                return self._provider.chat(messages, max_tokens, response_format=response_format)
            else:
                return self._provider.chat(messages, max_tokens, reasoning_effort, response_format)
        except LLMError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in chat: {e}")
            raise BadResponseError(f"Unexpected error: {e}") from e
    
    def chat_stream(self, messages: list[dict], max_tokens: Optional[int] = None, reasoning_effort: str = "high") -> Iterator[str]:
        """Send a streaming chat completion request.
        
        Args:
            messages: List of message dicts with 'role' and 'content'.
            max_tokens: Override default max tokens.
            reasoning_effort: XAI reasoning effort ("low", "medium", "high") for grok-3-mini models.
            
        Yields:
            Response text chunks as they arrive.
            
        Raises:
            LLMError subclasses for various failure modes.
        """
        if max_tokens is None:
            max_tokens = 1000
        
        try:
            if self._use_mock:
                yield from self._provider.chat_stream(messages, max_tokens)
            else:
                yield from self._provider.chat_stream(messages, max_tokens, reasoning_effort)
        except LLMError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in chat_stream: {e}")
            raise BadResponseError(f"Unexpected error: {e}") from e


# === Client Factory ===


def create_client_from_config(
    model: str,
    api_key: Optional[str] = None,
    max_tokens: int = 1000,
    timeout_seconds: int = 60,
    temperature: float = 0.7,
) -> LLMClient:
    """Create an XAI LLM client from configuration parameters.
    
    Args:
        model: XAI model name (e.g., 'grok-3-mini')
        api_key: XAI API key (XAI_API_KEY), or None to use mock provider
        max_tokens: Maximum tokens per response
        timeout_seconds: Request timeout
        temperature: Sampling temperature
        
    Returns:
        Configured LLMClient instance (XAI or mock)
    """
    # If no API key, use mock
    if not api_key or api_key in ("YOUR_API_KEY_HERE", "testkey123"):
        logger.info("No valid API key configured, using mock provider")
        return LLMClient(use_mock=True)
    
    config = LLMClientConfig(
        model=model,
        api_key=api_key,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
    )
    
    return LLMClient(config)


# === Structured Call Helper ===


def _response_preview(response: str | dict[str, Any] | None, max_len: int = 300) -> str:
    """Format a response for logging, truncating to max_len characters.
    
    Sanitizes API keys and other sensitive data from logs.
    """
    if not response:
        return "(no response captured)"
    
    if isinstance(response, dict):
        response = json.dumps(response, indent=2)
    
    # Sanitize API keys
    response = re.sub(r'(api[_-]?key["\s:]+)[^\s,"\']+', r'\1[REDACTED]', response, flags=re.IGNORECASE)
    response = re.sub(r'(bearer\s+)[^\s,"\']+', r'\1[REDACTED]', response, flags=re.IGNORECASE)
    response = re.sub(r'xai-[A-Za-z0-9]+', 'xai-REDACTED', response)
    
    if len(response) <= max_len:
        return response
    
    return response[:max_len] + "..."


def structured_call(
    client: LLMClient,
    messages: list[dict],
    model_cls: Type[BaseModel],
    schema_name: str = "response",
    label: str = "Structured call",
    convert: Optional[Callable[[BaseModel], T]] = None,
    max_tokens: int = 4000,
    reasoning_effort: str = "high",
    attempts: int = 2,
) -> Optional[Union[BaseModel, T]]:
    """Make a structured LLM call with validation and retry.
    
    Args:
        client: LLM client instance
        messages: Initial conversation messages
        model_cls: Pydantic model class defining the expected response structure
        schema_name: Name for the JSON schema
        label: Label for log messages (e.g., "World seed", "Depth seed")
        convert: Optional converter function that takes the parsed model and returns
                 a converted object. Should raise ValueError with error details on failure.
        max_tokens: Maximum tokens to generate
        reasoning_effort: XAI reasoning effort ("low", "medium", "high")
        attempts: Maximum number of attempts (including retries)
        
    Returns:
        Converted object (if converter provided), validated Pydantic model instance, or None if all attempts failed
    """
    # Generate schema from Pydantic model
    response_format = _schema_from_model(model_cls, schema_name)
    
    conversation = list(messages)
    
    for attempt in range(attempts):
        raw_response = None
        try:
            # Request with schema
            raw_response = client.chat(
                conversation,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
                response_format=response_format
            )
            
            # Parse with Pydantic
            parsed = model_cls.model_validate_json(raw_response)
            
            # Run converter if provided (which does semantic validation)
            if convert:
                return convert(parsed)
            
            # Success!
            return parsed
            
        except (json.JSONDecodeError, ValueError, LLMError) as exc:
            exc_name = type(exc).__name__
            error_msg = str(exc)
            
            # Log rejection with preview
            preview = _response_preview(raw_response)
            logger.warning(
                "%s rejected on attempt %d: %s: %s. Response preview: %s",
                label,
                attempt + 1,
                exc_name,
                error_msg,
                preview
            )
            
            # If this was the last attempt, give up
            if attempt + 1 >= attempts:
                logger.error(
                    "%s failed after %d attempts. Last error: %s",
                    label,
                    attempts,
                    error_msg
                )
                return None
            
            # Retry with error appended to conversation
            conversation.append({
                "role": "assistant",
                "content": raw_response or "(no response)"
            })
            conversation.append({
                "role": "user",
                "content": f"That response was rejected: {error_msg}. Please fix the issues and try again."
            })
    
    return None
