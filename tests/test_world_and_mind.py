"""Schema and dwarf-choice tests. No network."""

import json
import os

from fungi_fortress.characters import Dwarf, Task
from fungi_fortress.dwarf_mind import assign_work
from fungi_fortress.game_logic import GameLogic
from fungi_fortress.world_seed import apply_world_seed, grow_world, load_world_seed, parse_world_seed

SEED_PATH = os.path.join(os.path.dirname(__file__), "..", "fungi_fortress", "seeds", "example_world.json")


class Entity:
    def __init__(self, name, walkable=True, description=""):
        self.name = name
        self.walkable = walkable
        self.description = description


class Tile:
    def __init__(self, name, walkable=True):
        self.entity = Entity(name, walkable, name)
    
    @property
    def walkable(self):
        """Delegate walkable to entity like the real Tile class."""
        return self.entity.walkable


class Tasks:
    def __init__(self):
        self.tasks = []

    def remove_task(self, task):
        self.tasks.remove(task)


class Game:
    def __init__(self, width=5, height=1):
        self.map = [[Tile("Grass") for _ in range(width)] for _ in range(height)]
        self.dwarves = [Dwarf(0, 0, 0)]
        self.characters = []
        self.task_manager = Tasks()
        self.messages = []
        self.mission = {}

    def get_tile(self, x, y):
        if y < 0 or x < 0 or y >= len(self.map) or x >= len(self.map[0]):
            return None
        return self.map[y][x]

    def add_debug_message(self, msg):
        self.messages.append(msg)


def test_example_seed_is_executable():
    seed = load_world_seed(SEED_PATH)
    assert seed.quests[0].requirements[0].resource == "fungi"
    assert seed.characters[0].secret


def test_seed_rejects_invented_resources_and_givers():
    seed = json.loads(open(SEED_PATH, encoding="utf-8").read())
    seed["quests"][0]["requirements"] = [{"kind": "collect", "resource": "hope", "count": 1}]
    try:
        parse_world_seed(seed)
    except ValueError as exc:
        assert "unknown resource" in str(exc)
    else:
        raise AssertionError("invented resource was accepted")

    seed = json.loads(open(SEED_PATH, encoding="utf-8").read())
    seed["quests"][0]["giver_id"] = "nobody"
    try:
        parse_world_seed(seed)
    except ValueError as exc:
        assert "giver" in str(exc)
    else:
        raise AssertionError("unknown giver was accepted")


def test_apply_seed_sets_mission_and_spawns():
    game = Game(width=4, height=2)
    apply_world_seed(game, load_world_seed(SEED_PATH))
    assert game.mission["requirements"] == {"fungi": 8}
    names = {npc.name for npc in game.characters}
    assert names == {"Luma Capkeeper", "Bram Cinder", "Vesper Thread"}
    assert game.characters[0].data["secret"]


def test_nearest_task_without_jev():
    game = Game(width=6, height=1)
    near = Task(1, 0, "mine")
    far = Task(5, 0, "chop")
    game.task_manager.tasks = [far, near]
    assign_work(game)
    dwarf = game.dwarves[0]
    assert dwarf.task is near
    assert dwarf.state == "moving"
    assert far in game.task_manager.tasks


def test_orders_ignore_jev_and_take_the_nearest():
    game = Game(width=6, height=1)
    near = Task(1, 0, "mine")
    far = Task(5, 0, "chop")
    game.task_manager.tasks = [far, near]
    assign_work(game)
    assert game.dwarves[0].task is near
    assert game.dwarves[0].state == "moving"


def test_grow_world_uses_the_model_and_installs_it():
    game = Game(width=4, height=2)
    seen = []

    def complete(prompt):
        seen.append(prompt)
        with open(SEED_PATH, encoding="utf-8") as handle:
            return handle.read()

    note = grow_world(game, complete=complete)
    assert note.startswith("The Pale Cap")
    assert game.world_premise
    assert {npc.name for npc in game.characters} == {"Luma Capkeeper", "Bram Cinder", "Vesper Thread"}
    assert seen and "JSON" in seen[0]


def test_grow_world_retries_a_bad_draft_once():
    game = Game(width=4, height=2)
    calls = []

    def complete(prompt):
        calls.append(prompt)
        if len(calls) == 1:
            return '{"title": "broken"}'
        with open(SEED_PATH, encoding="utf-8") as handle:
            return handle.read()

    grow_world(game, complete=complete)
    assert len(calls) == 2
    assert "rejected" in calls[1]
    assert game.mission["requirements"]["fungi"] == 8


