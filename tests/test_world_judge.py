"""Encounter stance and mission reach. No network."""

import json

from fungi_fortress.characters import Dwarf, NPC
from fungi_fortress.missions import check_mission_completion
from fungi_fortress.world_judge import consider_encounter, note_arrivals, speech_lines


class Inventory:
    def __init__(self):
        self.resources = {"fungi": 8, "stone": 0}
        self.special_items = {}


class Player:
    location = "Surface Camp"


class Game:
    def __init__(self):
        self.dwarves = [Dwarf(0, 0, 0)]
        self.characters = []
        self.inventory = Inventory()
        self.player = Player()
        self.mission = {}
        self.mission_complete = False
        self.messages = []
        self.world_premise = "A pale fungus answers to names."
        self.map = []

    def add_debug_message(self, msg):
        self.messages.append(msg)


def _response(payload):
    class Response:
        def read(self):
            return json.dumps(payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def transport(request, timeout):
        transport.calls.append(json.loads(request.data.decode()))
        return Response()

    transport.calls = []
    return transport


def test_helpful_encounter_is_judged_once_and_can_reveal_a_secret():
    game = Game()
    luma = NPC("Luma Capkeeper", 1, 0, data={
        "seed_id": "luma",
        "motive": "Harvest the pale cap.",
        "voice": "Short sentences.",
        "secret": "She already ate one.",
    })
    game.characters.append(luma)
    transport = _response({
        "model": "jev-test",
        "answers": {
            "helpful": {"type": "noul", "noul": 0.9},
            "hostile": {"type": "noul", "noul": 0.1},
            "reveal_secret": {"type": "noul", "noul": 0.8},
            "stance": {"type": "choice", "choice": "help", "confidence": 0.7},
        },
    })
    note_arrivals(game, transport=transport, api_key="test-key")
    note_arrivals(game, transport=transport, api_key="test-key")
    assert len(transport.calls) == 1
    assert luma.stance == "help"
    lines = speech_lines(luma)
    assert any("Harvest the pale cap" in line for line in lines)
    assert any("already ate one" in line for line in lines)


def test_hostile_encounter_hides_the_secret():
    game = Game()
    bram = NPC("Bram Cinder", 0, 1, data={
        "seed_id": "bram",
        "motive": "Brace the forge.",
        "secret": "The axe is buried.",
    })
    game.characters.append(bram)
    consider_encounter(game, bram, transport=_response({
        "model": "jev-test",
        "answers": {
            "helpful": {"type": "noul", "noul": 0.1},
            "hostile": {"type": "noul", "noul": 0.9},
            "reveal_secret": {"type": "noul", "noul": 0.95},
            "stance": {"type": "choice", "choice": "hostile", "confidence": 0.8},
        },
    }), api_key="test-key")
    lines = " ".join(speech_lines(bram))
    assert "Stay back" in lines
    assert "buried" not in lines


def test_reach_is_standing_beside_the_giver():
    game = Game()
    game.characters.append(NPC("Bram Cinder", 1, 0, data={"seed_id": "bram"}))
    game.mission = {
        "seed_quest_id": "brace",
        "requirements": {"stone": 12, "reach": "Forge Mouth"},
        "required_npcs": ["Bram Cinder"],
    }
    game.inventory.resources["stone"] = 12
    assert check_mission_completion(game, game.mission)

    game.dwarves[0].x = 5
    assert not check_mission_completion(game, game.mission)


def test_written_success_is_judged_once():
    game = Game()
    game.mission = {
        "description": "Harvest without waking the grotto.",
        "success": "The pale caps were gathered and the grotto stayed asleep.",
        "requirements": {"fungi": 8},
        "required_npcs": [],
        "objectives": ["Collect 8 fungi"],
    }
    transport = _response({
        "model": "jev-test",
        "answers": {"accomplished": {"type": "noul", "noul": 0.2}},
    })
    from fungi_fortress.world_judge import judge_mission
    assert judge_mission(game, game.mission, transport=transport, api_key="test-key") is False
    assert judge_mission(game, game.mission, transport=transport, api_key="test-key") is False
    assert len(transport.calls) == 1


def test_revealed_figure_resolves_once_per_dose_band():
    game = Game()
    game.player.spore_exposure = 50
    vesper = NPC("Vesper Thread", 1, 0, data={
        "kind": "revealed",
        "motive": "The dose is a key.",
        "secret": "Below the nexus is a cathedral of spice.",
        "voice": "Slow, plural.",
        "seed_id": "vesper",
    })
    game.characters.append(vesper)
    note_arrivals(game, api_key="")
    assert vesper.judged_band == "glimpse"
    assert "shimmer" in speech_lines(vesper)[0]
    note_arrivals(game, api_key="")
    assert sum("shimmer" in message for message in game.messages) == 1

    game.player.spore_exposure = 60
    note_arrivals(game, api_key="")
    assert vesper.offer == "counsel"
    assert any("dose is a key" in line for line in speech_lines(vesper))
    assert all("cathedral" not in line for line in speech_lines(vesper))

    game.player.spore_exposure = 70
    note_arrivals(game, api_key="")
    assert vesper.offer == "stair"
    assert any("cathedral" in line for line in speech_lines(vesper))


def test_cursor_glance_names_a_person_and_hides_a_shimmer():
    from fungi_fortress.world_judge import glance

    luma = NPC("Luma Capkeeper", 2, 2, data={"description": "A young Spore-Keeper.", "kind": "kin"})
    assert glance(luma, 50) == ("Luma Capkeeper", "A young Spore-Keeper.")

    vesper = NPC("Vesper Thread", 3, 3, data={
        "kind": "revealed",
        "description": "A tall shimmer stitched from hyphae.",
        "secret": "Below the nexus is a cathedral.",
    })
    assert glance(vesper, 50)[0] == "A shimmer"
    assert "Vesper" not in glance(vesper, 50)[1]
    assert glance(vesper, 60) == ("Vesper Thread", "A tall shimmer stitched from hyphae.")
