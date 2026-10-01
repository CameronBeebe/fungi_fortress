"""Jev watches the world. It does not carry out player orders.

An encounter is judged once, when a dwarf meets a seeded character. A mission
with a written success condition is judged once, after the countable goals
are already met. Both results are stored and then read by ordinary code.
"""

from __future__ import annotations

import os
from typing import Any, Callable

from .characters import Oracle
from .jev_client import JevError, evaluate
from .spice import GLIMPSE, VOICE, WELCOME, band_for

REVEAL_YES = 0.5
ACCOMPLISHED_YES = 0.5


def note_arrivals(game: Any, transport: Callable[..., Any] | None = None, api_key: str | None = None) -> None:
    """Judge a seeded character the first time a dwarf stands beside them."""
    for dwarf in game.dwarves:
        for npc in game.characters:
            if isinstance(npc, Oracle) or not getattr(npc, "alive", True):
                continue
            if abs(dwarf.x - npc.x) + abs(dwarf.y - npc.y) != 1:
                continue
            data = getattr(npc, "data", None) or {}
            if data.get("kind") == "revealed":
                consider_revelation(game, npc, transport=transport, api_key=api_key)
            else:
                consider_encounter(game, npc, transport=transport, api_key=api_key)


def consider_encounter(
    game: Any,
    npc: Any,
    transport: Callable[..., Any] | None = None,
    api_key: str | None = None,
) -> None:
    """Store one stance for this character. Later meetings reuse it."""
    if getattr(npc, "judged", False) or isinstance(npc, Oracle):
        return
    data = getattr(npc, "data", None) or {}
    if not data.get("motive") and not data.get("seed_id"):
        return

    key = api_key if api_key is not None else os.environ.get("TYPESAFE_API_KEY", "")
    npc.stance = "wary"
    npc.reveal_secret = False
    npc.judged = True
    if not key and transport is None:
        game.add_debug_message(f"{npc.name} is here.")
        return

    try:
        payload = evaluate(_encounter_state(game, npc), _encounter_questions(), key or "unused", opener=transport)
        answers = payload["answers"]
        stance = answers["stance"]["choice"]
        if stance not in ("help", "wary", "hostile"):
            raise JevError(f"stance {stance} is not help, wary, or hostile")
        npc.stance = stance
        reveal = answers.get("reveal_secret", {}).get("noul", 0)
        npc.reveal_secret = stance == "help" and isinstance(reveal, (int, float)) and reveal >= REVEAL_YES
        game.add_debug_message(f"{npc.name} seems {stance}.")
    except (JevError, KeyError, TypeError) as exc:
        game.add_debug_message(f"{npc.name} could not be judged ({exc}).")


def speech_lines(npc: Any) -> list[str]:
    """What this character says from the seed, filtered by stance or dose."""
    data = getattr(npc, "data", None) or {}
    if data.get("kind") == "revealed":
        return _revealed_lines(npc)
    motive = data.get("motive") or data.get("description") or ""
    voice = data.get("voice") or ""
    secret = data.get("secret") or ""
    stance = getattr(npc, "stance", None)
    if stance == "hostile":
        return [f"{npc.name} snaps: Stay back."]
    lines = []
    if motive:
        lines.append(f"{npc.name}: {motive}")
    if voice:
        lines.append(f"({voice})")
    if getattr(npc, "reveal_secret", False) and secret:
        lines.append(f"{npc.name} lowers their voice: {secret}")
    if not lines:
        lines.append(f"You talk to {npc.name}. They grunt noncommittally.")
    return lines


def glance(npc: Any, exposure: int = 0) -> tuple[str, str]:
    """Name and public description for whoever the cursor is resting on.

    A revealed figure at a glimpse dose stays a shimmer. The secret stays out
    of this panel; talk is what draws it out.
    """
    data = getattr(npc, "data", None) or {}
    if data.get("kind") == "revealed":
        band = getattr(npc, "revealed_band", None) or band_for(exposure)
        if band == GLIMPSE:
            return "A shimmer", "The dose is too thin to hold a face."
    description = data.get("description") or ""
    if description == getattr(npc, "name", ""):
        description = ""
    return npc.name, description


