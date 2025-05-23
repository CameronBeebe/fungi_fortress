# characters.py
import random
from .lore import lore_base
from typing import Any, TYPE_CHECKING, List, Dict, Union
from .entities import GameEntity

# Conditional import for Task type hint if Task is defined later in the file
if TYPE_CHECKING:
    # If Task is defined in this file, no need for separate import inside TYPE_CHECKING
    pass # Assuming Task is defined below

class Dwarf:
    """Represents a dwarf character controlled by the game logic.

    Dwarves can be assigned tasks, move around the map, and perform actions
    like mining, building, fighting, etc.

    Attributes:
        x (int): The x-coordinate of the dwarf on the map.
        y (int): The y-coordinate of the dwarf on the map.
        id (int): A unique identifier for the dwarf.
        state (str): The current state of the dwarf (e.g., 'idle', 'moving', 'working').
        path (list[tuple[int, int]]): The list of coordinates the dwarf is currently following.
        target_x (int | None): The target x-coordinate for the current action or movement.
        target_y (int | None): The target y-coordinate for the current action or movement.
        task (Task | None): The current task assigned to the dwarf.
        health (int): The current health points of the dwarf.
        task_ticks (int): The number of game ticks remaining for the current task.
        mining_skill (int): The dwarf's proficiency in mining/chopping tasks, affecting speed.
        task_queue (list[Task]): A queue of tasks waiting to be assigned to this dwarf.
    """
    def __init__(self, x: int, y: int, id: int) -> None:
        self.x: int = x
        self.y: int = y
        self.id: int = id
        self.state: str = 'idle'
        self.path: list[tuple[int, int]] = []
        self.target_x: int | None = None
        self.target_y: int | None = None
        # Ensure Task type hint is valid - if Task is defined later, use 'Task' as string
        self.task: 'Task' | None = None
        self.health: int = 100
        self.task_ticks: int = 0
        self.mining_skill: int = random.randint(1, 3)
        # Ensure Task type hint is valid
        self.task_queue: list['Task'] = []

class Animal:
    """Represents a simple animal entity on the map.

    Animals typically move randomly on appropriate terrain (e.g., grass) and
    can be hunted for resources.

    Attributes:
        x (int): The x-coordinate of the animal on the map.
        y (int): The y-coordinate of the animal on the map.
        id (int): A unique identifier for the animal.
        alive (bool): Whether the animal is currently alive.
    """
    def __init__(self, x: int, y: int, id: int) -> None:
        self.x: int = x
        self.y: int = y
        self.id: int = id
        self.alive: bool = True

class NPC(GameEntity):
    """Represents a Non-Player Character with potential lore and interaction.

    NPCs are typically stationary or have simple behaviors and may hold
    information or be part of quests.

    Attributes:
        name (str): The unique name of the NPC, used to look up lore data.
        x (int): The x-coordinate of the NPC on the map.
        y (int): The y-coordinate of the NPC on the map.
        alive (bool): Whether the NPC is currently alive.
        data (dict): A dictionary containing lore information loaded from lore_base.
    """
    def __init__(self, name: str, x: int, y: int, entity_id: str = None, tile_char: str = 'N', color_pair: int = 7, is_walkable: bool = False, is_transparent: bool = True, light_source: bool = False, description: str = None, data: dict = None) -> None:
        super().__init__(
            entity_id if entity_id else name.lower().replace(" ", "_"), 
            tile_char, 
            color_pair, 
            is_walkable, 
            is_transparent, 
            light_source, 
            description if description else name
        )
        self.name: str = name
        self.x: int = x
        self.y: int = y
        self.alive: bool = True
        # Ensure lore_base is correctly accessed and typed
        self.data: dict[str, Any] = data if data is not None else lore_base.get("characters", {}).get(name, {})

