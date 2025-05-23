# Fungi Fortress

A terminal-based strategy/simulation game written in Python using the curses library. Manage a dwarf, explore, gather resources, and interact with a world of fungi!

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