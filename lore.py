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
    "oracles": {
        "Whispering Fungus": {
            "description": "An ancient, sentient mushroom that communicates through psionic echoes and rustling cap-flesh.",
            "canned_responses": {
                "greeting": [
                    "The Whispering Fungus quivers as you approach.",
                    "Its ancient thoughts brush against yours..."
                ],
                "no_api_key": [
                    "The Whispering Fungus hums faintly, its deepest connections dormant today."
                ],
                "greeting_offering_no_llm": [
                    "The Fungus accepts your offering with a gentle quiver.",
                    "Though its connection to the cosmic mycelium is faint, it imparts a simple truth:",
                    "Patience and perseverance uncover hidden paths in the deep."
                ],
                "no_offering_made": [
                    "The Fungus remains still, its whispers too faint to discern without a sign of respect.",
                    "A worthy offering might amplify its voice."
                ],
                "insufficient_offering": [
                    "The Whispering Fungus senses your intent, but the offering is not quite right or enough.",
                    "It requires the agreed-upon tribute to resonate fully."
                ],
                "generic_wisdom": [
                    "The Oracle ponders... It sees patterns in the spores, echoes in the stone.",
                    "Consider the path of the blind mole rat; even in darkness, it finds its way.",
                    "ACTION::add_message::{'text': 'A faint psionic echo resonates from the Oracle.'}"
                ],
                "generic_fallback": [
                    "The Oracle murmurs ancient, untranslatable words.",
                    "Focus on your immediate surroundings; clarity will come."
                ],
                "event_response_mushroom_growth": [
                    "The Oracle senses a surge in the mycelial network. New growth has occurred.",
                    "Seek out the fresh caps, for they hold potent secrets.",
                    "ACTION::spawn_resource::{'type': 'magic_fungi', 'x': 12, 'y': 22, 'amount': 3}"
                ],
                "player_low_health_tip": [
                    "The Oracle perceives your life force is dimming. You are injured.",
                    "Seek sustenance. The glowing moss can restore, or perhaps a carefully prepared fungal brew."
                ]
            }
        },
        "Echoing Geode": {
            "description": "A massive, hollow geode that resonates with the planet's core and the whispers of deep earth spirits.",
            "canned_responses": {
                "greeting": [
                    "The Echoing Geode hums with a low thrum as you near it.",
                    "Its crystalline facets shimmer with inner light."
                ],
                "no_api_key": [
                    "The Geode's resonance is muted, its connection to the earth-songs weak."
                ],
                "greeting_offering_no_llm": [
                    "The Geode accepts your tribute, its light pulsing once in acknowledgement.",
                    "It shares a fragment of earth-wisdom:",
                    "Solid foundations support the grandest structures. Dig deep."
                ],
                "no_offering_made": [
                    "The Geode remains largely silent, its deepest echoes reserved for those who show respect."
                ],
                "insufficient_offering": [
                    "The Geode pulses slowly, indicating the offering is not what it expects or needs.",
                    "The earth spirits require the customary tribute."
                ],
                "generic_wisdom": [
                    "The Geode resonates... It speaks of pressure, time, and transformation.",
                    "That which is hidden often holds the greatest value. Explore every crevice."
                ],
                "generic_fallback": [
                    "The Geode emits a series of cryptic rumbles.",
                    "Patience. The earth reveals its secrets in its own time."
                ]
            }
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
        },
        "Spore Pouch": {
            "description": "A sturdy pouch woven from giant puffball fibers, ideal for carrying spores.",
            "location": "Mission Reward",
            "magic_properties": "Allows carrying more spore types? (Gameplay effect TBD)"
        },
        "Map Fragment": {
            "description": "A torn piece of parchment showing a section of the tunnels.",
            "location": "Various",
            "magic_properties": "Reveals part of the map when used? (Gameplay effect TBD)"
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
