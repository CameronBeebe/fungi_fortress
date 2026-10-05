"""Executable world seeds.

A generative model fills this format once, before play. The map, inventory,
and mission checker stay in charge. Prose fields (motive, secret, voice) make
characters richer. Requirement fields are the only part the game executes.
"""

from __future__ import annotations

import json
import logging
import os
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

from .characters import NPC, Oracle
from .constants import STARTING_RESOURCES
from . import llm_client, llm_world
from .world_rules import CharacterKind, is_open_tile

logger = logging.getLogger(__name__)

COLLECTABLE = frozenset(STARTING_RESOURCES)
MAX_CHARACTERS = 12
MAX_PLACES = 12
MAX_QUESTS = 8
MAX_TEXT = 400
_PREPARED_SEED = os.path.join(os.path.dirname(__file__), "seeds", "example_world.json")
_PREPARED_DEPTH = os.path.join(os.path.dirname(__file__), "seeds", "example_depth.json")


# === Pydantic Models for Structured Outputs ===


class ResourceEnum(str, Enum):
    """Valid resource types for collection requirements."""
    food = "food"
    wood = "wood"
    stone = "stone"
    gold = "gold"
    crystals = "crystals"
    fungi = "fungi"
    magic_fungi = "magic_fungi"


class CollectRequirement(BaseModel):
    """Requirement to collect a specific resource."""
    kind: Literal["collect"]
    resource: ResourceEnum
    count: int = Field(ge=1, le=99)


class ReachRequirement(BaseModel):
    """Requirement to reach a specific place."""
    kind: Literal["reach"]
    place: str


class CharacterSchema(BaseModel):
    """Character in a world seed."""
    id: str
    name: str
    description: str
    kind: CharacterKind
    faction: str = ""
    motive: str = ""
    secret: str = ""
    voice: str = ""


class PlaceSchema(BaseModel):
    """Place in a world seed."""
    id: str
    name: str
    description: str


class QuestSchema(BaseModel):
    """Quest in a world seed."""
    id: str
    title: str
    summary: str
    giver_id: str
    requirements: list[Union[CollectRequirement, ReachRequirement]]
    success: str = ""


class WorldSeedSchema(BaseModel):
    """Complete world seed with structured validation."""
    title: str
    premise: str
    characters: list[CharacterSchema]
    places: list[PlaceSchema]
    quests: list[QuestSchema]


def _convert_to_world_seed(schema: WorldSeedSchema) -> WorldSeed:
    """Convert WorldSeedSchema to WorldSeed, running all semantic validation.
    
    This uses parse_world_seed as the single source of truth for validation.
    Raises ValueError with detailed error message if validation fails.
    """
    # Convert to dict format expected by parse_world_seed
    seed_dict = schema.model_dump(mode="json")
    # parse_world_seed does all semantic validation and raises ValueError on failure
    return parse_world_seed(seed_dict)


@dataclass
class CharacterSeed:
    id: str
    name: str
    description: str
    faction: str = ""
    motive: str = ""
    secret: str = ""
    voice: str = ""
    kind: str = "kin"


@dataclass
class PlaceSeed:
    id: str
    name: str
    description: str


@dataclass
class Requirement:
    kind: str
    resource: str | None = None
    count: int | None = None
    place: str | None = None


@dataclass
class QuestSeed:
    id: str
    title: str
    summary: str
    giver_id: str
    requirements: list[Requirement] = field(default_factory=list)
    success: str = ""


@dataclass
class WorldSeed:
    title: str
    premise: str
    characters: list[CharacterSeed]
    places: list[PlaceSeed]
    quests: list[QuestSeed]


def _text(data: dict[str, Any], key: str, required: bool = True) -> str:
    value = data.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{key} is required")
    if len(value) > MAX_TEXT:
        raise ValueError(f"{key} is longer than {MAX_TEXT} characters")
    return value


def _ident(data: dict[str, Any], key: str = "id") -> str:
    value = _text(data, key)
    if any(ch.isspace() for ch in value):
        raise ValueError(f"{key} cannot contain whitespace")
    return value


def parse_world_seed(data: dict[str, Any]) -> WorldSeed:
    """Validate a seed dict. Raises ValueError when the game could not run it."""
    if not isinstance(data, dict):
        raise ValueError("world seed must be an object")

    characters = [_character(item) for item in _list(data, "characters", MAX_CHARACTERS)]
    _ensure_one_revealed(characters)
    places = [_place(item) for item in _list(data, "places", MAX_PLACES)]
    character_ids = _unique((c.id for c in characters), "character")
    place_ids = _unique((p.id for p in places), "place")
    quests = [
        _quest(item, character_ids, place_ids)
        for item in _list(data, "quests", MAX_QUESTS)
    ]
    _unique((q.id for q in quests), "quest")
    if not quests:
        raise ValueError("world seed needs at least one quest")

    return WorldSeed(
        title=_text(data, "title"),
        premise=_text(data, "premise"),
        characters=characters,
        places=places,
        quests=quests,
    )


