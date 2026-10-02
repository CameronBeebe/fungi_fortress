import configparser
from typing import Optional, Dict, List
import os
import logging
from dataclasses import dataclass

from . import llm_client

# Get a logger instance for LLM interactions
logger = logging.getLogger(__name__)

# --- Path configuration for LLM config files ---
# Config files should be in the repo root (parent of the package)
PACKAGE_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG_FILENAME = "llm_config.ini"
# --- End Path configuration ---

@dataclass
class LLMConfig:
    """Configuration for LLM interactions."""
    api_key: Optional[str] = None
    model_name: str = "grok-3-mini"  # Default model
    provider: str = "auto"  # Provider: auto, xai, groq, openai, anthropic, etc.
    base_url: Optional[str] = None  # Optional base URL override (for Ollama, OpenRouter, etc.)
    context_level: str = "medium"  # Default context level (low, medium, high)
    enable_llm_fallback_responses: bool = True # Whether to use LLM for generic fallbacks if available
    offering_item: Optional[str] = None # Specific item Oracle might ask for (optional)
    offering_amount: int = 0 # Amount of specific item (if any)
    is_real_api_key_present: bool = False # True if api_key is not None, empty, or a known placeholder
    
    # Cost control and safety settings
    max_tokens: int = 500  # Maximum tokens per response to prevent runaway costs
    timeout_seconds: int = 30  # API call timeout in seconds
    max_retries: int = 2  # Maximum number of retries on failure
    retry_delay_seconds: float = 1.0  # Delay between retries
    daily_request_limit: int = 100  # Maximum requests per day (cost control)
    enable_request_logging: bool = True  # Whether to log all API requests for monitoring
    enable_structured_outputs: bool = True  # Whether to use structured outputs feature
    enable_streaming: bool = True  # Whether to enable streaming responses for more lifelike Oracle interactions

    def __post_init__(self):
        """Validate and finalize configuration after initialization."""
        if self.api_key and self.api_key.strip() and self.api_key not in ["YOUR_API_KEY_HERE", "testkey123", "None", ""]:
            self.is_real_api_key_present = True
        else:
            self.is_real_api_key_present = False
            if self.api_key in ["YOUR_API_KEY_HERE", "testkey123", "None", ""]: # Log if it's a known placeholder or empty
                 logger.info(f"API key is a placeholder or empty: \'{self.api_key}\'")
        
        # Validate safety limits
        if self.max_tokens <= 0 or self.max_tokens > 4000:
            logger.warning(f"max_tokens value {self.max_tokens} is outside safe range (1-4000). Using 500.")
            self.max_tokens = 500
            
        if self.timeout_seconds <= 0 or self.timeout_seconds > 120:
            logger.warning(f"timeout_seconds value {self.timeout_seconds} is outside safe range (1-120). Using 30.")
            self.timeout_seconds = 30
            
        if self.daily_request_limit < 0 or self.daily_request_limit > 1000:
            logger.warning(f"daily_request_limit value {self.daily_request_limit} is outside safe range (0-1000, 0=unlimited). Using 100.")
            self.daily_request_limit = 100
    
    def create_llm_client(self) -> llm_client.LLMClient:
        """Create an LLM client from this configuration.
        
        Returns:
            Configured LLMClient instance (may be mock if no valid API key)
        """
        return llm_client.create_client_from_config(
            model=self.model_name or "gpt-4o-mini",
            provider=self.provider,
            api_key=self.api_key,
            base_url=self.base_url,
            max_tokens=self.max_tokens,
            timeout_seconds=self.timeout_seconds,
            temperature=0.7,
        )

def get_api_key_from_env(provider: str) -> Optional[str]:
    """Get API key from environment variables based on provider.
    
    Args:
        provider: The LLM provider name (xai, openai, anthropic, groq, together, perplexity)
        
    Returns:
        The API key from environment variables, or None if not found
    """
    env_var_map = {
        "xai": "XAI_API_KEY",
        "openai": "OPENAI_API_KEY", 
        "anthropic": "ANTHROPIC_API_KEY",
        "groq": "GROQ_API_KEY",
        "together": "TOGETHER_API_KEY",
        "perplexity": "PERPLEXITY_API_KEY"
    }
    
    env_var = env_var_map.get(provider.lower())
    if env_var:
        api_key = os.getenv(env_var)
        if api_key:
            logger.info(f"Found API key for {provider} in environment variable {env_var}")
            return api_key
        else:
            logger.info(f"No API key found in environment variable {env_var} for provider {provider}")
    else:
        logger.warning(f"Unknown provider '{provider}' - cannot determine environment variable")
    
    return None

