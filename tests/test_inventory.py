import pytest
from fungi_fortress.inventory import Inventory # Import from package
from fungi_fortress.constants import STARTING_RESOURCES, STARTING_SPECIAL_ITEMS # Import from package

# Sample resource and item names used in the game
SAMPLE_RESOURCE = "wood"
SAMPLE_SPECIAL_ITEM = "Sclerotium" # Assuming this is a valid special item from lore
UNKNOWN_ITEM = "magic rock"

def test_inventory_initialization_defaults():
    """Test that Inventory initializes with default resources and items if none provided."""
    inventory = Inventory()
    # Check default resources (should be 0 for all standard types)
    assert inventory.resources.get("stone", 0) == 0
    assert inventory.resources.get("wood", 0) == 0
    assert inventory.resources.get("food", 0) == 0
    assert inventory.resources.get("gold", 0) == 0
    assert inventory.resources.get("crystals", 0) == 0
    assert inventory.resources.get("fungi", 0) == 0
    assert inventory.resources.get("magic_fungi", 0) == 0
    
    # Check default special items (should be 0, requires lore_base to be implicitly loaded)
    # We might need to mock lore_base or ensure it's available if this fails
    assert inventory.special_items.get(SAMPLE_SPECIAL_ITEM, 0) == 0 
    assert len(inventory.resources_gained) == len(inventory.resources)
    assert all(v == 0 for v in inventory.resources_gained.values())

def test_inventory_initialization_with_values():
    """Test initializing Inventory with specific starting values."""
    start_res = {"wood": 50, "gold": 10}
    start_items = {SAMPLE_SPECIAL_ITEM: 2}
    inventory = Inventory(starting_resources=start_res, starting_items=start_items)
    
    assert inventory.resources["wood"] == 50
    assert inventory.resources["gold"] == 10
    assert inventory.resources.get("stone", 0) == 0 # Check unspecified defaults to 0
    
    assert inventory.special_items[SAMPLE_SPECIAL_ITEM] == 2
    # Assuming "Map Fragment" is another special item from lore. If not, adjust.
    assert inventory.special_items.get("Map Fragment", 0) == 0 

def test_inventory_add_resource():
    """Test adding standard resources."""
    inventory = Inventory()
    inventory.add_resource(SAMPLE_RESOURCE, 15)
    assert inventory.resources[SAMPLE_RESOURCE] == 15
    assert inventory.resources_gained[SAMPLE_RESOURCE] == 15
    
    inventory.add_resource(SAMPLE_RESOURCE, 5)
    assert inventory.resources[SAMPLE_RESOURCE] == 20
    assert inventory.resources_gained[SAMPLE_RESOURCE] == 20

def test_inventory_add_special_item():
    """Test adding special items."""
    inventory = Inventory()
    inventory.add_resource(SAMPLE_SPECIAL_ITEM, 1) # Special items added via add_resource too
    assert inventory.special_items[SAMPLE_SPECIAL_ITEM] == 1
    # resources_gained should not track special items
    assert inventory.resources_gained.get(SAMPLE_SPECIAL_ITEM) is None 
    
    inventory.add_resource(SAMPLE_SPECIAL_ITEM, 2)
    assert inventory.special_items[SAMPLE_SPECIAL_ITEM] == 3

def test_inventory_add_unknown_item(capsys):
    """Test adding an unknown item prints an error."""
    inventory = Inventory()
    inventory.add_resource(UNKNOWN_ITEM, 1)
    captured = capsys.readouterr()
    assert f"Unknown resource: {UNKNOWN_ITEM}" in captured.out
    assert UNKNOWN_ITEM not in inventory.resources
    assert UNKNOWN_ITEM not in inventory.special_items

def test_inventory_remove_resource_sufficient():
    """Test removing standard resources when available."""
    inventory = Inventory(starting_resources={SAMPLE_RESOURCE: 20})
    inventory.reset_resources_gained() # Reset gained counter for clarity
    inventory.remove_resource(SAMPLE_RESOURCE, 5)
    assert inventory.resources[SAMPLE_RESOURCE] == 15
    assert inventory.resources_gained.get(SAMPLE_RESOURCE, 0) == 0 # remove shouldn't affect gained

def test_inventory_remove_resource_insufficient(capsys):
    """Test removing standard resources when insufficient."""
    inventory = Inventory(starting_resources={SAMPLE_RESOURCE: 5})
    inventory.remove_resource(SAMPLE_RESOURCE, 10)
    captured = capsys.readouterr()
    assert f"Not enough {SAMPLE_RESOURCE}" in captured.out
    assert inventory.resources[SAMPLE_RESOURCE] == 5 # Amount should not change

def test_inventory_remove_special_item_sufficient():
    """Test removing special items when available (using remove_resource)."""
    inventory = Inventory(starting_items={SAMPLE_SPECIAL_ITEM: 3})
    inventory.remove_resource(SAMPLE_SPECIAL_ITEM, 2)
    assert inventory.special_items[SAMPLE_SPECIAL_ITEM] == 1

def test_inventory_remove_special_item_insufficient(capsys):
    """Test removing special items when insufficient (using remove_resource)."""
    inventory = Inventory(starting_items={SAMPLE_SPECIAL_ITEM: 1})
    inventory.remove_resource(SAMPLE_SPECIAL_ITEM, 2)
    captured = capsys.readouterr()
    assert f"Not enough {SAMPLE_SPECIAL_ITEM}" in captured.out
    assert inventory.special_items[SAMPLE_SPECIAL_ITEM] == 1

def test_inventory_remove_item_method():
    """Test the dedicated remove_item method for special items."""
    inventory = Inventory(starting_items={SAMPLE_SPECIAL_ITEM: 3})
    inventory.remove_item(SAMPLE_SPECIAL_ITEM, 1) # Uses remove_item
    assert inventory.special_items[SAMPLE_SPECIAL_ITEM] == 2

def test_inventory_remove_item_method_insufficient(capsys):
    """Test remove_item method when insufficient."""
    inventory = Inventory(starting_items={SAMPLE_SPECIAL_ITEM: 1})
    inventory.remove_item(SAMPLE_SPECIAL_ITEM, 2) # Uses remove_item
    captured = capsys.readouterr()
    assert f"Not enough {SAMPLE_SPECIAL_ITEM}" in captured.out
    assert inventory.special_items[SAMPLE_SPECIAL_ITEM] == 1
    
def test_inventory_remove_unknown_item(capsys):
    """Test removing an unknown item prints an error."""
    inventory = Inventory()
    inventory.remove_resource(UNKNOWN_ITEM, 1)
    captured = capsys.readouterr()
    assert f"Unknown resource: {UNKNOWN_ITEM}" in captured.out

def test_inventory_reset_resources_gained():
    """Test resetting the gained resources counter."""
    inventory = Inventory()
    inventory.add_resource(SAMPLE_RESOURCE, 10)
    assert inventory.resources_gained[SAMPLE_RESOURCE] == 10
    inventory.reset_resources_gained()
    assert inventory.resources_gained[SAMPLE_RESOURCE] == 0
    # Ensure resources themselves are unchanged
    assert inventory.resources[SAMPLE_RESOURCE] == 10 