# characters.py
import random
from .lore import lore_base
from typing import Any

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
        self.task: Task | None = None
        self.health: int = 100
        self.task_ticks: int = 0
        self.mining_skill: int = random.randint(1, 3)
        self.task_queue: list[Task] = []

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

class NPC:
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
    def __init__(self, name: str, x: int, y: int) -> None:
        self.name: str = name
        self.x: int = x
        self.y: int = y
        self.alive: bool = True
        self.data: dict[str, Any] = lore_base["characters"].get(name, {})

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