def consider_revelation(
    game: Any,
    npc: Any,
    transport: Callable[..., Any] | None = None,
    api_key: str | None = None,
) -> None:
    """Judge a revealed figure once per dose band, while a dwarf stands beside them."""
    exposure = getattr(getattr(game, "player", None), "spore_exposure", 0)
    band = band_for(exposure)
    npc.revealed_band = band
    if getattr(npc, "judged_band", None) == band:
        return

    key = api_key if api_key is not None else os.environ.get("TYPESAFE_API_KEY", "")
    npc.judged_band = band
    npc.judged = True
    if not key and transport is None:
        _apply_band(npc, band)
        game.add_debug_message(_band_log(npc, band))
        return

    try:
        payload = evaluate(
            _revelation_state(game, npc, band, exposure),
            _revelation_questions(),
            key or "unused",
            opener=transport,
        )
        answers = payload["answers"]
        offer = answers["offer"]["choice"]
        if offer not in ("silence", "counsel", "stair"):
            raise JevError(f"offer {offer} is not silence, counsel, or stair")
        amenable = answers.get("amenable", {}).get("noul", 0)
        npc.amenable = isinstance(amenable, (int, float)) and amenable >= REVEAL_YES
        npc.offer = _cap_offer(band, offer, npc.amenable)
        npc.amenable = band == WELCOME or (band == VOICE and npc.amenable and npc.offer != "silence")
        game.add_debug_message(_band_log(npc, band))
    except (JevError, KeyError, TypeError) as exc:
        _apply_band(npc, band)
        game.add_debug_message(f"{npc.name} could not be judged ({exc}).")


def _apply_band(npc: Any, band: str) -> None:
    if band == WELCOME:
        npc.amenable = True
        npc.offer = "stair"
    elif band == VOICE:
        npc.amenable = False
        npc.offer = "counsel"
    else:
        npc.amenable = False
        npc.offer = "silence"


def _cap_offer(band: str, offer: str, amenable: bool) -> str:
    if band == GLIMPSE:
        return "silence"
    if band == VOICE:
        return "silence" if offer == "silence" and not amenable else "counsel"
    if offer == "stair" or amenable:
        return "stair"
    return "counsel"


def _band_log(npc: Any, band: str) -> str:
    if band == WELCOME:
        return f"{npc.name} welcomes you. The stair is open."
    if band == VOICE:
        return f"{npc.name} finds a voice."
    return f"{npc.name} is only a shimmer."


def _revealed_lines(npc: Any) -> list[str]:
    data = getattr(npc, "data", None) or {}
    band = getattr(npc, "revealed_band", None) or GLIMPSE
    offer = getattr(npc, "offer", None)
    if band == GLIMPSE or offer == "silence":
        return [f"A shimmer stands where a person would be. The dose is too thin to hold {npc.name}."]
    lines = []
    motive = data.get("motive") or data.get("description") or ""
    voice = data.get("voice") or ""
    if motive:
        lines.append(f"{npc.name}: {motive}")
    if voice:
        lines.append(f"({voice})")
    if band == WELCOME and offer == "stair" and data.get("secret"):
        lines.append(f"{npc.name} opens a hand: {data['secret']}")
    if not lines:
        lines.append(f"{npc.name} is present, and says nothing you can keep.")
    return lines


def _revelation_state(game: Any, npc: Any, band: str, exposure: int) -> dict[str, Any]:
    data = getattr(npc, "data", None) or {}
    return {
        "premise": getattr(game, "world_premise", "") or "",
        "dose": {"exposure": exposure, "band": band},
        "character": {
            "name": npc.name,
            "description": data.get("description", ""),
            "motive": data.get("motive", ""),
            "secret": data.get("secret", ""),
            "voice": data.get("voice", ""),
        },
        "situation": "A dwarf stands beside a figure that lives in the mycelium. The dose decides how clearly they resolve.",
    }


def _revelation_questions() -> dict[str, Any]:
    return {
        "amenable": {
            "type": "noul",
            "instructions": "At this dose band, is the figure amenable to the dwarf?",
            "criteria": {
                "true": "They welcome the dwarf and may show a way down",
                "false": "They stay distant",
            },
        },
        "offer": {
            "type": "choice",
            "instructions": "What does this figure offer at `dose.band`? Glimpse can only be silence. Voice can be silence or counsel. Welcome can be counsel or stair.",
            "criteria": {
                "silence": "They do not resolve into a person",
                "counsel": "They speak their motive and keep the secret",
                "stair": "They welcome the dwarf and show what lies under the nexus",
            },
        },
    }


