# task_manager.py
from .characters import Task  # Use relative import for Task class

class TaskManager:
    """Handles the queue of tasks waiting to be assigned to dwarves.

    Maintains a list of pending `Task` objects and a set of coordinates
    for tiles designated as targets for resource extraction or building.

    Attributes:
        tasks (List[Task]): The list of currently pending tasks.
        designated_tiles (Set[Tuple[int, int]]): A set of (x, y) coordinates for tiles
            targeted by tasks that involve a resource (e.g., mining, chopping,
            building bridge). Used for rendering and preventing duplicate tasks.
    """
    def __init__(self):
        """Initializes the TaskManager with an empty task list and designated tiles set."""
        self.tasks: List[Task] = []
        self.designated_tiles: Set[Tuple[int, int]] = set()

    def add_task(self, task: Task) -> bool:
        """Adds a task to the pending list and designates its target tile if applicable.

        Checks against an arbitrary task limit (currently 100). If the task involves
        a resource tile (resource_x/y are set), adds those coordinates to the
        `designated_tiles` set.

        Args:
            task (Task): The task object to add.

        Returns:
            bool: True if the task was added successfully, False if the task limit was reached.
        """
        if len(self.tasks) < 100:  # Arbitrary limit for stability; adjust as needed
            self.tasks.append(task)
            if task.resource_x is not None and task.resource_y is not None:
                self.designated_tiles.add((task.resource_x, task.resource_y))
            return True
        return False

    def remove_task(self, task: Task):
        """Removes a specific task from the list and potentially undesignates its target tile.

        If the removed task targeted a resource tile, checks if any other pending tasks
        target the same tile. If not, removes the coordinates from `designated_tiles`.

        Args:
            task (Task): The task object to remove.
        """
        if task in self.tasks:
            self.tasks.remove(task)
            if task.resource_x is not None and task.resource_y is not None:
                # Only remove if no other task designates the same tile
                if not any(t.resource_x == task.resource_x and t.resource_y == task.resource_y for t in self.tasks):
                    self.designated_tiles.discard((task.resource_x, task.resource_y))

    def clear_tasks(self):
        """Removes all pending tasks and clears all designated tiles."""
        self.tasks.clear()
        self.designated_tiles.clear()

    def is_designated(self, x: int, y: int) -> bool:
        """Checks if the tile at the given coordinates is currently designated by a task.

        Args:
            x (int): The x-coordinate of the tile.
            y (int): The y-coordinate of the tile.

        Returns:
            bool: True if the tile coordinates are in the `designated_tiles` set, False otherwise.
        """
        return (x, y) in self.designated_tiles

# Comments:
# - Basic TaskManager implementation with task list and designated tiles tracking.
# - add_task returns bool to indicate success, used in InputHandler debug messages.
# - Assumes Task has attributes x, y, type, resource_x, resource_y.
