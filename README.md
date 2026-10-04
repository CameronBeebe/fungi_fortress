# Fungi Fortress

A terminal-based strategy/simulation game written in Python using the curses library. Manage a dwarf, explore, gather resources, and interact with a world of fungi!

## 🤖 LLM Integration Status

**✅ OFFLINE + ONLINE MODE** - The Oracle LLM integration supports both offline and online play:

- **🎮 Offline Mode**: Built-in mock provider - fully playable with no API key required
- **⚡ XAI Provider**: Direct integration with XAI (Grok) via `https://api.x.ai/v1`
- **🛡️ Typed Errors**: Clear error handling with player-friendly messages
- **📊 Tested**: 227 tests passing, including client and Oracle integration tests
- **🔒 Secure**: API keys never logged or exposed (field(repr=False), env-only)

**Quick Setup**: 
- **No API key?** Just play! The game uses a deterministic mock Oracle with `[Offline Mode]` indicator.
- **Have an XAI key?** Set `export XAI_API_KEY="your-key"` and enjoy live Grok-powered Oracle responses.

See [LLM Oracle Integration](#llm-oracle-integration) below for details.

## Project Planning & Roadmap

See [`TODO.md`](TODO.md) for the running backlog and [`PLANNING.md`](PLANNING.md) for the overhaul plan and long-term architecture.

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

*   Set your XAI API key as an environment variable (for security):
    ```bash
    export XAI_API_KEY="your-xai-api-key-here"
    ```
*   Optionally, copy `llm_config.ini.example` to `llm_config.ini` to configure model and parameters
*   **No API key?** The game automatically uses the mock provider (offline mode) with `[Offline Mode]` indicator

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
    *   Expand `handle_game_event` to process a wider variety of game events (e.g., dynamic event generation, NPC behavior adaptations) using LLM capabilities.
    *   Refine LLM prompt context by selectively adding more detailed and relevant game state information.
*   **Gameplay Features:**
    *   Further develop dwarf task management (e.g., more complex tasks, dwarf skills affecting outcomes beyond mining).
    *   Expand shop functionality (e.g., dynamic pricing, wider item variety).
    *   Flesh out the Mycelial Network mechanics beyond path illumination (e.g., resource transfer, environmental effects).

## Contributing

Contributions are welcome! Please feel free to open issues or submit pull requests. (Further contribution guidelines TBD).

## LLM Oracle Integration

Fungi Fortress features an AI-powered Oracle that provides guidance, lore, and interactive storytelling. The Oracle system supports **both offline and online modes**:

- **🎮 Offline Mode**: Built-in mock Oracle provides deterministic, in-character responses with no API needed
- **🌐 Online Mode**: Connect to xAI (Grok) for dynamic LLM-powered responses, or use the offline mock provider

The unified LLM client supports both online (xAI/Grok) and offline (mock) modes.

### Recent Improvements (Latest Update)

- **✅ XAI-Only Architecture**: Simplified to XAI (Grok) + mock provider only
- **✅ Mock Provider**: Fully playable offline with deterministic Oracle responses and `[Offline Mode]` indicator
- **✅ Typed Error Handling**: Clear exceptions with player-friendly messages
- **✅ Comprehensive Test Suite**: 227 tests passing
- **✅ Streaming Support**: Real-time Oracle responses for engaging gameplay
- **✅ XAI-Specific Features**: `reasoning_effort` (high/low) and `response_format` (JSON Schema)
- **✅ Security**: API keys never logged (field(repr=False), removed from action details)

### Supported LLM Provider

The Oracle uses **XAI (Grok)** via `https://api.x.ai/v1`:

- **Available Models**:
  - `grok-4.3` (default, recommended)
  - `grok-2-1212`
  - `grok-beta`, `grok-vision-beta`

- **XAI Features**:
  - `reasoning_effort`: "high" for Oracle (quality), "low" for world gen (speed)
  - `response_format`: JSON Schema for structured action parsing

### Configuration

Copy `llm_config.ini.example` to `llm_config.ini` and configure your settings:

```ini
[LLM]
# === API KEY CONFIGURATION ===
# API key is loaded from environment variable for security
# Set this in your shell or .env file:
#
# For XAI (Grok):     export XAI_API_KEY="your-xai-api-key-here"
#
# If not set, the game uses the built-in mock provider (offline mode)

# Model to use (XAI Grok models only):
#   grok-4.3 (default, recommended)
#   grok-2-1212, grok-beta, grok-vision-beta
model_name = grok-4.3

# Context level for game information (low, medium, high)
# low = tick + depth, 1 history turn
# medium = + mission, 3 history turns
# high = + resources, 5 history turns
context_level = medium

# === COST CONTROL SETTINGS ===
max_tokens = 1000             # Max response length (prevents runaway costs)
timeout_seconds = 60          # Request timeout (prevents hanging)
enable_streaming = true       # Word-by-word streaming responses
enable_structured_outputs = false  # JSON Schema for action parsing
```

### Using Your XAI API Key

**Secure Environment Variable Setup**: API keys are stored as environment variables for security:

```bash
# Add to your shell profile (.bashrc, .zshrc, etc.) for persistence:
export XAI_API_KEY="your-xai-api-key-here"

# Or set for current session only:
export XAI_API_KEY="your-xai-api-key-here"
```

**No XAI key?** The game works perfectly offline using the mock provider!

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