def judge_mission(
    game: Any,
    mission: dict,
    transport: Callable[..., Any] | None = None,
    api_key: str | None = None,
) -> bool:
    """Ask once whether a written success condition has been met.

    Countable requirements are the caller's job. With no key, those counts
    stand and the mission can still finish.
    """
    if mission.get("jev_mission_checked"):
        return bool(mission.get("jev_accomplished"))

    key = api_key if api_key is not None else os.environ.get("TYPESAFE_API_KEY", "")
    mission["jev_mission_checked"] = True
    if not key and transport is None:
        mission["jev_accomplished"] = True
        return True

    try:
        payload = evaluate(_mission_state(game, mission), _mission_questions(), key or "unused", opener=transport)
        noul = payload["answers"]["accomplished"].get("noul", 0)
        done = isinstance(noul, (int, float)) and noul >= ACCOMPLISHED_YES
    except (JevError, KeyError, TypeError) as exc:
        game.add_debug_message(f"Mission judge failed ({exc}).")
        done = True
    mission["jev_accomplished"] = done
    return done


def _encounter_state(game: Any, npc: Any) -> dict[str, Any]:
    data = getattr(npc, "data", None) or {}
    mission = getattr(game, "mission", {}) or {}
    return {
        "premise": getattr(game, "world_premise", "") or "",
        "quest": {
            "title": mission.get("title", ""),
            "summary": mission.get("description", ""),
            "objectives": mission.get("objectives", []),
        },
        "character": {
            "name": npc.name,
            "description": data.get("description", ""),
            "faction": data.get("faction", ""),
            "motive": data.get("motive", ""),
            "secret": data.get("secret", ""),
            "voice": data.get("voice", ""),
        },
        "situation": "A dwarf is standing beside this character.",
    }


def _encounter_questions() -> dict[str, Any]:
    return {
        "helpful": {
            "type": "noul",
            "instructions": "Will this character help the quest, given `character` and `quest`?",
            "criteria": {"true": "They would aid the dwarf", "false": "They would not"},
        },
        "hostile": {
            "type": "noul",
            "instructions": "Is this character hostile to the dwarf right now?",
            "criteria": {"true": "They would threaten or refuse", "false": "They are not hostile"},
        },
        "reveal_secret": {
            "type": "noul",
            "instructions": "Would this character reveal `character.secret` in this meeting?",
            "criteria": {"true": "The secret comes out", "false": "They keep it"},
        },
        "stance": {
            "type": "choice",
            "instructions": "What stance does this character take toward the dwarf?",
            "criteria": {
                "help": "They aid the quest and may speak plainly",
                "wary": "They share only their public motive",
                "hostile": "They threaten the dwarf and say nothing useful",
            },
        },
    }


def _mission_state(game: Any, mission: dict) -> dict[str, Any]:
    resources = {}
    inventory = getattr(game, "inventory", None)
    if inventory is not None:
        for name, qty in mission.get("requirements", {}).items():
            if isinstance(qty, int):
                resources[name] = inventory.resources.get(name, 0)
    return {
        "success": mission.get("success", ""),
        "summary": mission.get("description", ""),
        "evidence": {
            "resources": resources,
            "objectives": mission.get("objectives", []),
            "givers_met": _givers_beside_a_dwarf(game, mission),
        },
    }


def _mission_questions() -> dict[str, Any]:
    return {
        "accomplished": {
            "type": "noul",
            "instructions": "Has this mission been accomplished, given `success` and `evidence`?",
            "criteria": {
                "true": "The written success condition holds",
                "false": "It does not yet hold",
            },
        }
    }


def _givers_beside_a_dwarf(game: Any, mission: dict) -> list[str]:
    names = []
    wanted = set(mission.get("required_npcs") or [])
    for npc in getattr(game, "characters", []):
        if npc.name not in wanted:
            continue
        for dwarf in game.dwarves:
            if abs(dwarf.x - npc.x) + abs(dwarf.y - npc.y) <= 1:
                names.append(npc.name)
                break
    return names