def load_world_seed(path: str) -> WorldSeed:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return parse_world_seed(data)


def mission_from_quest(seed: WorldSeed, quest: QuestSeed) -> dict[str, Any]:
    """Translate one quest into the mission dict the current checker understands."""
    givers = [c for c in seed.characters if c.id == quest.giver_id]
    giver_name = givers[0].name if givers else quest.giver_id
    requirements: dict[str, Any] = {}
    objectives: list[str] = []
    for req in quest.requirements:
        if req.kind == "collect" and req.resource and req.count:
            requirements[req.resource] = req.count
            objectives.append(f"Collect {req.count} {req.resource}")
        elif req.kind == "reach" and req.place:
            place_name = next(p.name for p in seed.places if p.id == req.place)
            requirements["reach"] = place_name
            objectives.append(f"Reach {place_name}")
    return {
        "description": quest.summary,
        "title": quest.title,
        "objectives": objectives,
        "rewards": [],
        "requirements": requirements,
        "required_npcs": [giver_name],
        "seed_quest_id": quest.id,
        "premise": seed.premise,
        "success": quest.success,
    }


def apply_world_seed(game: Any, seed: WorldSeed) -> None:
    """Install the first quest and stand the seeded characters on open tiles."""
    game.mission = mission_from_quest(seed, seed.quests[0])
    game.world_title = seed.title
    game.world_premise = seed.premise
    game.add_debug_message(seed.premise)
    _spawn_characters(game, seed)


def load_and_apply(game: Any, path: str) -> WorldSeed:
    seed = load_world_seed(path)
    apply_world_seed(game, seed)
    return seed


def schema_guide() -> str:
    """The prompt the game sends when it grows a world. Not a player instruction."""
    return _seed_prompt()


def grow_world(game: Any, complete: Callable[[str], str] | None = None) -> str:
    """Grow a world from the player's LLM key and install it.

    Returns one line for the game log. A prepared grove is used when the
    model is missing or both attempts come back invalid.
    """
    # Get or create an LLM client
    if complete is None:
        client = _get_llm_client(game)
        if client is None:
            _install_prepared(game)
            return "No language-model key found. Using a prepared grove."
    else:
        # Wrap the complete function in a minimal client adapter for tests
        client = _CompleteAdapter(complete)
    
    # Use structured call with schema and converter
    messages = [
        {"role": "system", "content": "You write one JSON object and nothing else."},
        {"role": "user", "content": _seed_prompt()},
    ]
    
    seed = llm_client.structured_call(
        client,
        messages,
        WorldSeedSchema,
        schema_name="world_seed",
        label="World seed",
        convert=_convert_to_world_seed,
        max_tokens=4000,
        reasoning_effort="low",
    )
    
    if seed is None:
        _install_prepared(game)
        return "The new world came back unusable. Using a prepared grove."
    
    apply_world_seed(game, seed)
    return f"{seed.title}. {seed.quests[0].title}."


def _seed_prompt(rejection: str = "") -> str:
    rules = (
        "Write a JSON world for Fungi Fortress. "
        "Exactly one character must be revealed. Kin are ordinary people who covet spice. "
        "The revealed figure lives in the mycelium and is only half-present at a low dose. "
        "Include 2 or 3 characters and 1 or 2 quests. "
        "Add success only when the point of the quest is not already the requirements, "
        "as a short sentence such as whether a character is satisfied or a place stayed undisturbed. "
        "The premise and secrets are facts the inhabitants know. "
        "All IDs must be unique and contain no spaces."
    )
    if rejection:
        return rules + " The previous response was rejected: " + rejection
    return rules


def _get_llm_client(game: Any) -> Optional[llm_client.LLMClient]:
    """Get an LLM client from game configuration or environment.
    
    Returns None if no valid API key is available.
    """
    config = getattr(game, "llm_config", None)
    if config is not None:
        try:
            client = config.create_llm_client()
            # Only return if it's not using mock (i.e., has a real key)
            if not client.is_mock():
                return client
        except Exception:
            pass
    
    # Try XAI_API_KEY environment variable as fallback
    xai_key = os.environ.get("XAI_API_KEY", "").strip()
    if xai_key:
        return llm_client.create_client_from_config(
            model="grok-3-mini",
            api_key=xai_key,
            max_tokens=4000,
            timeout_seconds=45,
            temperature=0.8,
        )
    
    return None