# --- New Oracle Class ---
class Oracle(NPC):
    """Represents an Oracle character, a special type of NPC.

    Oracles are intended to be interaction points for LLM-driven dialogue,
    events, and potentially quest generation. They inherit base NPC properties
    but are specifically identified for triggering LLM logic.

    Attributes:
        Inherits all attributes from NPC.
        canned_responses (Dict[str, Union[str, List[str]]]): Predefined dialogue options,
                                                              loaded from lore_base.
    """
    def __init__(self, name: str, x: int, y: int, entity_id: str = None, tile_char: str = 'O', color_pair: int = 11, description: str = None) -> None:
        """Initializes an Oracle character."""
        super().__init__(
            name=name, 
            x=x, 
            y=y, 
            entity_id=entity_id if entity_id else name.lower().replace(" ", "_").replace("'", "") + "_oracle",
            tile_char=tile_char, 
            color_pair=color_pair, 
            description=description if description else f"The enigmatic {name}"
        )
        
        # Load canned responses from lore_base, with fallbacks
        oracle_lore_data = lore_base.get("oracles", {}).get(self.name, {})
        self.canned_responses: Dict[str, Union[str, List[str]]] = oracle_lore_data.get("canned_responses", {})

        # Default responses if not found in lore or if specific keys are missing
        default_responses = {
            "greeting": [
                f"The air around {self.name} shimmers.",
                "You feel a strange pull towards it...",
                "It seems to beckon your thoughts."
            ],
            "no_offering_made": [
                f"{self.name} remains silent, its glow dimming slightly.",
                "Perhaps it requires a token of your understanding..."
            ],
            "no_api_key": [
                f"{self.name} seems to be a conduit to vast knowledge,",
                "but the connection is currently dormant.",
                "(The ancient pathways require an API key; configure it in your settings.)"
            ],
            "default_query_response": [
                "The patterns of fate are ever-shifting.",
                "What you seek may be found, or it may be lost to time."
            ],
            "fallback_error": [
                f"{self.name}'s whispers become indistinct, like wind through cracks.",
                "The connection falters. Try again later."
            ]
        }
        # Merge loaded responses with defaults, ensuring all essential keys have a fallback
        for key, value in default_responses.items():
            if key not in self.canned_responses:
                self.canned_responses[key] = value

# --- Task Class ---
class Task:
    """Represents a task that can be assigned to a dwarf.

    Tasks define an action to be performed at a specific location, potentially
    involving a target resource or building.

    Attributes:
        x (int): The target x-coordinate for the dwarf to move to before starting the task.
                 For tasks like mining/chopping/building bridges, this is the adjacent tile
                 from which the action is performed. For building/fishing/fighting, this is the
                 tile where the action takes place.
        y (int): The target y-coordinate corresponding to x.
        type (str): The type of task (e.g., 'mine', 'chop', 'build', 'fish', 'hunt', 'fight', 'enter', 'build_bridge').
        resource_x (int | None): The x-coordinate of the resource/target tile (e.g., the tree to chop,
                                 the wall to mine, the water to build a bridge over, the sublevel entrance).
                                 None for tasks like fishing or fighting generic enemies not tied to a specific resource tile.
        resource_y (int | None): The y-coordinate corresponding to resource_x.
        building (str | None): The name (key in ENTITY_REGISTRY) of the building to construct for 'build' tasks.
        task_unreachable_ticks (int): Counter for how many ticks this task has been considered unreachable by any dwarf.
    """
    def __init__(self, x: int, y: int, type: str, resource_x: int | None = None, resource_y: int | None = None, building: str | None = None) -> None:
        self.x: int = x
        self.y: int = y
        self.type: str = type
        self.resource_x: int | None = resource_x
        self.resource_y: int | None = resource_y
        self.building: str | None = building
        self.task_unreachable_ticks: int = 0

if __name__ == "__main__":
    npc = NPC("Zorak Sporeweaver", 0, 0)
    print(f"NPC {npc.name}: {npc.data['description']}")
