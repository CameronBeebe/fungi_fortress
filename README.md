# Fungi Fortress

A terminal-based strategy/simulation game written in Python using the curses library. Manage a dwarf, explore, gather resources, and interact with a world of fungi!

## 🤖 LLM Integration Status

**✅ PRODUCTION-READY** - The Oracle LLM integration is now fully ready for live API usage with comprehensive safety features:

- **🛡️ Cost Controls**: Daily request limits, token limits, timeout protection
- **⚡ Reliability**: Smart retry logic, graceful error handling, provider auto-detection  
- **🔧 Multi-Provider**: Supports XAI (Grok), OpenAI (GPT), Anthropic (Claude), Groq
- **📊 Monitoring**: Real-time usage tracking, detailed logging, emergency controls

**Quick Setup**: Copy `oracle_config.ini.example` → `oracle_config.ini`, add your API key, and play! See [LLM Oracle Integration](#llm-oracle-integration) below for details.

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

## How to Run

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd fungi-fortress
    ```
2.  **Set up API Key (Optional, for LLM features):**
    This game can use a Large Language Model (LLM) for certain features. To enable these:
    *   Locate the file named `oracle_config.ini.example` in the root directory.
    *   Make a copy of this file and rename it to `oracle_config.ini`.
    *   Open `oracle_config.ini` in a text editor.
    *   Replace `YOUR_API_KEY_HERE` with your actual API key from an LLM provider.
    *   You can also optionally specify a `model_name` and `context_level` if you have specific preferences.
    *   **Important:** The `oracle_config.ini` file is included in `.gitignore` and should NEVER be committed to version control if it contains a real API key.

3.  **Ensure requirements are met** (see above, especially for `curses` on Windows).
4.  **Run the game:**
    ```bash
    python main.py
    ```
    *(Alternatively, if running as an installed module later: `python -m fungi_fortress.main`)*

## Basic Controls (Tentative - Check `InputHandler`)

*   **Arrow Keys:** Move cursor / navigate menus
*   **Enter:** Confirm selection / interact
*   **i:** Toggle Inventory
*   **s:** Toggle Shop (if applicable)
*   **l:** Toggle Legend
*   **p:** Pause game
*   **m:** Mine (Assign task at cursor?)
*   **c:** Chop (Assign task at cursor?)
*   **b:** Build (Assign task at cursor?)
*   **q:** Quit

*(These controls are inferred and may need verification by checking `input_handler.py`)*

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

**🚀 NEW: Production-Ready with Safety Features** - The LLM integration now includes comprehensive cost controls, retry logic, and monitoring to ensure safe live API usage.

### Supported LLM Providers

The Oracle supports multiple LLM providers through a unified interface:

- **XAI (Grok models)**: Access to Grok-3, Grok-2, and other Grok models via XAI's direct API
- **OpenAI**: GPT-4o, GPT-4o-mini, GPT-4-turbo, and GPT-3.5-turbo models  
- **Anthropic**: Claude-3.5-Sonnet, Claude-3.5-Haiku, and Claude-3-Opus models
- **Groq**: Fast inference for open-source models like LLaMA, Mixtral, and Gemma
- **Auto-detection**: Automatically chooses the appropriate provider based on model name

### Configuration

Copy `oracle_config.ini.example` to `oracle_config.ini` and configure your settings:

```ini
[OracleAPI]
# Your API key for the LLM provider
api_key = YOUR_ACTUAL_API_KEY_HERE

# Provider selection (auto, xai, groq, openai, anthropic)
provider = auto

# Model to use - examples by provider:
# XAI: grok-3, grok-3-beta, grok-2-1212
# OpenAI: gpt-4o, gpt-4o-mini, gpt-3.5-turbo  
# Anthropic: claude-3-5-sonnet-20241022, claude-3-5-haiku-20241022
# Groq: llama-3.3-70b-versatile, llama-3.1-8b-instant, gemma2-9b-it
model_name = gpt-4o-mini

# Context level for game information (low, medium, high)
context_level = medium

# === COST CONTROL SETTINGS ===
max_tokens = 500              # Max response length (prevents runaway costs)
daily_request_limit = 100     # Daily API call limit (cost control)
timeout_seconds = 30          # Request timeout (prevents hanging)
max_retries = 2              # Retry attempts (reliability)
```

### Using Your XAI Credits

**Yes, you can use your XAI API credits directly!** Set your configuration like this:

```ini
[OracleAPI]
api_key = xai-your-actual-api-key-here
provider = xai
model_name = grok-3
context_level = medium
```

The Oracle will communicate directly with XAI's API at `api.x.ai`, using your credits and API limits.

### Cost-Effective Gaming

Since the Oracle is designed for interactive storytelling rather than intensive research tasks, it works well with:

- **Smaller, faster models** (gpt-4o-mini, claude-3-5-haiku, llama-3.1-8b-instant)
- **Cost-efficient providers** (Groq for open-source models, XAI for competitive pricing)
- **Flexible switching** between providers based on your budget and preferences

### Safety Features

- **Daily request limits** prevent unexpected charges
- **Token limits** control response length and costs  
- **Smart retry logic** handles temporary failures
- **Real-time monitoring** shows usage and costs
- **Emergency controls** for immediate cost management

### Setup Verification

After configuring your `oracle_config.ini`, verify everything works:

```bash
python verify_llm_setup.py
```

This tool tests provider detection, verifies configuration, and provides optimization tips.

### Provider Flexibility Benefits

- **No vendor lock-in**: Switch providers anytime by updating your config
- **Use your existing credits**: Works with whatever LLM service you already pay for
- **Cost optimization**: Choose the most cost-effective option for your usage
- **Performance tuning**: Select faster models for real-time gameplay or more sophisticated models for complex storytelling

The Oracle's multi-provider architecture ensures you're never locked into a single LLM service, giving you the freedom to use whichever models and credits work best for your gaming experience. 