class _CompleteAdapter:
    """Minimal adapter that wraps a complete function to look like an LLM client for tests."""
    
    def __init__(self, complete_fn: Callable[[str], str]):
        self._complete = complete_fn
    
    def chat(self, messages: list[dict], **kwargs) -> str:
        """Extract the last user prompt and call the complete function."""
        # Find the last user message
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return self._complete(msg["content"])
        return self._complete("")


def _install_prepared(game: Any) -> None:
    prepared = load_world_seed(_PREPARED_SEED)
    apply_world_seed(game, prepared)


def _list(data: dict[str, Any], key: str, limit: int) -> list[Any]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    if len(value) > limit:
        raise ValueError(f"{key} has more than {limit} entries")
    return value


def _unique(values, label: str) -> set[str]:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"duplicate {label} id {value}")
        seen.add(value)
    return seen


def _character(item: Any) -> CharacterSeed:
    if not isinstance(item, dict):
        raise ValueError("character must be an object")
    return CharacterSeed(
        id=_ident(item),
        name=_text(item, "name"),
        description=_text(item, "description"),
        faction=_text(item, "faction", required=False),
        motive=_text(item, "motive", required=False),
        secret=_text(item, "secret", required=False),
        voice=_text(item, "voice", required=False),
        kind=_kind(item),
    )


def _kind(item: dict[str, Any]) -> str:
    kind = _text(item, "kind", required=False) or "kin"
    if kind not in ("kin", "revealed"):
        raise ValueError(f"character kind {kind} must be kin or revealed")
    return kind


def _ensure_one_revealed(characters: list[CharacterSeed]) -> None:
    """Every world has one figure who resolves with the dose."""
    revealed = [character for character in characters if character.kind == "revealed"]
    if not revealed and characters:
        characters[-1].kind = "revealed"
        return
    for extra in revealed[1:]:
        extra.kind = "kin"


def grow_depth(game: Any, complete: Callable[[str], str] | None = None) -> str:
    """Grow the first depth once. The surface mission stays until enter_depth."""
    existing = getattr(game, "depth_seed", None)
    if existing is not None:
        return f"{existing.title}. {existing.quests[0].title}."

    # Get or create an LLM client
    if complete is None:
        client = _get_llm_client(game)
        if client is None:
            game.depth_seed = load_world_seed(_PREPARED_DEPTH)
            return f"{game.depth_seed.title}. The stair uses a prepared depth."
    else:
        # Wrap the complete function in a minimal client adapter for tests
        client = _CompleteAdapter(complete)
    
    # Use structured call with schema and converter
    messages = [
        {"role": "system", "content": "You write one JSON object and nothing else."},
        {"role": "user", "content": _depth_prompt()},
    ]
    
    seed = llm_client.structured_call(
        client,
        messages,
        WorldSeedSchema,
        schema_name="depth_seed",
        label="Depth seed",
        convert=_convert_to_world_seed,
        max_tokens=4000,
        reasoning_effort="low",
    )
    
    if seed is None:
        game.depth_seed = load_world_seed(_PREPARED_DEPTH)
        return f"{game.depth_seed.title}. The new depth came back unusable. Using a prepared depth."
    
    game.depth_seed = seed
    return f"{seed.title}. {seed.quests[0].title}."


def enter_depth(game: Any) -> None:
    """Stand the depth's people on the current map and hold the surface mission aside."""
    seed = getattr(game, "depth_seed", None) or load_world_seed(_PREPARED_DEPTH)
    game.depth_seed = seed
    if not getattr(game, "in_depth", False):
        game.surface_cast = list(game.characters)
        game.surface_mission = game.mission
        game.surface_mission_complete = getattr(game, "mission_complete", False)
        game.in_depth = True
    game.characters = []
    game.spice_grade = 2
    game.depth_title = seed.title
    game.depth_premise = seed.premise
    game.mission = mission_from_quest(seed, seed.quests[0])
    game.mission_complete = False
    _spawn_characters(game, seed, layer="depth")
    game.add_debug_message(seed.premise)


def leave_depth(game: Any) -> None:
    """Return the surface people and the surface mission."""
    if not getattr(game, "in_depth", False):
        return
    game.characters = list(getattr(game, "surface_cast", []))
    if getattr(game, "surface_mission", None) is not None:
        game.mission = game.surface_mission
        game.mission_complete = getattr(game, "surface_mission_complete", False)
    game.spice_grade = 1
    game.in_depth = False


