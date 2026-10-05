import configparser
import os
from typing import Optional
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
    "temperature": (0.0, 2.0),
}

# Allowed values for string config fields (single source of truth)
ALLOWED_REASONING_EFFORTS = frozenset({"none", "low", "medium", "high"})
ALLOWED_CONTEXT_LEVELS = frozenset({"low", "medium", "high"})

# Placeholder API keys that should be treated as missing (single source of truth)
PLACEHOLDER_API_KEYS = frozenset({"YOUR_API_KEY_HERE", "None", ""})

@dataclass
class LLMConfig:
    """Configuration for XAI LLM interactions (defaults are single source of truth)."""
    api_key: Optional[str] = field(default=None, repr=False)  # Redacted from repr to prevent leaks
    model_name: str = "grok-4.3"
    reasoning_effort: str = "low"  # XAI reasoning effort (none/low/medium/high)
    temperature: float = 0.7  # Sampling temperature for generation
    context_level: str = "medium"  # Context level (low, medium, high)
    
    # Cost control and safety settings
    max_tokens: int = 500  # Maximum tokens per response to prevent runaway costs
    timeout_seconds: int = 30  # API call timeout in seconds
    max_retries: int = 2  # Maximum number of retries on failure
    enable_structured_outputs: bool = True  # Whether to use structured outputs feature
    enable_streaming: bool = True  # Whether to enable streaming responses for more lifelike Oracle interactions


    @property
    def is_real_api_key_present(self) -> bool:
        """Check if a real (non-placeholder) API key is configured."""
        return bool(self.api_key and self.api_key.strip() and self.api_key.strip() not in PLACEHOLDER_API_KEYS)
    
    def __post_init__(self):
        """Validate and finalize configuration after initialization."""
        if not self.is_real_api_key_present and self.api_key:
            stripped = self.api_key.strip()
            if stripped in PLACEHOLDER_API_KEYS:
                logger.info(f"API key is a placeholder or empty: '{self.api_key}'")
        
        # Validate numeric and string fields using centralized validation
        _validate_fields(self)
    
    def create_llm_client(self) -> llm_client.LLMClient:
        """Create an LLM client from this configuration.
        
        Returns:
            Configured LLMClient instance (may be mock if no valid API key)
        """
        return llm_client.LLMClient(self)

def _validate_fields(config: LLMConfig) -> None:
    """Validate numeric and string fields against safe ranges/sets, falling back to dataclass defaults.
    
    Args:
        config: LLMConfig instance to validate (modified in place)
    """
    # Get dataclass field defaults for fallback
    field_defaults = {f.name: f.default for f in fields(LLMConfig) if f.default is not DATACLASS_MISSING}
    
    # Validate numeric fields
    for field_name, (min_val, max_val) in FIELD_VALIDATION_RANGES.items():
        current_value = getattr(config, field_name)
        if not (min_val <= current_value <= max_val):
            default_value = field_defaults.get(field_name)
            logger.warning(
                f"Config field '{field_name}' value {current_value} out of range "
                f"[{min_val}, {max_val}]. Using default: {default_value}"
            )
            setattr(config, field_name, default_value)
    
    # Validate reasoning_effort
    if config.reasoning_effort not in ALLOWED_REASONING_EFFORTS:
        default_value = field_defaults.get("reasoning_effort", "low")
        logger.warning(
            f"Config field 'reasoning_effort' value '{config.reasoning_effort}' not in "
            f"{ALLOWED_REASONING_EFFORTS}. Using default: '{default_value}'"
        )
        config.reasoning_effort = default_value
    
    # Validate context_level
    if config.context_level not in ALLOWED_CONTEXT_LEVELS:
        default_value = field_defaults.get("context_level", "medium")
        logger.warning(
            f"Config field 'context_level' value '{config.context_level}' not in "
            f"{ALLOWED_CONTEXT_LEVELS}. Using default: '{default_value}'"
        )
        config.context_level = default_value


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
    """Load LLM configuration from a file, falling back to defaults if file not found.
    
    Args:
        config_file_name: Name of the config file (default: llm_config.ini)
        
    Returns:
        LLMConfig: Configuration object with loaded or default values
    """
    config_file_path = os.path.join(PACKAGE_ROOT_DIR, config_file_name)
    parser = configparser.ConfigParser()
    
    try:
        with open(config_file_path, 'r') as f:
            parser.read_file(f)
    except FileNotFoundError:
        logger.info(f"Configuration file '{config_file_path}' not found.")
        api_key = get_xai_api_key_from_env()
        return LLMConfig(api_key=api_key)
    except (configparser.Error, OSError) as e:
        logger.warning(f"Error loading config file '{config_file_path}': {e}. Using defaults.")
        api_key = get_xai_api_key_from_env()
        return LLMConfig(api_key=api_key)

    # Start with defaults from LLMConfig dataclass
    config = LLMConfig()
    
    # Override api_key from environment (is_real_api_key_present computed via @property)
    config.api_key = get_xai_api_key_from_env()
    
    # Override fields from [LLM] section if present
    if "LLM" not in parser:
        logger.warning(f"[LLM] section not found in '{config_file_path}'. Using defaults.")
        return config
    
    # Generic field loading: iterate over dataclass fields
    for field_info in fields(LLMConfig):
        field_name = field_info.name
        
        # Skip api_key (env-only)
        if field_name == "api_key":
            continue
        
        if field_name not in parser["LLM"]:
            continue
        
        try:
            field_type = field_info.type
            # Handle Optional types
            if hasattr(field_type, '__origin__'):
                field_type = field_type.__args__[0] if field_type.__args__ else str
            
            # Pick parser based on type
            if field_type == bool:
                value = parser["LLM"].getboolean(field_name)
            elif field_type == int:
                value = parser["LLM"].getint(field_name)
            elif field_type == float:
                value = parser["LLM"].getfloat(field_name)
            else:  # str or other
                value = parser["LLM"][field_name]
            
            setattr(config, field_name, value)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid {field_name} value in config: {e}. Using default.")
    
    # Validate all fields before returning
    _validate_fields(config)
    
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