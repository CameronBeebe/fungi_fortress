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
    model_name: str = "gemini-1.5-flash-latest"  # Default model
    context_level: str = "medium"  # Default context level (low, medium, high)
    enable_llm_fallback_responses: bool = True # Whether to use LLM for generic fallbacks if available
    offering_item: Optional[str] = None # Specific item Oracle might ask for (optional)
    offering_amount: int = 0 # Amount of specific item (if any)
    is_real_api_key_present: bool = False # True if api_key is not None, empty, or a known placeholder

    def __post_init__(self):
        """Validate and finalize configuration after initialization."""
        if self.api_key and self.api_key.strip() and self.api_key not in ["YOUR_API_KEY_HERE", "testkey123", "None", ""]:
            self.is_real_api_key_present = True
        else:
            self.is_real_api_key_present = False
            if self.api_key in ["YOUR_API_KEY_HERE", "testkey123", "None", ""]: # Log if it's a known placeholder or empty
                 logger.info(f"API key is a placeholder or empty: \'{self.api_key}\'")

def load_oracle_config(config_file_name: str = DEFAULT_CONFIG_FILENAME) -> OracleConfig:
    """Loads Oracle configuration from the specified .ini file.

    Reads API key, model name, and context level from the [OracleAPI] section.
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
            print(f"INFO: Configuration file '{config_file_name}' not found.")
            print(f"To enable LLM features, please copy '{example_config_path}' to '{config_file_path}' and add your API key.")
            print("See README.md for more details.")
        else:
            print(f"INFO: Configuration file '{config_file_name}' not found and no example configuration was found.")
            print("LLM features will be disabled. See README.md for manual configuration instructions if you wish to use them.")
        return OracleConfig() 

    api_key: Optional[str] = None
    model_name: Optional[str] = None
    context_level: str = "medium" # Default context level

    if "OracleAPI" in parser:
        api_key = parser["OracleAPI"].get("api_key")
        if not api_key: # Only treat truly empty as no key for loading purposes
            api_key = None
            logger.info(f"API key not configured or is empty in '{config_file_path}'.")

        model_name = parser["OracleAPI"].get("model_name")
        if not model_name: # If model_name is empty in the file
            model_name = None 
            
        context_level_from_file = parser["OracleAPI"].get("context_level")
        if context_level_from_file in ["low", "medium", "high"]:
            context_level = context_level_from_file
        elif context_level_from_file: # If it's set but not a valid option
            logger.warning(f"Invalid 'context_level' in '{config_file_path}'. Using default '{context_level}'.")

    else:
        logger.warning(f"[OracleAPI] section not found in '{config_file_path}'. Oracle LLM features may be unavailable.")
        # api_key will remain None, which is the desired behavior

    return OracleConfig(api_key=api_key, model_name=model_name, context_level=context_level)

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