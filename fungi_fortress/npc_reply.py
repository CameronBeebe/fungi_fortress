"""NPC reply models for typed LLM dialogue.

Used by Oracle and other NPCs to ensure structured, validated responses.
"""

from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, Field


class AddMessageAction(BaseModel):
    """Action to add a debug message."""
    action_type: Literal["add_message"]
    text: str


class SpawnCharacterAction(BaseModel):
    """Action to spawn a character on the map."""
    action_type: Literal["spawn_character"]
    type: str
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
