import configparser
from typing import Optional, Dict, List # Added Dict, List for future use if needed here
import os
import logging # Import logging
from dataclasses import dataclass

# Get a logger instance (it will inherit the config from main.py if run after main's setup)
# Or, if this module is imported before main's basicConfig, it might log to console by default.
# For robustness in this specific debug case, we ensure it uses the same file if possible,
# but basicConfig in main should cover it if main runs first.
logger = logging.getLogger(__name__) 
# If we wanted to be absolutely sure it logs to our file even if imported first:
# if not logging.getLogger().hasHandlers():
#     logging.basicConfig(
#         filename="ff_init_debug.log", level=logging.INFO, 
#         format='%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s', filemode='a'
#     )

# --- Path configuration for oracle_config.ini ---
# Assumes oracle_config.ini is in the same directory as this script (package root)
PACKAGE_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_FILENAME = "oracle_config.ini"
# --- End Path configuration ---

@dataclass
class OracleConfig:
    """Configuration for Oracle LLM interactions."""
    api_key: Optional[str] = None
    model_name: str = "gpt-4o-mini"  # Default model
    provider: str = "auto"  # Provider: auto, xai, groq, openai, anthropic, etc.
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
    enable_structured_outputs: bool = True  # Whether to use XAI structured outputs feature

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
            
        if self.daily_request_limit <= 0 or self.daily_request_limit > 1000:
            logger.warning(f"daily_request_limit value {self.daily_request_limit} is outside safe range (1-1000). Using 100.")
            self.daily_request_limit = 100

