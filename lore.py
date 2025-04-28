import json
from typing import Dict, Any

"""Central repository for game lore, including history, places, events,
characters, items, magic details, factions, and quests.

This data is primarily stored in the `lore_base` dictionary and used by various
parts of the game (e.g., character initialization, mission generation, item descriptions).

The structure allows for easy modification and potential loading from external
JSON files in the future.
"""

lore_base: Dict[str, Any] = {
    "history": {
        "The Mycelial Dawn": {
            "description": "Long ago, the dwarves of Eryndor discovered the Mycelial Nexus, a cavern pulsing with fungal magic. This sparked the rise of spore-based civilization, forging tools and spells from luminous fungi."
        },
        "The Spore Schism": {
            "description": "A rift formed when the Spore-Keepers hoarded the most potent fungi, leading to the exile of the Shadow Mycologists and a fractured realm."
        }
    },
    "places": {
        "Mycelial Nexus": {
            "description": "A glowing fungal cavern, the heart of dwarven magic, filled with towering mushrooms and psychedelic spores.",
            "events": ["The Great Spore Bloom"],
            "characters": ["Zorak Sporeweaver"],
            "items": ["Psychedelic Polyp"]
        },
        "Dwarven Sporeforge": {
            "description": "A subterranean forge where dwarves meld metal with fungal spores, crafting enchanted gear under a haze of glowing dust.",
            "events": ["The Forge Bloom"],
            "characters": ["Krag Ironspore"],
            "items": ["Sporeforged Axe"]
        },
        "Shadowed Grotto": {
            "description": "A dark fungal maze where exiled Shadow Mycologists experiment with corrupted spores.",
            "events": ["The Spore Purge"],
            "characters": ["Vyx the Corruptor"],
            "items": ["Corrupted Spore"]
        }
    },
    "events": {
        "The Great Spore Bloom": {
            "description": "A surge of spores floods the Nexus, granting visions and spawning rare fungi.",
            "characters_involved": ["Zorak Sporeweaver"],
            "outcome": "New fungal growths appear"
        },
        "The Forge Bloom": {
            "description": "Spores ignite the forge, creating a rare artifact but risking corruption.",
            "characters_involved": ["Krag Ironspore"],
            "outcome": "Sporeforged Axe crafted"
        },
        "The Spore Purge": {
            "description": "The Shadow Mycologists unleash a corrupted spore wave, threatening the Nexus.",
            "characters_involved": ["Vyx the Corruptor"],
            "outcome": "Ongoing conflict"
        }
    },
    "characters": {
        "Zorak Sporeweaver": {
            "description": "A revered dwarf shaman who communes with the Nexus spores for wisdom.",
            "faction": "Spore-Keepers",
            "quests": ["Harvest the Psychedelic Bloom"]
        },
        "Krag Ironspore": {
            "description": "A master smith blending fungal spores with steel, seeking to perfect his craft.",
            "faction": "Spore-Keepers",
            "quests": ["Forge the Spore Relic"]
        },
        "Vyx the Corruptor": {
            "description": "An exiled dwarf obsessed with corrupted fungi, plotting to overtake the Nexus.",
            "faction": "Shadow Mycologists",
            "quests": ["Purge the Corrupted Grotto"]
        }
    },
    "special_items": {
        "Psychedelic Polyp": {
            "description": "A luminous mushroom emitting visions of the mycelial web.",
            "location": "Mycelial Nexus",
            "magic_properties": "Grants foresight (spore_exposure +5)"
        },
        "Sporeforged Axe": {
            "description": "An axe infused with fungal strength, releasing spores on impact.",
            "location": "Dwarven Sporeforge",
            "magic_properties": "Spore burst on hit"
        },
        "Corrupted Spore": {
            "description": "A dark spore radiating malevolent energy, twisting nearby life.",
            "location": "Shadowed Grotto",
            "magic_properties": "Corrupts terrain"
        },
        "Sclerotium": {
            "description": "A dried hyphae core storing mycelial network memories.",
            "location": "Mycelial Nexus",
            "magic_properties": "Capable of growing a new Nexus"
        }
    },
    "magic": {
        "Spore Resonance": {
            "description": "Magic harnessing fungal vibrations for power.",
            "spells": {
                "Spore Cloud": {"cost": 5, "effect": "Blinds enemies"},
                "Mycelial Binding": {"cost": 10, "effect": "Traps foes in fungal tendrils"}
            }
        }
    },
    "factions": {
        "Spore-Keepers": {
            "description": "Guardians of fungal magic, protectors of the Nexus.",
            "allies": [],
            "enemies": ["Shadow Mycologists"]
        },
        "Shadow Mycologists": {
            "description": "Exiled dwarves experimenting with corrupted spores.",
            "allies": [],
            "enemies": ["Spore-Keepers"]
        }
    },
    "quests": {
        "Harvest the Psychedelic Bloom": {
            "description": "Gather rare spores from the Nexus for Zorak Sporeweaver.",
            "objectives": ["Reach the Mycelial Nexus", "Collect 3 Psychedelic Polyps"],
            "rewards": ["Spore Pouch", "Spore Cloud spell"],
            # Updated: Changed game.resources to game.inventory.resources
            "condition": lambda game: game.inventory.resources["magic_fungi"] >= 3
        },
        "Forge the Spore Relic": {
            "description": "Assist Krag Ironspore in crafting a relic at the Sporeforge.",
            "objectives": ["Gather 5 fungi", "Deliver to Dwarven Sporeforge"],
            "rewards": ["Sporeforged Axe"],
            # Updated: Changed game.resources to game.inventory.resources and game.player_state to game.player
            "condition": lambda game: game.inventory.resources["fungi"] >= 5 and game.player.location == "Dwarven Sporeforge"
        },
        "Purge the Corrupted Grotto": {
            "description": "Defeat Vyx the Corruptor to stop the spread of corrupted spores.",
            "objectives": ["Reach the Shadowed Grotto", "Defeat Vyx the Corruptor"],
            "rewards": ["Crystal Shard"],
            "condition": lambda game: "Vyx the Corruptor" not in [c.name for c in game.characters if c.alive]
        }
    }
}

def load_lore_from_file(file_path: str) -> dict:
    """Loads lore data from a specified JSON file.

    Intended for future expansion where lore might be managed externally.
    If the file is not found, it prints a debug message and returns the
    default `lore_base` dictionary defined in this module.

    Args:
        file_path (str): The path to the JSON file containing lore data.

    Returns:
        dict: The loaded lore data, or the default `lore_base` if loading fails.
    """
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Debug: {file_path} not found, using default lore_base.")
        return lore_base

if __name__ == "__main__":
    print("Lore Test: Places =", list(lore_base["places"].keys()))
    print("Quest Test: Harvest Objectives =", lore_base["quests"]["Harvest the Psychedelic Bloom"]["objectives"])