def _depth_prompt(rejection: str = "") -> str:
    rules = (
        "Write a depth beneath a Mycelial Nexus. "
        "This is a mind-region, mythic and archetypal: a cathedral, court, wound, or machine-garden of spice. "
        "Spice is rarer and stronger here than on the surface. "
        "Exactly one character must be revealed. "
        "Include 2 characters and 1 quest. The quest should ask for magic_fungi or reaching the place. "
        "The premise is what a dwarf perceives on the stair. "
        "All IDs must be unique and contain no spaces."
    )
    if rejection:
        return rules + " The previous response was rejected: " + rejection
    return rules


def _place(item: Any) -> PlaceSeed:
    if not isinstance(item, dict):
        raise ValueError("place must be an object")
    return PlaceSeed(id=_ident(item), name=_text(item, "name"), description=_text(item, "description"))


def _quest(item: Any, character_ids: set[str], place_ids: set[str]) -> QuestSeed:
    if not isinstance(item, dict):
        raise ValueError("quest must be an object")
    giver_id = _text(item, "giver_id")
    if giver_id not in character_ids:
        raise ValueError(f"quest giver {giver_id} is not a character id")
    raw_reqs = item.get("requirements", [])
    if not isinstance(raw_reqs, list) or not raw_reqs:
        raise ValueError("quest requirements must be a non-empty list")
    requirements = [_requirement(req, place_ids) for req in raw_reqs]
    return QuestSeed(
        id=_ident(item),
        title=_text(item, "title"),
        summary=_text(item, "summary"),
        giver_id=giver_id,
        requirements=requirements,
        success=_text(item, "success", required=False),
    )


def _requirement(item: Any, place_ids: set[str]) -> Requirement:
    if not isinstance(item, dict):
        raise ValueError("requirement must be an object")
    kind = item.get("kind")
    if kind == "collect":
        resource = item.get("resource")
        count = item.get("count")
        if resource not in COLLECTABLE:
            raise ValueError(f"unknown resource {resource}")
        if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 99:
            raise ValueError("collect count must be an integer from 1 to 99")
        return Requirement(kind="collect", resource=resource, count=count)
    if kind == "reach":
        place = item.get("place")
        if not isinstance(place, str) or place not in place_ids:
            raise ValueError(f"reach place {place} must be a place id in this seed")
        return Requirement(kind="reach", place=place)
    raise ValueError(f"unknown requirement kind {kind}")


def _spawn_characters(game: Any, seed: WorldSeed, layer: str = "surface") -> None:
    if not getattr(game, "map", None):
        return
    height = len(game.map)
    width = len(game.map[0]) if height else 0
    occupied = {(d.x, d.y) for d in getattr(game, "dwarves", [])}
    occupied.update((c.x, c.y) for c in game.characters)
    dwarves = list(getattr(game, "dwarves", []))
    chosen: list[tuple[int, int]] = []
    for character in seed.characters:
        spot = _open_tile(game, width, height, occupied, dwarves, chosen)
        if spot is None:
            game.add_debug_message(f"No room to spawn {character.name}")
            continue
        # Build data dict once for both Oracle and NPC
        char_data = {
            "description": character.description,
            "faction": character.faction,
            "motive": character.motive,
            "secret": character.secret,
            "voice": character.voice,
            "seed_id": character.id,
            "kind": character.kind,
            "layer": layer,
        }
        # Create Oracle instance for "revealed" kind characters (oracles/mystical entities)
        if character.kind == "revealed":
            npc = Oracle(
                character.name,
                spot[0],
                spot[1],
                description=character.description,
                data=char_data,
            )
        else:
            npc = NPC(
                character.name,
                spot[0],
                spot[1],
                data=char_data,
            )
        game.characters.append(npc)
        occupied.add(spot)
        chosen.append(spot)
        game.add_debug_message(f"{character.name} is at ({spot[0]}, {spot[1]})")


def _open_tile(game, width, height, occupied, dwarves, chosen) -> tuple[int, int] | None:
    """Pick a walkable tile away from the dwarves and from other seeded people."""
    spots = []
    for y in range(height):
        for x in range(width):
            if (x, y) in occupied:
                continue
            is_valid, _ = is_open_tile(game, x, y)
            if is_valid:
                spots.append((x, y))

    def away(min_dwarf: int, min_peer: int):
        found = []
        for spot in spots:
            if any(_manhattan(spot, (dwarf.x, dwarf.y)) < min_dwarf for dwarf in dwarves):
                continue
            if any(_manhattan(spot, other) < min_peer for other in chosen):
                continue
            found.append(spot)
        return found

    for min_dwarf, min_peer in ((8, 5), (4, 3), (2, 2)):
        found = away(min_dwarf, min_peer)
        if found:
            # Pick randomly among valid spots (using game's RNG for reproducibility)
            return random.choice(found)
    return None


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