def load_oracle_config(config_file_name: str = DEFAULT_CONFIG_FILENAME) -> OracleConfig:
    """Loads Oracle configuration from the specified .ini file.

    Reads API key, model name, provider, and context level from the [OracleAPI] section.
    Handles cases where the file or specific settings might be missing.

    Args:
        config_file_name (str): The name of the configuration file.
                                Defaults to "oracle_config.ini".

    Returns:
        OracleConfig: An instance of OracleConfig populated with settings from the file.
                      If the file is not found or a setting is missing, defaults will be used
                      (e.g., api_key will be None).
    """
    parser = configparser.ConfigParser()
    
    # Construct path relative to this file's directory
    config_file_path = os.path.join(PACKAGE_ROOT_DIR, config_file_name)
    
    logger.info(f"Attempting to load config from: {config_file_path}") # Use the constructed full path

    try:
        # Use the constructed full path here too
        with open(config_file_path, 'r') as f:
            parser.read_file(f)
    except FileNotFoundError:
        logger.info(f"Configuration file '{config_file_path}' not found. Oracle LLM features may be unavailable.")
        example_config_path = os.path.join(PACKAGE_ROOT_DIR, "oracle_config.ini.example")
        if os.path.exists(example_config_path):
            logger.info(f"Configuration file '{config_file_name}' not found.")
            logger.info(f"To enable LLM features, please copy '{example_config_path}' to '{config_file_path}' and add your API key.")
            logger.info("See README.md for more details.")
        else:
            logger.info(f"Configuration file '{config_file_name}' not found and no example configuration was found.")
            logger.info("LLM features will be disabled. See README.md for manual configuration instructions if you wish to use them.")
        return OracleConfig() 

    api_key: Optional[str] = None
    model_name: Optional[str] = None
    provider: str = "auto" # Default provider setting
    context_level: str = "medium" # Default context level
    
    # Safety settings with defaults
    max_tokens: int = 500
    timeout_seconds: int = 30
    max_retries: int = 2
    retry_delay_seconds: float = 1.0
    daily_request_limit: int = 100
    enable_request_logging: bool = True
    enable_structured_outputs: bool = True

    if "OracleAPI" in parser:
        api_key = parser["OracleAPI"].get("api_key")
        if not api_key: # Only treat truly empty as no key for loading purposes
            api_key = None
            logger.info(f"API key not configured or is empty in '{config_file_path}'.")

        model_name = parser["OracleAPI"].get("model_name")
        if not model_name: # If model_name is empty in the file
            model_name = None 
            
        provider = parser["OracleAPI"].get("provider", "auto")
        if provider not in ["auto", "xai", "groq", "openai", "anthropic", "together", "perplexity"]:
            logger.warning(f"Invalid 'provider' in '{config_file_path}'. Using default 'auto'.")
            provider = "auto"
            
        context_level_from_file = parser["OracleAPI"].get("context_level")
        if context_level_from_file in ["low", "medium", "high"]:
            context_level = context_level_from_file
        elif context_level_from_file: # If it's set but not a valid option
            logger.warning(f"Invalid 'context_level' in '{config_file_path}'. Using default '{context_level}'.")
        
        # Load safety settings from config file with validation
        try:
            max_tokens = parser["OracleAPI"].getint("max_tokens", fallback=500)
            if max_tokens <= 0 or max_tokens > 4000:
                logger.warning(f"max_tokens value {max_tokens} in config is outside safe range. Using 500.")
                max_tokens = 500
        except ValueError:
            logger.warning(f"Invalid max_tokens value in config. Using default 500.")
            max_tokens = 500
            
        try:
            timeout_seconds = parser["OracleAPI"].getint("timeout_seconds", fallback=30)
            if timeout_seconds <= 0 or timeout_seconds > 120:
                logger.warning(f"timeout_seconds value {timeout_seconds} in config is outside safe range. Using 30.")
                timeout_seconds = 30
        except ValueError:
            logger.warning(f"Invalid timeout_seconds value in config. Using default 30.")
            timeout_seconds = 30
            
        try:
            max_retries = parser["OracleAPI"].getint("max_retries", fallback=2)
            if max_retries < 0 or max_retries > 5:
                logger.warning(f"max_retries value {max_retries} in config is outside safe range. Using 2.")
                max_retries = 2
        except ValueError:
            logger.warning(f"Invalid max_retries value in config. Using default 2.")
            max_retries = 2
            
        try:
            retry_delay_seconds = parser["OracleAPI"].getfloat("retry_delay_seconds", fallback=1.0)
            if retry_delay_seconds < 0 or retry_delay_seconds > 10:
                logger.warning(f"retry_delay_seconds value {retry_delay_seconds} in config is outside safe range. Using 1.0.")
                retry_delay_seconds = 1.0
        except ValueError:
            logger.warning(f"Invalid retry_delay_seconds value in config. Using default 1.0.")
            retry_delay_seconds = 1.0
            
        try:
            daily_request_limit = parser["OracleAPI"].getint("daily_request_limit", fallback=100)
            if daily_request_limit <= 0 or daily_request_limit > 1000:
                logger.warning(f"daily_request_limit value {daily_request_limit} in config is outside safe range. Using 100.")
                daily_request_limit = 100
        except ValueError:
            logger.warning(f"Invalid daily_request_limit value in config. Using default 100.")
            daily_request_limit = 100
            
        enable_request_logging = parser["OracleAPI"].getboolean("enable_request_logging", fallback=True)
        enable_structured_outputs = parser["OracleAPI"].getboolean("enable_structured_outputs", fallback=True)

    else:
        logger.warning(f"[OracleAPI] section not found in '{config_file_path}'. Oracle LLM features may be unavailable.")
        # api_key will remain None, which is the desired behavior

    return OracleConfig(
        api_key=api_key, 
        model_name=model_name, 
        provider=provider, 
        context_level=context_level,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        retry_delay_seconds=retry_delay_seconds,
        daily_request_limit=daily_request_limit,
        enable_request_logging=enable_request_logging,
        enable_structured_outputs=enable_structured_outputs
    )

if __name__ == "__main__":
    # Example usage and test
    print("Attempting to load Oracle configuration...")
    config = load_oracle_config()
    if config.api_key:
        print(f"  API Key: {'*' * (len(config.api_key) - 4) + config.api_key[-4:]}") # Masked
    else:
        print("  API Key: Not configured.")
    print(f"  Model Name: {config.model_name if config.model_name else 'Not specified (will use default)'}")
    print(f"  Context Level: {config.context_level}")

    # Test with a non-existent file
    print("\nAttempting to load non-existent configuration...")
    non_existent_config = load_oracle_config("non_existent_config.ini")
    print(f"  API Key (non-existent file): {non_existent_config.api_key}") 