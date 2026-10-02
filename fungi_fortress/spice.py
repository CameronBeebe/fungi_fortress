"""Spice is the dose and the sense organ.

Starting exposure is 50, enough for a small spell and not enough to see clearly.
One magic fungus adds 5. The bands are the threshold where a revealed figure resolves.
"""

from __future__ import annotations

GLIMPSE = "glimpse"
VOICE = "voice"
WELCOME = "welcome"

VOICE_AT = 55
WELCOME_AT = 65


def band_for(exposure: int) -> str:
    """How clearly the network's people can be seen at this dose."""
    if exposure >= WELCOME_AT:
        return WELCOME
    if exposure >= VOICE_AT:
        return VOICE
    return GLIMPSE


def linger_ticks(exposure: int) -> int:
    """How long a revealed mycelial path stays lit. Higher dose, longer sight."""
    return 75 + max(0, exposure)


def pulse_sends(path_length: int, exposure: int) -> int:
    """How many times the nexus repeats a pulse. The dose adds repeats."""
    return 3 + max(0, path_length) // 5 + max(0, exposure) // 20
