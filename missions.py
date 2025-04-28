"""Handles the generation, parsing, checking, and completion of game missions.

Missions are based on quests defined in the `lore_base` dictionary.
This module provides functions to:
- Select an available quest and format it as a mission dictionary.
- Parse quest objectives into a structured requirements dictionary.
- Check if the current game state satisfies the mission requirements.
- Update the game state upon mission completion (grant rewards, mark complete).
"""
import random
from typing import TYPE_CHECKING, List, Dict, Union, Any

# Update imports to relative
from .lore import lore_base
from .constants import MAP_HEIGHT, MAP_WIDTH # Needed for loop bounds

if TYPE_CHECKING:
    # Use relative path for type hints
    from .game_state import GameState

def generate_mission(game: 'GameState') -> dict:
    """Generates a new mission for the player.

    Selects a random, uncompleted quest from `lore_base["quests"]`.
    Formats the quest data into a mission dictionary containing description,
    objectives, rewards, involved places, parsed requirements, and required NPCs.
    Ensures a default requirement if none are parsed from objectives.

    Args:
        game (GameState): The current game state, used to check completed quests.

    Returns:
        dict: A dictionary representing the generated mission.
              Returns a default "No missions available" structure if all quests
              are completed.
    """
    available_quests = [q for q in lore_base["quests"].keys() if q not in game.player.completed_quests]
    if not available_quests:
        return {
            "description": "No missions available",
            "objectives": [],
            "rewards": [],
            "requirements": {"fungi": 1},  # Ensure a minimal requirement
            "required_npcs": []
        }
    
    quest_name = random.choice(available_quests)
    quest = lore_base["quests"][quest_name]
    required_npcs = [char for char in lore_base["characters"] if char in quest["description"] or any(char in obj for obj in quest["objectives"])]
    mission = {
        "description": quest["description"],
        "objectives": quest["objectives"],
        "rewards": quest["rewards"],
        "places": [p for p in lore_base["places"] if p in " ".join(quest["objectives"])],
        "requirements": parse_objectives(quest["objectives"]),
        "required_npcs": required_npcs
    }
    # Ensure the mission has at least one non-trivial requirement
    if not mission["requirements"]:
        mission["requirements"] = {"fungi": 1}  # Default requirement if none parsed
    return mission

def parse_objectives(objectives: List[str]) -> Dict[str, Union[int, str]]:
    """Parses a list of quest objective strings into a requirements dictionary.

    Identifies keywords like "collect", "gather", "defeat", "reach", "deliver to"
    to extract requirement types and values (item names, quantities, NPC names, place names).

    Args:
        objectives (List[str]): A list of strings, each describing a quest objective.

    Returns:
        dict: A dictionary where keys are requirement types (e.g., 'stone', 'magic_fungi',
              'defeat', 'reach', 'deliver') and values are the corresponding quantities
              or names.
    """
    reqs: Dict[str, Union[int, str]] = {}
    for obj in objectives:
        obj_lower = obj.lower()
        if "collect" in obj_lower or "gather" in obj_lower:
            parts = obj_lower.split()
            for i, part in enumerate(parts):
                if part.isdigit():
                    qty = int(part)
                    item = " ".join(parts[i+1:]).replace("s", "")
                    reqs[item] = qty
        elif "defeat" in obj_lower:
            name = " ".join(obj.split()[1:])
            reqs["defeat"] = name
        elif "reach" in obj_lower or "deliver to" in obj_lower:
            place = " ".join(obj.split()[1:]) if "reach" in obj_lower else " ".join(obj.split()[2:])
            for p in lore_base["places"]:
                if p.lower() in place:
                    reqs["reach" if "reach" in obj_lower else "deliver"] = p
                    break
    return reqs