def detect_provider_from_model(model_name: str) -> str:
    """Auto-detect provider based on model name.
    
    Delegates to llm_client._detect_provider_from_model for consistency.
    
    Args:
        model_name: The model name to analyze
        
    Returns:
        The detected provider name
        
    Raises:
        ValueError: If model name doesn't match any known provider
    """
    if not model_name:
        raise ValueError("Model name is required for provider detection")
    
    return llm_client._detect_provider_from_model(model_name)

def load_llm_config(config_file_name: str = DEFAULT_CONFIG_FILENAME) -> LLMConfig:
    """Loads LLM configuration from the specified .ini file.

    Reads model name, provider, and other settings from the [LLM] section.
    API keys are loaded from environment variables for security.

    Args:
        config_file_name (str): The name of the configuration file.
                                Defaults to "llm_config.ini".

    Returns:
        LLMConfig: An instance of LLMConfig populated with settings from the file.
                   If the file is not found or a setting is missing, defaults will be used.
    """
    parser = configparser.ConfigParser()
    
    # Construct path relative to this file's directory
    config_file_path = os.path.join(PACKAGE_ROOT_DIR, config_file_name)
    
    logger.info(f"Attempting to load config from: {config_file_path}")

    try:
        with open(config_file_path, 'r') as f:
            parser.read_file(f)
    except FileNotFoundError:
        logger.info(f"Configuration file '{config_file_path}' not found.")
        
        # Check for API keys in environment even without config file
        # Try each provider's key to determine which one to use
        for provider_name in ["xai", "openai", "anthropic", "groq", "together", "perplexity"]:
            api_key = get_api_key_from_env(provider_name)
            if api_key:
                logger.info(f"Found {provider_name.upper()} API key in environment, using defaults for that provider")
                # Return config with detected provider and default model
                default_models = {
                    "xai": "grok-3-mini",
                    "openai": "gpt-4o-mini",
                    "anthropic": "claude-3-5-sonnet-20241022",
                    "groq": "llama-3.3-70b-versatile",
                    "together": "meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo",
                    "perplexity": "llama-3.1-sonar-large-128k-online",
                }
                return LLMConfig(
                    api_key=api_key,
                    model_name=default_models.get(provider_name, "gpt-4o-mini"),
                    provider=provider_name,
                    context_level="medium",
                    max_tokens=1000,
                    timeout_seconds=60,
                )
        
        # No API keys found either
        logger.info("No API keys found in environment. LLM will use mock provider (offline mode).")
        return LLMConfig() 

    # Default values
    model_name: Optional[str] = None
    provider: str = "auto"
    base_url: Optional[str] = None
    context_level: str = "medium"
    
    # Safety settings with defaults
    max_tokens: int = 500
    timeout_seconds: int = 30
    max_retries: int = 2
    retry_delay_seconds: float = 1.0
    daily_request_limit: int = 100
    enable_request_logging: bool = True
    enable_structured_outputs: bool = True
    enable_streaming: bool = True

    # Load from [LLM] section
    if "LLM" in parser:
        model_name = parser["LLM"].get("model_name")
        if not model_name:
            model_name = None 
            
        provider = parser["LLM"].get("provider", "auto")
        if provider not in ["auto", "xai", "groq", "openai", "anthropic", "together", "perplexity"]:
            logger.warning(f"Invalid 'provider' in '{config_file_path}'. Using default 'auto'.")
            provider = "auto"
        
        # Optional base URL override
        base_url = parser["LLM"].get("base_url")
        if base_url:
            logger.info(f"Using custom base URL: {base_url}")
            
        context_level_from_file = parser["LLM"].get("context_level")
        if context_level_from_file in ["low", "medium", "high"]:
            context_level = context_level_from_file
        elif context_level_from_file:
            logger.warning(f"Invalid 'context_level' in '{config_file_path}'. Using default '{context_level}'.")
        
        # Load safety settings from config file with validation
        try:
            max_tokens = parser["LLM"].getint("max_tokens", fallback=500)
            if max_tokens <= 0 or max_tokens > 4000:
                logger.warning(f"max_tokens value {max_tokens} in config is outside safe range. Using 500.")
                max_tokens = 500
        except ValueError:
            logger.warning(f"Invalid max_tokens value in config. Using default 500.")
            max_tokens = 500
            
        try:
            timeout_seconds = parser["LLM"].getint("timeout_seconds", fallback=30)
            if timeout_seconds <= 0 or timeout_seconds > 120:
                logger.warning(f"timeout_seconds value {timeout_seconds} in config is outside safe range. Using 30.")
                timeout_seconds = 30
        except ValueError:
            logger.warning(f"Invalid timeout_seconds value in config. Using default 30.")
            timeout_seconds = 30
            
        try:
            max_retries = parser["LLM"].getint("max_retries", fallback=2)
            if max_retries < 0 or max_retries > 5:
                logger.warning(f"max_retries value {max_retries} in config is outside safe range. Using 2.")
                max_retries = 2
        except ValueError:
            logger.warning(f"Invalid max_retries value in config. Using default 2.")
            max_retries = 2
            
        try:
            retry_delay_seconds = parser["LLM"].getfloat("retry_delay_seconds", fallback=1.0)
            if retry_delay_seconds < 0 or retry_delay_seconds > 10:
                logger.warning(f"retry_delay_seconds value {retry_delay_seconds} in config is outside safe range. Using 1.0.")
                retry_delay_seconds = 1.0
        except ValueError:
            logger.warning(f"Invalid retry_delay_seconds value in config. Using default 1.0.")
            retry_delay_seconds = 1.0
            
        try:
            daily_request_limit = parser["LLM"].getint("daily_request_limit", fallback=100)
            if daily_request_limit < 0 or daily_request_limit > 1000:
                logger.warning(f"daily_request_limit value {daily_request_limit} in config is outside safe range (0-1000, 0=unlimited). Using 100.")
                daily_request_limit = 100
        except ValueError:
            logger.warning(f"Invalid daily_request_limit value in config. Using default 100.")
            daily_request_limit = 100
            
        enable_request_logging = parser["LLM"].getboolean("enable_request_logging", fallback=True)
        enable_structured_outputs = parser["LLM"].getboolean("enable_structured_outputs", fallback=True)
        enable_streaming = parser["LLM"].getboolean("enable_streaming", fallback=True)

    else:
        logger.warning(f"[LLM] section not found in '{config_file_path}'. LLM features may be unavailable.")

    # Determine actual provider for API key lookup
    # Precedence: 1) explicit provider, 2) detect from model, 3) detect from env key
    actual_provider = provider
    
    if provider != "auto":
        # Explicit provider in config wins
        logger.info(f"Using explicit provider '{provider}' from config")
        actual_provider = provider
    elif model_name:
        # Auto-detect from model name
        try:
            actual_provider = detect_provider_from_model(model_name)
            logger.info(f"Auto-detected provider '{actual_provider}' for model '{model_name}'")
        except ValueError as e:
            logger.error(f"Provider detection failed: {e}")
            raise
    else:
        # No explicit provider and no model - check which env key is set
        for provider_name in ["xai", "openai", "anthropic", "groq", "together", "perplexity"]:
            if get_api_key_from_env(provider_name):
                actual_provider = provider_name
                logger.info(f"Auto-detected provider '{actual_provider}' from environment key")
                break
        else:
            # No env keys found
            logger.info("No provider specified and no API keys in environment")
            actual_provider = "openai"  # Default for mock

    # Get API key from environment variables
    api_key = get_api_key_from_env(actual_provider)

    return LLMConfig(
        api_key=api_key, 
        model_name=model_name, 
        provider=provider,
        base_url=base_url,
        context_level=context_level,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        retry_delay_seconds=retry_delay_seconds,
        daily_request_limit=daily_request_limit,
        enable_request_logging=enable_request_logging,
        enable_structured_outputs=enable_structured_outputs,
        enable_streaming=enable_streaming
    )

if __name__ == "__main__":
    # Example usage and test
    print("Attempting to load LLM configuration...")
    config = load_llm_config()
    if config.api_key:
        print(f"  API Key: {'*' * (len(config.api_key) - 4) + config.api_key[-4:]}") # Masked
    else:
        print("  API Key: Not configured.")
    print(f"  Model Name: {config.model_name if config.model_name else 'Not specified (will use default)'}")
    print(f"  Provider: {config.provider}")
    print(f"  Context Level: {config.context_level}")

    # Test with a non-existent file
    print("\nAttempting to load non-existent configuration...")
    non_existent_config = load_llm_config("non_existent_config.ini")
    print(f"  API Key (non-existent file): {non_existent_config.api_key}") 