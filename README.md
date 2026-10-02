# Fungi Fortress

A terminal-based strategy/simulation game written in Python using the curses library. Manage a dwarf, explore, gather resources, and interact with a world of fungi!

## 🤖 LLM Integration Status

**✅ PRODUCTION-READY + OFFLINE MODE** - The Oracle LLM integration is fully ready for both live API usage and offline play:

- **🎮 Offline Mode**: Built-in mock provider - fully playable with no API key required
- **⚡ Unified Client**: Single OpenAI-compatible interface for all providers
- **🔧 Multi-Provider**: Supports XAI (Grok), OpenAI (GPT), Anthropic (Claude), Groq, Together, Perplexity
- **🛡️ Typed Errors**: Clear error handling with player-friendly messages
- **📊 Battle-Tested**: 40+ new tests for client, mock provider, Oracle integration, and error handling

**Quick Setup**: 
- **No API key?** Just play! The game uses a deterministic mock Oracle.
- **Have an API key?** Set it as an environment variable (e.g., `export OPENAI_API_KEY="sk-..."`), and the game auto-detects your provider.

See [LLM Oracle Integration](#llm-oracle-integration) below for details.

## Features (Current)

*   Curses-based graphical interface
*   Map generation and exploration
*   Basic dwarf task management (moving, simple actions)
*   Resource tracking (in-memory)
*   Inventory and Shop screens (basic implementation)
*   Mycelial network concepts

## Requirements

*   Python 3.10+ (3.12 recommended)
*   **Terminal:** Minimum 70 columns × 45 rows for proper display
*   **C compiler** (for `noise` package):
    *   **macOS:** `xcode-select --install`
    *   **Linux:** Usually pre-installed (`gcc`/`build-essential`)
    *   **Windows:** Visual C++ Build Tools or similar
*   **curses:**
    *   **Linux/macOS:** Included with Python
    *   **Windows:** Automatically installed via `windows-curses` dependency

## Installation

### Using uv (Recommended - Fast!)

[uv](https://github.com/astral-sh/uv) is a fast Python package manager that handles virtual environments and dependencies automatically.

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone <repository-url>
cd fungi-fortress

# Install dependencies (creates .venv automatically, uses uv.lock for exact versions)
uv sync

# Run the game
uv run fungi
```

### Using pip (Traditional Method)

```bash
# Clone the repository
git clone <repository-url>
cd fungi-fortress

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package with dev dependencies
pip install -e ".[dev]"

# Run the game
fungi
```

## How to Run

After installation with **uv**:
```bash
uv run fungi                    # Console command (recommended)
uv run python -m fungi_fortress # As module
uv run python main.py          # Direct script
```

After installation with **pip** (in activated venv):
```bash
fungi                    # Console command (recommended)
python -m fungi_fortress # As module
python main.py          # Direct script
```

### Optional: Set up API Key for LLM features

**The game is fully playable without an API key** - the built-in mock Oracle provides deterministic responses.

To use live LLM providers:

*   Set your API key as an environment variable (for security):
    ```bash
    # For OpenAI:         export OPENAI_API_KEY="your-openai-api-key-here"
    # For XAI (Grok):     export XAI_API_KEY="your-xai-api-key-here"
    # For Anthropic:      export ANTHROPIC_API_KEY="your-anthropic-api-key-here"
    # For Groq:           export GROQ_API_KEY="your-groq-api-key-here"
    # For Together:       export TOGETHER_API_KEY="your-together-api-key-here"
    # For Perplexity:     export PERPLEXITY_API_KEY="your-perplexity-api-key-here"
    ```
*   Optionally, copy `llm_config.ini.example` to `llm_config.ini` to configure model and parameters
*   The game automatically detects which provider to use based on your model name
*   **No API key?** The game automatically uses the mock provider (offline mode)

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

### Running Tests

With **uv**:
```bash
# Run all tests
uv run pytest -q

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_game_logic.py
```

With **pip** (in activated venv):
```bash
# Run all tests
pytest -q

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_game_logic.py
```

### Running Type Checks

With **uv**:
```bash
uv run mypy fungi_fortress/
```

With **pip** (in activated venv):
```bash
mypy fungi_fortress/
```

### Development Setup

**Using uv** (recommended):
```bash
uv sync  # Installs all dependencies including dev tools
```

**Using pip**:
```bash
pip install -e ".[dev]"
```

This installs pytest, mypy, and other development tools.

## Known Issues

*   **Level 1 Pathfinding:** Harvesting magic fungi on the first level may not illuminate a path to the `nexus_site` if the only path requires crossing water tiles, as there is currently no mechanism for the player to cross water. Design question: Should the path still illuminate through water, or should we add water-crossing mechanics?
*   **Code Quality:** Test coverage and type hint coverage are currently low.

## Development Goals

*   **Procedural Content Generation:** Integrate Large Language Model (LLM) APIs to enable player-driven procedural generation of game content, including maps, story elements, characters, and events.
*   **Improve Test Coverage:** Write comprehensive unit and integration tests for core game logic, map generation, entities, and utilities.
*   **Enhance Type Hinting:** Add type hints throughout the codebase and resolve any issues reported by `mypy` to improve code robustness and maintainability.

### Detailed Technical TODOs

*   **Event System (`events.py`):**
    *   Implement the `trigger_event` function to handle game event initiation.
    *   Implement the `check_events` function for ongoing event condition checking.
*   **Interactions (`interactions.py`):**
    *   Develop and implement the UI and core functionality for the Dwarven Sporeforge interaction (`interact_dwarven_sporeforge_logic`).
*   **Map Generation & Entities (`map_generation.py`, `tiles.py`):**
    *   Define a "mineral_deposit" entity in the `ENTITY_REGISTRY` and integrate its spawning into grotto map generation.
    *   Define a walkable "shallow_water" entity in the `ENTITY_REGISTRY` and implement its use for river fords in surface map generation. This could also help address pathfinding issues across water.
*   **LLM Integration (`llm_interface.py`):**
    *   Implement true streaming support for Anthropic models in `_detect_provider_and_call_api_streaming` instead of the current non-streaming fallback.
    *   Expand `handle_game_event` to process a wider variety of game events (e.g., dynamic event generation, NPC behavior adaptations) using LLM capabilities.
    *   Refine LLM prompt context by selectively adding more detailed and relevant game state information to `handle_oracle_query_streaming` and `handle_oracle_query_non_streaming`.
    *   Standardize LLM provider detection: Ensure the logic in `_detect_provider_and_call_api` (for non-streaming calls) is consistent with `config_manager.detect_provider_from_model`, ideally by calling the centralized function.
    *   Consider creating a dedicated `_call_anthropic_api` function for non-streaming Anthropic calls if it offers unique features or requires specific error handling beyond the generic OpenAI-compatible wrapper.
*   **Gameplay Features:**
    *   Further develop dwarf task management (e.g., more complex tasks, dwarf skills affecting outcomes beyond mining).
    *   Expand shop functionality (e.g., dynamic pricing, wider item variety).
    *   Flesh out the Mycelial Network mechanics beyond path illumination (e.g., resource transfer, environmental effects).

## Contributing

Contributions are welcome! Please feel free to open issues or submit pull requests. (Further contribution guidelines TBD).

## LLM Oracle Integration

Fungi Fortress features an AI-powered Oracle that provides guidance, lore, and interactive storytelling. The Oracle system supports **both offline and online modes**:

- **🎮 Offline Mode**: Built-in mock Oracle provides deterministic, in-character responses with no API needed
- **🌐 Online Mode**: Connect to any OpenAI-compatible LLM provider for dynamic responses

**🚀 PRODUCTION-READY + OFFLINE-READY** - The unified LLM client is stable, tested, and works great whether you're online or offline.

### Recent Improvements (Latest Update)

- **✅ Unified Client Architecture**: Single, clean interface for all LLM interactions
- **✅ Mock Provider**: Fully playable offline with deterministic Oracle responses
- **✅ Typed Error Handling**: Clear exceptions with player-friendly messages
- **✅ Comprehensive Test Suite**: 205+ tests passing, including 40 new tests for the unified client
- **✅ Provider Auto-Detection**: Automatically selects the correct API based on model name
- **✅ Streaming Support**: Real-time Oracle responses for engaging gameplay
- **✅ OpenAI-Compatible**: Works with OpenAI, XAI (Grok), Anthropic (Claude), Groq, Together, Perplexity

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