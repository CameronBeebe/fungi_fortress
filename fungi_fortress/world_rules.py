"""Core world rules and character types.

Low-level module for types and predicates used across world generation,
NPC validation, and gameplay logic.
"""

from enum import Enum


class CharacterKind(str, Enum):
    """Character kinds: ordinary kin or mystical revealed."""
    kin = "kin"
    revealed = "revealed"


def is_open_tile(game, x: int, y: int) -> tuple[bool, str]:
    """Check if a tile can hold a spawned character.
    
    Args:
        game: Game state with map
        x: X coordinate
        y: Y coordinate
        
    Returns:
        (is_valid, reason) where reason describes why if invalid
    """
    # Check bounds
    height = len(game.map)
    width = len(game.map[0]) if height else 0
    if x < 0 or x >= width or y < 0 or y >= height:
        return False, f"out of bounds (map is {width}x{height})"
    
    # Check tile is walkable
    tile = game.map[y][x]
    if not tile.walkable:
        return False, "not walkable"
    
    return True, ""
