# constants.py

from typing import Dict

# Map dimensions
MAP_WIDTH = 40
MAP_HEIGHT = 40
UI_WIDTH = 30 # Adjusted UI width
LOG_HEIGHT = 5 # Height of the log window

# --- Spell System Configuration ---
MAX_SPELL_SLOTS = 5  # Maximum number of spells a player can have
SPELL_HOTKEYS = {
    "1": 0,  # First spell slot
    "2": 1,  # Second spell slot
    "3": 2,  # Third spell slot
    "4": 3,  # Fourth spell slot
    "5": 4   # Fifth spell slot
}

# Game initialization
STARTING_RESOURCES = {
    "food": 2,
    "wood": 10,
    "stone": 5,
    "gold": 0,
    "crystals": 0,
    "fungi": 5,
    "magic_fungi": 0
}
STARTING_SPECIAL_ITEMS: Dict[str, int] = {
    "Sclerotium": 1,
    "Map Fragment": 1
}
STARTING_PLAYER_STATS = {
    'location': "Surface Camp", # Start location
    'completed_quests': [],
    'spore_exposure': 50,  # Give some starting spore exposure to cast spells
    'spells': ["Spore Cloud", "Fungal Bloom", "Reveal Mycelium"],  # Start with these spells
    'max_carry_weight': 20,
    'spell_slots': [None] * MAX_SPELL_SLOTS  # Initialize empty spell slots
}

# Task and action timing/limits
MAX_TASKS = 10 # Maximum number of tasks allowed in the TaskManager queue.
FISHING_TICKS = 10 # Number of game ticks required to complete one fishing attempt.
ANIMAL_MOVE_CHANCE = 0.2 # Probability (0.0 to 1.0) that an animal will move each game tick.
MAX_DWARVES = 3 # Maximum number of dwarves allowed in the game.
BASE_UNDERGROUND_MINING_TICKS = 5 # Base number of ticks to mine/chop resources (modified by dwarf skill). Also used for bridge building.

# Screen dimensions
MIN_SCREEN_WIDTH = MAP_WIDTH + UI_WIDTH + 2 # Map width + sidebar width + spacing
MIN_SCREEN_HEIGHT = MAP_HEIGHT + LOG_HEIGHT + 2 # Map height + log height + status lines

# --- Map Generation Parameters ---
# Perlin noise thresholds used during map generation.
# Values typically range from -1.0 to 1.0.
ROCK_THRESHOLD = 0.6    # Perlin noise value above which is stone wall (underground)
WATER_LEVEL = -0.2      # Perlin noise value below which is water (surface)
GRASS_LEVEL = 0.1       # Perlin noise value below which is grass (surface)
# Density parameters control the frequency of entities placed on valid tiles.
TREE_DENSITY = 0.05     # Chance (0.0 to 1.0) for a tree to spawn on a grass tile (surface).
FUNGI_DENSITY = 0.08    # Chance (0.0 to 1.0) for fungi on walkable floors (underground/caves).
MAGIC_FUNGI_DENSITY = 0.02 # Chance (0.0 to 1.0) for magic fungi on walkable floors (underground/caves).
MYCELIUM_THRESHOLD = 0.4 # Perlin noise value above which is mycelium wall (used in specific sublevel generation).

# Sidebar layout
# Defines the vertical space (number of lines) allocated to each section in the UI sidebar.
SIDEBAR_SECTIONS = {
    'basic_info': 3,      # Tick, Depth, Selected Tile
    'spells': 10,         # Selected spell + list of known spells
    'tile_info': 2,       # Info about the selected tile's terrain and entity
    'resources': 8,       # Header + list of player resources
    'items': 8,           # Header + list of player special items
    'mission': 10,        # Current mission description and objectives
    'status': 2,          # Player status (Spore Exposure, Paused)
    'debug': 4,           # Header + recent debug messages
    'hotkeys': 5          # Header + key command reminders
}

SIDEBAR_X = MAP_WIDTH + 2  # Starting X coordinate (column) for the sidebar rendering.

# General Comments:
# - This file centralizes game configuration values.
# - It avoids dependencies on other game modules.
# - Constants are used across various parts of the game (logic, rendering, map generation, UI).
# - BASE_UNDERGROUND_MINING_TICKS is used in game_logic.py for task duration.
# - MAP_WIDTH, MAP_HEIGHT, UI_WIDTH, LOG_HEIGHT are used in renderer.py and potentially elsewhere.
# - Spell constants are used in game_state.py and input_handler.py.
