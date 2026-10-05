import configparser
from typing import Optional, Dict, List
import os
import logging
from dataclasses import dataclass, field, fields, MISSING as DATACLASS_MISSING

from . import llm_client

# Get a logger instance for LLM interactions
logger = logging.getLogger(__name__)

# --- Path configuration for LLM config files ---
# Config files should be in the repo root (parent of the package)
PACKAGE_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG_FILENAME = "llm_config.ini"
# --- End Path configuration ---

# Validation ranges for numeric config fields (single source of truth)
FIELD_VALIDATION_RANGES = {
    "max_tokens": (1, 4000),
    "timeout_seconds": (1, 120),
    "max_retries": (0, 5),
    "retry_delay_seconds": (0.0, 10.0),
    "daily_request_limit": (0, 1000),
}

# Placeholder API keys that should be treated as missing (single source of truth)
PLACEHOLDER_API_KEYS = frozenset({"YOUR_API_KEY_HERE", "None", ""})

@dataclass
class LLMConfig:
    """Configuration for XAI LLM interactions (defaults are single source of truth)."""
    api_key: Optional[str] = field(default=None, repr=False)  # Redacted from repr to prevent leaks
    model_name: str = "grok-4.3"
    reasoning_effort: str = "low"  # XAI reasoning effort (none/low/medium/high/xhigh)
    temperature: float = 0.7  # Sampling temperature for generation
    context_level: str = "medium"  # Default context level (low, medium, high)
    enable_llm_fallback_responses: bool = True # Whether to use LLM for generic fallbacks if available
    offering_item: Optional[str] = None # Specific item Oracle might ask for (optional)
    offering_amount: int = 0 # Amount of specific item (if any)
    
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
        
        # Validate numeric fields using centralized validation
        _validate_numeric_fields(self)
    def create_llm_client(self) -> llm_client.LLMClient:
        """Create an LLM client from this configuration.
        
        Returns:
            Configured LLMClient instance (may be mock if no valid API key)
        """
        return llm_client.LLMClient(self)

def _validate_numeric_fields(config: LLMConfig) -> None:
    """Validate numeric fields against safe ranges, falling back to dataclass defaults.
    
    Args:
        config: LLMConfig instance to validate (modified in place)
    """
    # Get dataclass field defaults for fallback
    field_defaults = {f.name: f.default for f in fields(LLMConfig) if f.default is not DATACLASS_MISSING}
    
    for field_name, (min_val, max_val) in FIELD_VALIDATION_RANGES.items():
        current_value = getattr(config, field_name)
        if not (min_val <= current_value <= max_val):
            default_value = field_defaults.get(field_name)
            logger.warning(
                f"{field_name} value {current_value} outside safe range ({min_val}-{max_val}). "
                f"Falling back to {default_value}."
            )
            setattr(config, field_name, default_value)


def get_xai_api_key_from_env() -> Optional[str]:
    """Get XAI API key from environment variables.
    
    Returns:
        The XAI_API_KEY from environment variables, or None if not found
    """
    api_key = os.getenv("XAI_API_KEY")
    if api_key:
        logger.info("Found XAI_API_KEY in environment")
        return api_key
    else:
        logger.info("No XAI_API_KEY found in environment")
    
    return None

def load_llm_config(config_file_name: str = DEFAULT_CONFIG_FILENAME) -> LLMConfig:
    """Loads XAI LLM configuration from the specified .ini file.

    Reads model name and other settings from the [LLM] section.
    API keys are loaded from environment variables (XAI_API_KEY) for security.

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
        # Use defaults from LLMConfig, override api_key from env if present
        api_key = get_xai_api_key_from_env()
        return LLMConfig(api_key=api_key) 

    # Start with defaults from LLMConfig dataclass
    config = LLMConfig()
    
    # Override api_key from environment (is_real_api_key_present computed via @property)
    config.api_key = get_xai_api_key_from_env()
    
    # Override fields from [LLM] section if present
    if "LLM" in parser:
        if "model_name" in parser["LLM"]:
            config.model_name = parser["LLM"]["model_name"]
        
        if "reasoning_effort" in parser["LLM"]:
            config.reasoning_effort = parser["LLM"]["reasoning_effort"]
            
        context_level = parser["LLM"].get("context_level")
        if context_level in ["low", "medium", "high"]:
            config.context_level = context_level
        elif context_level:
            logger.warning(f"Invalid 'context_level' in '{config_file_path}'. Using default.")
        
        # Load numeric safety settings from config file
        for field_name in FIELD_VALIDATION_RANGES.keys():
            if field_name in parser["LLM"]:
                try:
                    # Use getfloat for float fields, getint for others
                    if field_name == "retry_delay_seconds":
                        value = parser["LLM"].getfloat(field_name)
                    else:
                        value = parser["LLM"].getint(field_name)
                    setattr(config, field_name, value)
                except ValueError:
                    logger.warning(f"Invalid {field_name} value in config. Using default.")
            
        for bool_field in ["enable_request_logging", "enable_structured_outputs", "enable_streaming"]:
            if bool_field in parser["LLM"]:
                try:
                    setattr(config, bool_field, parser["LLM"].getboolean(bool_field))
                except ValueError:
                    logger.warning(f"Invalid {bool_field} value in config. Using default.")
    else:
        logger.warning(f"[LLM] section not found in '{config_file_path}'. Using defaults.")
    
    # Validate all numeric fields before returning
    _validate_numeric_fields(config)
    
    return config

if __name__ == "__main__":
    # Example usage and test
    print("Attempting to load LLM configuration...")
    config = load_llm_config()
    if config.api_key:
        print(f"  API Key: {'*' * (len(config.api_key) - 4) + config.api_key[-4:]}") # Masked
    else:
        print("  API Key: Not configured.")
    print(f"  Model Name: {config.model_name if config.model_name else 'Not specified (will use default)'}")
    print(f"  Context Level: {config.context_level}")

    # Test with a non-existent file
    print("\nAttempting to load non-existent configuration...")
    non_existent_config = load_llm_config("non_existent_config.ini")
    print(f"  API Key (non-existent file): {non_existent_config.api_key}") 