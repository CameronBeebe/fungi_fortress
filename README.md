# Fungi Fortress

A terminal-based strategy/simulation game written in Python using the curses library. Manage a dwarf, explore, gather resources, and interact with a world of fungi!

## 🤖 LLM Integration Status

**✅ PRODUCTION-READY** - The Oracle LLM integration is now fully ready for live API usage with comprehensive safety features:

- **🛡️ Cost Controls**: Daily request limits, token limits, timeout protection
- **⚡ Reliability**: Smart retry logic, graceful error handling, provider auto-detection  
- **🔧 Multi-Provider**: Supports XAI (Grok), OpenAI (GPT), Anthropic (Claude), Groq
- **📊 Monitoring**: Real-time usage tracking, detailed logging, emergency controls

**Quick Setup**: Copy `llm_config.ini.example` → `llm_config.ini`, set your API key as an environment variable, and play! See [LLM Oracle Integration](#llm-oracle-integration) below for details.

## Features (Current)

*   Curses-based graphical interface
*   Map generation and exploration
*   Basic dwarf task management (moving, simple actions)
*   Resource tracking (in-memory)
*   Inventory and Shop screens (basic implementation)
*   Mycelial network concepts

## Requirements

*   Python 3.7+
*   **curses:**
    *   **Linux/macOS:** Typically included with Python or available through system package managers (e.g., `sudo apt-get install libncursesw5-dev` on Debian/Ubuntu, often pre-installed on macOS).
    *   **Windows:** You need to install the `windows-curses` package:
        ```bash
        pip install windows-curses
        ```
        *(Note: This project is primarily developed/tested on Unix-like systems. Windows compatibility via `windows-curses` may vary.)*
*   **groq:** Current LLM integration testing using the X.AI API (used by the Oracle for LLM features) with groq.
    ```bash
    pip install groq
    ```
*   **LLM SDKs:** For LLM features, the following are installed via `requirements.txt`:
    *   `openai`: For XAI (Grok), OpenAI (GPT), and other OpenAI-compatible APIs.
    *   `groq`: For Groq API.
    *   `requests`: Used for some direct API calls (e.g., Anthropic).

## How to Run

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd fungi-fortress
    ```
2.  **Set up API Key (Optional, for LLM features):**
    This game can use a Large Language Model (LLM) for certain features. To enable these:
    *   Copy `llm_config.ini.example` to `llm_config.ini`
    *   Set your API key as an environment variable (for security):
        ```bash
        # For XAI (Grok):     export XAI_API_KEY="your-xai-api-key-here"
        # For OpenAI:         export OPENAI_API_KEY="your-openai-api-key-here"
        # For Anthropic:      export ANTHROPIC_API_KEY="your-anthropic-api-key-here"
        # For Groq:           export GROQ_API_KEY="your-groq-api-key-here"
        # For Together:       export TOGETHER_API_KEY="your-together-api-key-here"
        # For Perplexity:     export PERPLEXITY_API_KEY="your-perplexity-api-key-here"
        ```
    *   The game automatically detects which API key to use based on your chosen model
    *   **Security:** API keys are stored in environment variables, never in files

3.  **Ensure requirements are met** (see above, especially for `curses` on Windows).
4.  **Run the game:**
    ```bash
    python main.py
    ```
    *(Alternatively, if running as an installed module later: `python -m fungi_fortress.main`)*

## Basic Controls

*   **Arrow Keys:** Move cursor / navigate menus
*   **Enter:** Confirm selection / interact
*   **ESC:** Quit game / Close open menus
*   **i:** Toggle Inventory
*   **q:** Open Quest/Oracle Content Menu  
*   **l:** Toggle Legend
*   **t:** Talk to adjacent NPCs/Oracles
*   **e:** Enter/Interact with structures
*   **p:** Pause game
*   **m:** Mine/Move (Assign task at cursor)
*   **f:** Fish/Fight (Assign task at cursor)
*   **b:** Build (Assign task at cursor)
*   **d:** Descent/Shop preparation
*   **c:** Cast selected spell
*   **s:** Cycle through spells
*   **1-5:** Select spell slots

### Oracle Dialogue Controls

When consulting an Oracle:
*   **Type normally:** Enter your query (including 'q' safely)
*   **Enter:** Submit query
*   **ESC:** Exit consultation (with confirmation when typing)
*   **Arrow Keys:** Navigate longer responses

## Testing and Type Checking

This project uses `pytest` for testing and `mypy` for static type checking.

1.  **Install Development Dependencies:**
    Ensure you have installed the necessary packages:
    ```bash
    pip install -r requirements.txt
    ```
    *(This includes `pytest` and `mypy` marked as development dependencies).*

2.  **Running Tests:**
    Execute tests from the root directory:
    ```bash
    pytest
    ```

3.  **Running Type Checks:**
    Run the type checker from the root directory:
    ```bash
    mypy .
    ```

## Known Issues

*   **Level 1 Pathfinding:** Harvesting magic fungi on the first level may not illuminate a path to the `nexus_site` if the only path requires crossing water tiles, as there is currently no mechanism for the player to cross water. Design question: Should the path still illuminate through water, or should we add water-crossing mechanics?
*   **Code Quality:** Test coverage and type hint coverage are currently low.

## Development Goals

*   **Procedural Content Generation:** Integrate Large Language Model (LLM) APIs to enable player-driven procedural generation of game content, including maps, story elements, characters, and events.
*   **Improve Test Coverage:** Write comprehensive unit and integration tests for core game logic, map generation, entities, and utilities.
*   **Enhance Type Hinting:** Add type hints throughout the codebase and resolve any issues reported by `mypy` to improve code robustness and maintainability.

## Contributing

Contributions are welcome! Please feel free to open issues or submit pull requests. (Further contribution guidelines TBD).

## LLM Oracle Integration

Fungi Fortress features an AI-powered Oracle that provides guidance, lore, and interactive storytelling through Large Language Model (LLM) integration. The Oracle system is designed to be **flexible and provider-agnostic**, allowing players to use their preferred LLM service and API credits.

**🚀 PRODUCTION-READY** - The LLM integration is fully stable with comprehensive safety features, extensive testing, and robust error handling for live API usage.

### Recent Improvements (Latest Update)

- **✅ Dynamic Text Streaming**: Oracle responses now stream in real-time for a more engaging experience.
- **✅ Enhanced Error Handling**: Improved parsing of malformed LLM responses with graceful degradation
- **✅ Comprehensive Test Suite**: Over 170 tests covering unit tests, integration tests, and live API validation
- **✅ Response Format Support**: Handles both structured JSON responses and legacy text format seamlessly  
- **✅ Provider Auto-Detection**: Automatically selects the correct API based on model name patterns
- **✅ Structured Output**: Supports XAI's structured JSON schema for more reliable responses
- **✅ Integration Tests**: Added `test_integration_game.py` and `tests/test_integration_xai_direct.py` for full pipeline validation

### Supported LLM Providers

The Oracle supports multiple LLM providers through a unified interface:

- **XAI (Grok models)**: Access to Grok-3, Grok-2, and other Grok models via XAI's direct API
  - **NEW**: Full support for structured JSON responses and reasoning tokens
- **OpenAI**: GPT-4o, GPT-4o-mini, GPT-4-turbo, and GPT-3.5-turbo models  
- **Anthropic**: Claude-3.5-Sonnet, Claude-3.5-Haiku, and Claude-3-Opus models
- **Groq**: Fast inference for open-source models like LLaMA, Mixtral, and Gemma
- **Auto-detection**: Automatically chooses the appropriate provider based on model name

### Configuration

Copy `llm_config.ini.example` to `llm_config.ini` and configure your settings:

```ini
[LLM]
# === API KEY CONFIGURATION ===
# API keys are loaded from environment variables for security
# Set these environment variables in your shell or .env file:
#
# For XAI (Grok):     export XAI_API_KEY="your-xai-api-key-here"
# For OpenAI:         export OPENAI_API_KEY="your-openai-api-key-here"
# For Anthropic:      export ANTHROPIC_API_KEY="your-anthropic-api-key-here"
# For Groq:           export GROQ_API_KEY="your-groq-api-key-here"
# For Together:       export TOGETHER_API_KEY="your-together-api-key-here"
# For Perplexity:     export PERPLEXITY_API_KEY="your-perplexity-api-key-here"

# Provider selection (auto, xai, groq, openai, anthropic, together, perplexity)
provider = auto

# Model to use - examples by provider:
# XAI: grok-3, grok-3-beta, grok-2-1212, grok-3-mini, grok-3-mini-fast
# OpenAI: gpt-4o, gpt-4o-mini, gpt-3.5-turbo  
# Anthropic: claude-3-5-sonnet-20241022, claude-3-5-haiku-20241022
# Groq: llama-3.3-70b-versatile, llama-3.1-8b-instant, gemma2-9b-it
# Together: meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo
# Perplexity: llama-3.1-sonar-small-128k-online
model_name = gpt-4o-mini

# Context level for game information (low, medium, high)
context_level = medium

# === COST CONTROL SETTINGS ===
max_tokens = 1000             # Max response length (prevents runaway costs)
daily_request_limit = 0       # Daily API call limit (0 = unlimited)
timeout_seconds = 60          # Request timeout (prevents hanging)
max_retries = 2              # Retry attempts (reliability)
```

### Using Your API Credits

**Secure Environment Variable Setup**: API keys are now stored as environment variables for enhanced security:

```bash
# Add to your shell profile (.bashrc, .zshrc, etc.) for persistence:
export XAI_API_KEY="your-xai-api-key-here"

# Or set for current session only:
export XAI_API_KEY="your-xai-api-key-here"
```

### Testing Infrastructure

The LLM integration includes comprehensive testing:

```bash
# Run all tests (most use mocks, safe for CI)
pytest

# Run only LLM-specific interface tests (uses mocks)
pytest tests/test_llm_interface.py -v

# Run specific integration tests that may require API keys (check .gitignore for these files)
# Example for XAI live endpoint tests:
pytest tests/test_integration_xai_direct.py -v
```

**Test Organization**:
- Unit and integration tests (using mocks) are located in the `tests/` directory.
- Tests designed for live API validation (e.g., `tests/test_integration_xai_direct.py`) are configured in `.gitignore` to prevent accidental key exposure and should be run with caution.