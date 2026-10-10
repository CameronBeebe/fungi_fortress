import os
from typing import Optional
from dataclasses import dataclass, field

from . import llm_client

# Placeholder API keys that should be treated as missing (single source of truth)
PLACEHOLDER_API_KEYS = frozenset({"YOUR_API_KEY_HERE", "None", ""})

@dataclass
class LLMConfig:
    """Configuration for XAI LLM interactions (defaults are single source of truth).
    
    All settings have programmer-controlled defaults defined here. Only api_key is
    read from the environment (XAI_API_KEY). No user config file.
    """
    api_key: Optional[str] = field(default=None, repr=False)  # Redacted from repr to prevent leaks
    model_name: str = "grok-4.3"
    reasoning_effort: str = "low"  # XAI reasoning effort (none/low/medium/high)
    temperature: float = 0.7  # Sampling temperature for generation
    context_level: str = "medium"  # Context level (low, medium, high)
    
    # Cost control and safety settings
    max_tokens: int = 500  # Maximum tokens per response to prevent runaway costs
    timeout_seconds: int = 30  # API call timeout in seconds
    max_retries: int = 2  # Transport-level retries (network, 5xx errors)
    max_validation_retries: int = 2  # Semantic validation retries in structured_call
    enable_structured_outputs: bool = True  # Whether to use structured outputs feature
    enable_streaming: bool = True  # Whether to enable streaming responses for more lifelike Oracle interactions

    @property
    def is_real_api_key_present(self) -> bool:
        """Check if a real (non-placeholder) API key is configured."""
        return bool(self.api_key and self.api_key.strip() and self.api_key.strip() not in PLACEHOLDER_API_KEYS)
    
    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Create LLMConfig from environment variables.
        
        Only reads XAI_API_KEY from environment; all other settings use defaults.
        
        Returns:
            LLMConfig instance with api_key from environment (or None)
        """
        api_key = os.getenv("XAI_API_KEY")
        return cls(api_key=api_key)
    
    def create_llm_client(self) -> llm_client.LLMClient:
        """Create an LLM client from this configuration.
        
        Returns:
            Configured LLMClient instance (may be mock if no valid API key)
        """
        return llm_client.LLMClient(self)
