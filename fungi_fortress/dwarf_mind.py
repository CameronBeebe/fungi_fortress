"""Player orders go straight to the nearest idle dwarf.

Jev does not sit on this path. A move, mine, or build you ordered is carried
out when a path exists.
"""

from __future__ import annotations

from typing import Any

from .utils import a_star


def assign_work(game_state: Any) -> None:
    """Give each idle dwarf the nearest reachable order."""
    pending = list(game_state.task_manager.tasks)
    if not pending:
        return

    for dwarf in game_state.dwarves:
        if dwarf.state != "idle" or dwarf.task:
            continue
        reachable = _reachable(game_state, dwarf, pending)
        if not reachable:
            continue
        task, path = min(reachable, key=lambda item: len(item[1]))
        if not path and task.type == "move" and (dwarf.x, dwarf.y) == (task.x, task.y):
            game_state.task_manager.remove_task(task)
            pending.remove(task)
            game_state.add_debug_message(f"D{dwarf.id} is already there")
            continue
        dwarf.task = task
        dwarf.path = path
        dwarf.state = "moving"
        game_state.task_manager.remove_task(task)
        pending.remove(task)
        game_state.add_debug_message(f"D{dwarf.id} takes {task.type} at ({task.x},{task.y})")


def _reachable(game_state, dwarf, pending):
    found = []
    for task in pending:
        path = a_star(game_state.map, (dwarf.x, dwarf.y), (task.x, task.y))
        if path is not None:
            found.append((task, path))
    return found
