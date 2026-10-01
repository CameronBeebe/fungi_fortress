from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    # Use forward references to avoid circular imports for type hints
    from .game_state import GameState
    from .tiles import Tile # Assuming Tile class will exist in tiles.py

class GameEntity:
    """Base class for anything that can occupy a map tile other than the base terrain.

    Entities define the visual representation, basic properties (like walkability),
    and potential interactions for objects placed on the map.
    """
    def __init__(self, name: str, char: str, color: int, walkable: bool, interactive: bool, buildable: bool, description: str = "", is_mycelial: bool = False):
        """Initializes a GameEntity.

        Args:
            name (str): The internal name of the entity (e.g., "stone_wall", "tree").
            char (str): The character used to represent the entity on the map.
            color (int): The curses color pair index for rendering the entity.
            walkable (bool): Can characters (dwarves, player) move onto this tile?
            interactive (bool): Can the player interact with this entity using the 'e' key?
            buildable (bool): Can a structure be built on this tile? (Usually False for entities).
            description (str): A short description shown to the player when inspecting the tile.
            is_mycelial (bool): Flag indicating if this entity is part of or related to the mycelial network.
        """
        self.name = name
        self.char = char
        self.color = color
        self.walkable = walkable # Can the player/dwarves walk ON this entity's tile?
        self.interactive = interactive # Can the player interact with this using 'e'?
        self.buildable = buildable # Can something be built ON this entity's tile? (Usually False for entities)
        self.description = description
        self.is_mycelial = is_mycelial # NEW: Flag for mycelial network entities

class Structure(GameEntity):
    """Represents buildable or pre-placed structures on the map.

    Structures are game entities that often have specific interaction logic,
    like workshops, doors, or quest objectives.
    """
    def __init__(self, name: str, char: str, color: int, walkable: bool, buildable: bool = False, description: str = "",
                 interaction_logic: Callable[['GameState', 'Tile', 'Structure'], None] | None = None, **kwargs):
        """Initializes a Structure.

        Args:
            name (str): The internal name of the structure.
            char (str): The character used to represent the structure.
            color (int): The curses color pair index.
            walkable (bool): Can characters walk on the structure's tile?
            buildable (bool): Can another structure be built on this tile? (Defaults to False).
            description (str): Player-facing description.
            interaction_logic (Callable | None): A function called when the player interacts
                                               with the structure (using 'e'). If None, the
                                               structure is not interactive via 'e'.
                                               The function receives the GameState, the Tile the
                                               structure is on, and the Structure instance itself.
            **kwargs: Additional keyword arguments passed to GameEntity init (e.g., is_mycelial).
        """
        # Structures are interactive if they have specific logic defined
        super().__init__(name, char, color, walkable, interaction_logic is not None, buildable, description, **kwargs)
        # Store the function reference needed for interaction
        self._interaction_logic = interaction_logic

    def interact(self, game_state: 'GameState', tile: 'Tile'):
        """Performs the player interaction associated with this structure.

        Calls the interaction_logic function provided during initialization, if any.

        Args:
            game_state (GameState): The current game state.
            tile (Tile): The tile the structure is located on.
        """
        if self._interaction_logic:
            # Call the stored logic function, passing necessary context
            self._interaction_logic(game_state, tile, self)
        else:
            # Default message if no specific logic was provided
            game_state.add_debug_message(f"Interacting with {self.name}... (No specific logic defined)")

class Sublevel(GameEntity):
    """Represents an entity that acts as an entry point to a sub-level map.

    Interacting with a Sublevel entity typically triggers a map transition.
    """
    def __init__(self, name: str, char: str, color: int, walkable: bool = True, description: str = "",
                 entry_logic: Callable[['GameState', 'Tile', 'Sublevel'], None] | None = None):
        """Initializes a Sublevel entry point.

        Args:
            name (str): The internal name of the sublevel entry (often matches the target sublevel).
            char (str): The character used to represent the entry.
            color (int): The curses color pair index.
            walkable (bool): Can characters walk on the entry tile? (Defaults to True).
            description (str): Player-facing description.
            entry_logic (Callable | None): A function called when the player tries to enter
                                        the sublevel (using 'e'). If None, default debug
                                        message is shown. The function receives the GameState,
                                        the Tile the entry is on, and the Sublevel instance itself.
        """
        # Sublevel entries are always interactive, never buildable on top of
        super().__init__(name, char, color, walkable, True, False, description)
        # Store the function reference needed for entry
        self._entry_logic = entry_logic

    def enter(self, game_state: 'GameState', tile: 'Tile'):
        """Handles the logic for entering this sub-level via player interaction.

        Calls the entry_logic function provided during initialization, if any.
        Note: Dwarf entry into sublevels is handled differently in GameLogic.

        Args:
            game_state (GameState): The current game state.
            tile (Tile): The tile the sublevel entry is located on.
        """
        if self._entry_logic:
            # Call the stored logic function, passing necessary context
            self._entry_logic(game_state, tile, self)
        else:
             # Default message if no specific logic is provided
             game_state.add_debug_message(f"Trying to enter {self.name}... (No specific entry logic defined)")

class ResourceNode(GameEntity):
    """Represents a mineable/harvestable resource node like fungi, stone, or trees.

    These entities are typically targeted by dwarf tasks ('mine', 'chop') rather than
    direct player interaction.
    """
    def __init__(self, name: str, char: str, color: int, walkable: bool, resource_type: str, yield_amount: int = 1, spore_yield: int = 0, description: str = "", **kwargs):
        """Initializes a ResourceNode.

        Args:
            name (str): The internal name of the resource node.
            char (str): The character used to represent the resource.
            color (int): The curses color pair index.
            walkable (bool): Can characters walk on the resource node's tile?
                           (Usually False for walls/trees, True for floor fungi).
            resource_type (str): The type of resource yielded (e.g., "stone", "wood", "fungi").
                                Must match keys used in the player inventory.
            yield_amount (int): The quantity of the resource gained when harvested.
            spore_yield (int): The amount of spore exposure gained by the player when this node is harvested.
            description (str): Player-facing description.
            **kwargs: Additional keyword arguments passed to GameEntity init (e.g., is_mycelial).
        """
         # Resources aren't directly interactive with 'e', but are targeted by tasks ('m').
         # They aren't buildable on top of until harvested/removed.
        super().__init__(name, char, color, walkable, False, False, description, **kwargs)
        self.resource_type = resource_type # e.g., "stone", "fungi"
        self.yield_amount = yield_amount # Amount yielded when harvested/mined
        self.spore_yield = spore_yield   # Spore exposure gained when harvested

    # Harvesting/mining logic is handled by the task system in game_logic.py, not direct interaction. 