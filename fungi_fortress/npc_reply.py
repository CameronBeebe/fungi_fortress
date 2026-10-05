"""NPC reply models for typed LLM dialogue.

Used by Oracle and other NPCs to ensure structured, validated responses.
"""

from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, Field

from .world_rules import CharacterKind, is_open_tile


class AddMessageAction(BaseModel):
    """Action to add a debug message."""
    action_type: Literal["add_message"]
    text: str


class SpawnCharacterAction(BaseModel):
    """Action to spawn a character on the map."""
    action_type: Literal["spawn_character"]
    kind: CharacterKind
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


def validate_npc_reply(reply: NpcReply, game) -> NpcReply:
    """Validate NpcReply spawn actions against game state.
    
    Checks that spawn locations are valid (in bounds, walkable).
    Raises ValueError with specific errors for retry.
    
    Args:
        reply: The NpcReply to validate
        game: Game state with map
        
    Returns:
        The validated reply
        
    Raises:
        ValueError: If spawn actions have invalid coordinates
    """
    errors = []
    
    for action in reply.actions:
        if isinstance(action, SpawnCharacterAction):
            is_valid, reason = is_open_tile(game, action.x, action.y)
            if not is_valid:
                errors.append(f"spawn location ({action.x}, {action.y}) is {reason}")
    
    if errors:
        raise ValueError("; ".join(errors))
    
    return reply
