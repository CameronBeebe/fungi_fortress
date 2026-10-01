from .lore import lore_base
from typing import Optional, Dict, List, Tuple

class Inventory:
    """Represents the player/colony's inventory, holding resources and special items.

    Also tracks resources gained since the last reset, useful for displaying
    session gains.

    Attributes:
        resources (dict[str, int]): Dictionary mapping standard resource names
                                   (e.g., 'wood', 'stone', 'gold') to their quantities.
        resources_gained (dict[str, int]): Dictionary tracking how much of each standard
                                         resource has been gained since the last call to
                                         `reset_resources_gained`.
        special_items (dict[str, int]): Dictionary mapping special item names
                                       (e.g., 'Sclerotium', 'Map Fragment') to their quantities.
                                       The list of known special items is derived from `lore_base`.
    """
    def __init__(self, starting_resources: Optional[Dict[str, int]] = None, starting_items: Optional[Dict[str, int]] = None) -> None:
        """Initializes the inventory.

        Sets up the resource and special item dictionaries. If starting values
        are not provided, resources default to 0, and special items default to 0
        based on the keys found in `lore_base["special_items"]`.
        Also initializes the `resources_gained` tracker.

        Args:
            starting_resources (dict, optional): Initial quantities for standard resources.
                                                Defaults to a predefined set with 0 quantities.
            starting_items (dict, optional): Initial quantities for special items.
                                           Defaults to 0 for all items listed in lore.
        """
        # Default resources if none provided
        default_res = {"stone": 0, "wood": 0, "food": 0, "gold": 0, "crystals": 0, "fungi": 0, "magic_fungi": 0}
        self.resources = starting_resources if starting_resources is not None else default_res
        
        # Initialize resources gained based on current resources
        self.resources_gained = {k: 0 for k in self.resources.keys()}
        
        # Default special items based on lore if none provided
        default_items = {item: 0 for item in lore_base.get("special_items", {}).keys()}
        self.special_items = starting_items if starting_items is not None else default_items

    def add_resource(self, resource: str, amount: int):
        """Adds a specified amount of a resource or special item.

        Determines whether the `resource` name corresponds to a standard resource
        or a special item and updates the appropriate dictionary. If it's a
        standard resource, also increments the `resources_gained` counter.
        Prints an error if the resource name is unknown.

        Args:
            resource (str): The name of the resource or special item to add.
            amount (int): The quantity to add (should be positive).
        """
        if resource in self.resources:
            self.resources[resource] += amount
            self.resources_gained[resource] += amount
        elif resource in self.special_items:
            self.special_items[resource] += amount
        else:
            print(f"Unknown resource: {resource}")

    def remove_resource(self, resource: str, amount: int):
        """Removes a specified amount of a resource or special item.

        Checks for sufficient quantity before removing. Determines if the `resource`
        name is a standard resource or special item and updates the correct dictionary.
        Prints an error if the resource is unknown or insufficient.

        Note: Does not affect `resources_gained`.

        Args:
            resource (str): The name of the resource or special item to remove.
            amount (int): The quantity to remove (should be positive).
        """
        if resource in self.resources:
            if self.resources[resource] >= amount:
                self.resources[resource] -= amount
            else:
                print(f"Not enough {resource} to remove {amount}")
        elif resource in self.special_items:
            if self.special_items[resource] >= amount:
                self.special_items[resource] -= amount
            else:
                print(f"Not enough {resource} to remove {amount}")
        else:
            print(f"Unknown resource: {resource}")

    def remove_item(self, item_name: str, amount: int):
        """Removes a specified amount of a special item.

        Checks for sufficient quantity before removing.
        Prints an error if the item is unknown or insufficient.

        Args:
            item_name (str): The name of the special item to remove.
            amount (int): The quantity to remove (should be positive).
        """
        if item_name in self.special_items:
            if self.special_items[item_name] >= amount:
                self.special_items[item_name] -= amount
            else:
                print(f"Not enough {item_name} to remove {amount}")
        else:
            print(f"Unknown special item: {item_name}")

    def reset_resources_gained(self):
        """Resets all counters in the `resources_gained` dictionary to zero.

        Typically called after descending to a new level or displaying session gains.
        """
        for res in self.resources_gained:
            self.resources_gained[res] = 0

    def can_afford(self, cost: List[Tuple[str, int]]) -> bool:
        """Checks if the inventory has enough resources for a given cost.

        Args:
            cost (List[Tuple[str, int]]): A list of tuples, where each tuple is
                                         (resource_name, amount_needed).

        Returns:
            bool: True if all resources are affordable, False otherwise.
        """
        for resource_name, amount_needed in cost:
            if resource_name in self.resources:
                if self.resources[resource_name] < amount_needed:
                    return False # Not enough of this standard resource
            elif resource_name in self.special_items:
                if self.special_items[resource_name] < amount_needed:
                    return False # Not enough of this special item
            else:
                return False # Unknown resource/item in cost
        return True

# Removed global dictionaries (resources, resources_gained, special_items) and add_resource function
# These are now encapsulated within the Inventory class to centralize inventory management