def check_mission_completion(game: 'GameState', mission: dict) -> bool:
    """Checks if the current game state satisfies the mission's requirements.

    Iterates through the parsed requirements in the `mission` dictionary.
    Checks player inventory, character states (alive/defeated), player location,
    and potentially dwarf location/state for delivery tasks against the required values.

    Args:
        game (GameState): The current game state object.
        mission (dict): The mission dictionary containing the parsed `requirements`.

    Returns:
        bool: True if all mission requirements are met, False otherwise.
    """
    reqs = mission.get("requirements", {}) # Use .get for safety
    # Use relative imports if accessing internal game components
    from .tiles import ENTITY_REGISTRY # Might be needed if checking against entity objects directly
    from .entities import Structure # Example if checking type

    for req, value in reqs.items():
        if req in game.inventory.resources:
            if game.inventory.resources[req] < value:
                return False
        elif req in game.inventory.special_items:
            if game.inventory.special_items[req] < value:
                return False
        elif req == "defeat":
            if any(c.name == value and c.alive for c in game.characters):
                return False
        elif req == "reach":
            # Check player location (string comparison is fine here)
            if game.player.location != value:
                return False
        elif req == "deliver":
            # Ensure resources are required and location is met
            # Check inventory first
            resource_to_deliver = None
            required_amount = 0
            for item, amount in reqs.items():
                if item in game.inventory.resources: # Assume only one resource delivery per mission for now
                    resource_to_deliver = item
                    required_amount = amount
                    break
            if resource_to_deliver and game.inventory.resources.get(resource_to_deliver, 0) < required_amount:
                 game.add_debug_message(f"Deliver check failed: Not enough {resource_to_deliver}")
                 return False
            
            # Check if a dwarf is at the delivery location (which is stored in 'value')
            # Location could be an NPC name or a Structure/Place name
            delivery_location_name = value
            dwarf_at_location = False
            
            # Check if delivery target is an NPC
            target_npc = next((npc for npc in game.characters if npc.name == delivery_location_name and npc.alive), None)
            if target_npc:
                 if any(d.x == target_npc.x and d.y == target_npc.y and d.state == "idle" for d in game.dwarves):
                     dwarf_at_location = True
            # Check if delivery target is a Structure/Place on the map
            else:
                 # Iterate through tiles to find the structure/place by name
                 for y in range(MAP_HEIGHT):
                     for x in range(MAP_WIDTH):
                         # Need safe access to map tile
                         tile = game.get_tile(x, y) 
                         # Check the entity name on the tile
                         if tile and tile.entity.name == delivery_location_name:
                             # Check if any idle dwarf is at this tile location
                             if any(d.x == x and d.y == y and d.state == "idle" for d in game.dwarves):
                                 dwarf_at_location = True
                                 break # Found dwarf at this location instance
                     if dwarf_at_location:
                          break # Found dwarf at a matching location
            
            if not dwarf_at_location:
                 game.add_debug_message(f"Deliver check failed: No idle dwarf at {delivery_location_name}")
                 return False
        # Add checks for other requirement types if needed
        # ...

    # If all checks passed
    return True

def complete_mission(game: 'GameState', mission: dict):
    """Updates the game state upon successful mission completion.

    Adds the mission description to the player's completed quests list.
    Grants rewards specified in the mission dictionary (resources, items, spells).
    Sets the `game.mission_complete` flag to True.
    Adds a debug message.

    Args:
        game (GameState): The current game state object to update.
        mission (dict): The completed mission dictionary containing rewards.
    """
    # Ensure description exists before appending
    mission_desc = mission.get("description", "Unknown Mission")
    game.player.completed_quests.append(mission_desc)
    
    for reward in mission.get("rewards", []): # Use .get for safety
        # Check resource types first
        if reward in game.inventory.resources:
            game.inventory.add_resource(reward, 1)
        elif reward.endswith("spell"):
            game.player.spells.append(reward)
        else:
            game.inventory.add_resource(reward, 1)  # Assuming special items use the same method
    game.mission_complete = True
    game.add_debug_message("Mission completed!")

# Comment out or remove the __main__ block
# if __name__ == "__main__":
#    from .main import Game # This import won't work easily
#    game = Game()
#    mission = generate_mission(game)
#    print("Generated Mission:", mission)
#    # Updated to use Inventory method for testing
#    game.inventory.add_resource("magic_fungi", 3)
#    if check_mission_completion(game, mission):
#        complete_mission(game, mission)
#        print("Player Completed Quests:", game.player.completed_quests)
#        print("Player Spells:", game.player.spells)
