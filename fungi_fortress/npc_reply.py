"""NPC reply models for typed LLM dialogue.

Used by Oracle and other NPCs to ensure structured, validated responses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Union

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from typing import Any

# Import CharacterKind from world_seed to reuse its type constraint
from .world_seed import CharacterKind


class AddMessageAction(BaseModel):
    """Action to add a debug message."""
    action_type: Literal["add_message"]
    text: str


class SpawnCharacterAction(BaseModel):
    """Action to spawn a character on the map."""
    action_type: Literal["spawn_character"]
    kind: CharacterKind  # Reuses world seed character kind (kin or revealed)
    name: str
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class NpcReply(BaseModel):
    """Reply from an NPC or Oracle with narrative and optional actions.
    
    Used for all NPC dialogue, including the Oracle.
    """
    narrative: str = Field(description="The NPC's spoken response")
    actions: list[Union[AddMessageAction, SpawnCharacterAction]] = Field(
        default_factory=list,
        description="Game actions to execute"
    )


def validate_npc_reply(reply: NpcReply, game: Any) -> NpcReply:
    """Validate NpcReply spawn actions against game state.
    
    Checks that spawn locations are valid (in bounds, walkable, unoccupied).
    Raises ValueError with specific errors for retry.
    
    Args:
        reply: The NpcReply to validate
        game: Game state with map
        
    Returns:
        The validated reply
        
    Raises:
        ValueError: If spawn actions have invalid coordinates or types
    """
    from .world_seed import is_open_tile
    
    errors = []
    
    for action in reply.actions:
        if isinstance(action, SpawnCharacterAction):
            # Check tile is valid using shared predicate
            if not is_open_tile(game, action.x, action.y):
                # Get actual map dimensions for error message
                if hasattr(game, 'map') and game.map:
                    height = len(game.map)
                    width = len(game.map[0]) if height else 0
                    errors.append(
                        f"spawn location ({action.x}, {action.y}) is invalid "
                        f"(must be in bounds 0-{width-1}, 0-{height-1} and walkable)"
                    )
                else:
                    errors.append(f"spawn location ({action.x}, {action.y}) is invalid (map not available)")
    
    if errors:
        raise ValueError("; ".join(errors))
    
    return reply
