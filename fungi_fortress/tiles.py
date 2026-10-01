# tiles.py

from typing import TYPE_CHECKING, Dict
import random

# Remove sys.path manipulation
# project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# sys.path.insert(0, project_root)

# Import entity classes using relative paths
from .entities import GameEntity, Structure, Sublevel, ResourceNode
# Import interaction logic from the new interactions module
from .interactions import (
    enter_sublevel_logic,
    interact_mycelial_nexus_logic,
    interact_dwarven_sporeforge_logic
)

if TYPE_CHECKING:
    from .game_state import GameState # Use relative path for type hint


# --- Entity Instance Registry ---
# Replace TILE_PROPERTIES with instances of our new classes
ENTITY_REGISTRY: Dict[str, GameEntity] = {
    # Basic Terrain (Using GameEntity directly)
    "grass": GameEntity(name="Grass", char=".", color=1, walkable=True, interactive=False, buildable=True, description="Patchy grass."),
    "stone_floor": GameEntity(name="Stone Floor", char=".", color=9, walkable=True, interactive=False, buildable=True, description="Rough stone floor."),
    "water": GameEntity(name="Water", char="~", color=3, walkable=False, interactive=False, buildable=False, description="Murky water."),
    "bridge": GameEntity(name="Bridge", char="H", color=2, walkable=True, interactive=False, buildable=False, description="A wooden bridge segment."),
    "mycelium_floor": GameEntity(name="Mycelium Floor", char=".", color=11, walkable=True, interactive=False, buildable=True, description="Floor covered in fungal growth."),
    "mycelium_wall": Structure(name="Mycelium Wall", char="#", color=11, walkable=False, buildable=False, description="Wall pulsating with mycelium.", is_mycelial=True),

    # Resources (Using ResourceNode)
    "stone_wall": ResourceNode(name="Stone Wall", char="^", color=5, walkable=False, resource_type="stone", yield_amount=1, description="A sturdy stone wall, mineable."),
    "tree": ResourceNode(name="Tree", char="T", color=1, walkable=False, resource_type="wood", yield_amount=1, description="A tree, provides wood when chopped."), # Assuming trees yield wood
    "fungi": ResourceNode(name="Fungi Patch", char="f", color=13, walkable=True, resource_type="fungi", yield_amount=1, spore_yield=1, description="A patch of common fungi."),
    "magic_fungi": ResourceNode(name="Magic Fungi", char="F", color=16, walkable=True, resource_type="magic_fungi", yield_amount=1, spore_yield=5, description="A patch of glowing, magical fungi.", is_mycelial=True),

    # Structures (Using Structure)
    "Mycelial Nexus": Structure(name="Mycelial Nexus", char="N", color=17, walkable=True, buildable=False, interaction_logic=interact_mycelial_nexus_logic, description="A built Mycelial Nexus structure.", is_mycelial=True),
    "Dwarven Sporeforge": Structure(name="Dwarven Sporeforge", char="S", color=16, walkable=True, buildable=False, interaction_logic=interact_dwarven_sporeforge_logic, description="A built Dwarven Sporeforge structure.", is_mycelial=True),

    # Sublevels (Using Sublevel)
    "Shadowed Grotto": Sublevel(name="Shadowed Grotto", char="G", color=6, walkable=True, entry_logic=enter_sublevel_logic, description="An entrance to the Shadowed Grotto."),
    # Add other potential sublevel entries here if needed
}

# --- Tile Class --- 

class Tile:
    """Represents a single tile on the game map.

    Each tile contains a specific entity (`GameEntity` subclass) which defines
    its base properties (character, color, walkability, etc.). The tile itself
    manages its coordinates, task designation status, and timers for temporary
    visual effects like highlighting, flashing, or pulsing.

    Attributes:
        entity (GameEntity): The actual entity occupying this tile.
        x (int): The x-coordinate of the tile on the map.
        y (int): The y-coordinate of the tile on the map.
        designated (bool): True if this tile is targeted by a pending task.
        highlight_ticks (int): Remaining ticks for a highlight effect.
        flash_ticks (int): Remaining ticks for a flashing effect.
        pulse_ticks (int): Remaining ticks for a pulsing effect.
        _color_override (int | None): A temporary color pair index to use instead
                                     of the entity's default color. Set to None
                                     to use the default.
    """
    def __init__(self, entity: GameEntity, x: int, y: int, color_override: int | None = None, designated: bool = False):
        """Initializes a Tile.

        Args:
            entity (GameEntity): The entity instance occupying this tile.
            x (int): The x-coordinate.
            y (int): The y-coordinate.
            color_override (int | None, optional): Initial color override. Defaults to None.
            designated (bool, optional): Initial designation status. Defaults to False.

        Raises:
            TypeError: If the provided `entity` is not an instance of `GameEntity`.
        """
        if not isinstance(entity, GameEntity):
             raise TypeError(f"Tile entity must be an instance of GameEntity, got {type(entity)}")
        self.entity = entity
        self.x = x
        self.y = y
        self.designated = designated # For tasks like mining/building
        self.highlight_ticks = 0
        self.flash_ticks = 0
        self.pulse_ticks = 0
        self._color_override = color_override # For temporary effects like flashing

    # Delegate properties to the contained entity
    @property
    def name(self) -> str:
        """Returns the name of the entity on this tile."""
        return self.entity.name

    @property
    def char(self) -> str:
        """Returns the character representation of the entity on this tile."""
        return self.entity.char

    @property
    def walkable(self) -> bool:
        """Returns whether the entity on this tile allows movement onto it."""
        return self.entity.walkable

    @property
    def interactive(self) -> bool:
        """Returns whether the entity on this tile is interactive via the 'e' key."""
        return self.entity.interactive

    @property
    def buildable(self) -> bool:
        """Returns whether the entity on this tile allows building on top of it."""
        # A tile is buildable if its *current* entity allows it (e.g., grass, floor)
        return self.entity.buildable

    @property
    def color(self) -> int:
        """Returns the effective color pair index for rendering this tile.

        Uses the `_color_override` if set, otherwise returns the default
        color index of the contained entity.
        """
        # Use override if set, otherwise default entity color
        return self._color_override if self._color_override is not None else self.entity.color

    def set_color_override(self, color: int | None):
        """Sets or clears the temporary color override for this tile.

        Used by rendering logic for visual effects.

        Args:
            color (int | None): The curses color pair index to use, or None to
                              revert to the entity's default color.
        """
        self._color_override = color

    def __str__(self):
        """Returns the name of the entity on the tile for string representation."""
        # Represent the tile by its entity's name for debugging/logging
        return self.entity.name

    def interact(self, game_state: 'GameState'):
        """Handles player interaction with this tile.

        Delegates the interaction to the `interact` method of the contained
        `Structure` entity or the `enter` method of a `Sublevel` entity,
        if applicable. Logs messages for other cases.

        Args:
            game_state (GameState): The current game state.
        """
        if isinstance(self.entity, Structure):
            self.entity.interact(game_state, self)
        elif isinstance(self.entity, Sublevel):
            self.entity.enter(game_state, self)
        elif self.entity.interactive: # Fallback for generic interactive entities? 
             game_state.add_debug_message(f"Interacted with {self.entity.name}, but no specific logic handled by Tile.interact.")
        else:
            game_state.add_debug_message(f"Nothing to interact with: {self.entity.name}")

# REMOVED TILE_PROPERTIES dictionary
# REMOVED redundant InteractiveTile class