def test_chop_starts_when_already_beside_the_tree():
    game = Game(width=3, height=1)
    game.map[0][2] = Tile("Tree", walkable=False)
    dwarf = game.dwarves[0]
    dwarf.x, dwarf.y = 1, 0
    dwarf.state = "moving"
    dwarf.path = []
    dwarf.task = Task(1, 0, "chop", 2, 0)
    GameLogic(game)._update_dwarf(dwarf)
    assert dwarf.state == "chopping"
    assert dwarf.task.type == "chop"
    assert any("chopping" in line for line in game.messages)


def test_chop_starts_after_the_last_step():
    game = Game(width=3, height=1)
    dwarf = game.dwarves[0]
    dwarf.state = "moving"
    dwarf.path = [(1, 0)]
    dwarf.task = Task(1, 0, "chop", 2, 0)
    GameLogic(game)._update_dwarf(dwarf)
    assert (dwarf.x, dwarf.y) == (1, 0)
    assert dwarf.state == "chopping"


def test_seeded_people_do_not_start_beside_the_dwarf():
    game = Game(width=20, height=12)
    apply_world_seed(game, load_world_seed(SEED_PATH))
    for npc in game.characters:
        assert abs(npc.x - 0) + abs(npc.y - 0) >= 4


def test_bridge_queues_only_if_the_existing_orders_would_reach_it():
    from fungi_fortress.input_handler import bridge_stand

    game = Game(width=1, height=4)
    game.map = [[Tile("Grass")], [Tile("Water", False)], [Tile("Water", False)], [Tile("Water", False)]]
    dwarf = game.dwarves[0]
    assert bridge_stand(game, dwarf, 0, 1) == (0, 0)
    game.task_manager.tasks.append(Task(0, 0, "build_bridge", 0, 1))
    assert bridge_stand(game, dwarf, 0, 2) == (0, 1)
    assert bridge_stand(game, dwarf, 0, 3) is None

    # Grass past the first bridge becomes a stand once that order is built.
    game = Game(width=4, height=1)
    game.map = [[Tile("Grass"), Tile("Water", False), Tile("Grass"), Tile("Water", False)]]
    dwarf = game.dwarves[0]
    assert bridge_stand(game, dwarf, 3, 0) is None
    game.task_manager.tasks.append(Task(0, 0, "build_bridge", 1, 0))
    assert bridge_stand(game, dwarf, 3, 0) == (2, 0)


def test_nexus_build_places_the_structure_and_pays():
    from fungi_fortress.constants import STARTING_RESOURCES, STARTING_SPECIAL_ITEMS
    from fungi_fortress.inventory import Inventory

    game = Game(width=3, height=1)
    game.inventory = Inventory(dict(STARTING_RESOURCES), dict(STARTING_SPECIAL_ITEMS))
    game.buildings = {
        "Mycelial Nexus": {"resources": {"wood": 10, "fungi": 5}, "special_items": {"Sclerotium": 1}, "ticks": 20}
    }
    dwarf = game.dwarves[0]
    dwarf.task = Task(1, 0, "build", 2, 0, building="Mycelial Nexus")
    GameLogic(game)._complete_building(dwarf, game.map[0][1])
    assert game.map[0][2].entity.name == "Mycelial Nexus"
    assert game.map[0][1].entity.name == "Grass"
    assert game.inventory.resources["wood"] == 0
    assert game.inventory.special_items["Sclerotium"] == 0


def test_dose_bands_and_a_longer_pulse():
    from fungi_fortress.spice import VOICE, WELCOME, band_for, linger_ticks, pulse_sends

    assert band_for(50) == "glimpse"
    assert band_for(55) == VOICE
    assert band_for(65) == WELCOME
    assert linger_ticks(65) > linger_ticks(50)
    assert pulse_sends(5, 65) > pulse_sends(5, 50)


def test_depth_holds_the_surface_mission_aside():
    from fungi_fortress.world_seed import enter_depth, leave_depth

    game = Game(width=16, height=10)
    apply_world_seed(game, load_world_seed(SEED_PATH))
    surface = game.mission
    names = {npc.name for npc in game.characters}
    enter_depth(game)
    assert game.in_depth
    assert game.spice_grade == 2
    assert game.mission["requirements"]["magic_fungi"] == 3
    assert "The Choir Beneath" == game.depth_title
    assert {npc.name for npc in game.characters}.isdisjoint(names)
    leave_depth(game)
    assert game.mission is surface
    assert {npc.name for npc in game.characters} == names
    assert game.spice_grade == 1
