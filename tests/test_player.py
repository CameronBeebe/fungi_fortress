import pytest
from fungi_fortress.player import Player # Import from package
from fungi_fortress.constants import STARTING_PLAYER_STATS, MAX_SPELL_SLOTS # Import from package

def test_player_initialization_defaults():
    """Test that a Player instance is created with default stats."""
    player = Player() # Uses default STARTING_PLAYER_STATS
    
    assert player.location == STARTING_PLAYER_STATS.get('location')
    assert player.spore_exposure == STARTING_PLAYER_STATS.get('spore_exposure')
    assert player.spells == STARTING_PLAYER_STATS.get('spells')
    assert player.max_carry_weight == STARTING_PLAYER_STATS.get('max_carry_weight')
    assert len(player.spell_slots) == MAX_SPELL_SLOTS
    # Check that starting spells were assigned to slots
    for i, spell in enumerate(STARTING_PLAYER_STATS.get('spells', [])[:MAX_SPELL_SLOTS]):
        assert player.spell_slots[i] == spell

def test_player_initialization_custom_stats():
    """Test initializing Player with custom stats."""
    custom_stats = {
        'location': "Custom Location",
        'spore_exposure': 99,
        'spells': ["Zap", "Boom"],
        'max_carry_weight': 5
        # 'spell_slots' not provided, should default
    }
    player = Player(starting_stats=custom_stats)
    
    assert player.location == "Custom Location"
    assert player.spore_exposure == 99
    assert player.spells == ["Zap", "Boom"]
    assert player.max_carry_weight == 5
    assert len(player.spell_slots) == MAX_SPELL_SLOTS
    assert player.spell_slots[0] == "Zap"
    assert player.spell_slots[1] == "Boom"
    assert player.spell_slots[2] is None # Check remaining slots are empty

def test_player_update_state():
    """Test updating player attributes via update_state."""
    player = Player()
    initial_location = player.location
    player.update_state('location', "New Zone")
    assert player.location == "New Zone"
    
    player.update_state('spore_exposure', player.spore_exposure + 10)
    assert player.spore_exposure == STARTING_PLAYER_STATS.get('spore_exposure', 0) + 10
    
    # Test updating a non-direct attribute (goes into state dict)
    player.update_state('custom_flag', True)
    assert player.state.get('custom_flag') is True

# Add more tests below for spell management methods (assign_spell_to_slot, etc.)
# e.g.
# def test_player_assign_spell_to_slot():
#     player = Player()
#     spell_to_assign = player.spells[0] # Assuming player starts with spells
#     success = player.assign_spell_to_slot(spell_to_assign, 0)
#     assert success is True
#     assert player.spell_slots[0] == spell_to_assign

# Test movement etc. would require a different testing approach, likely involving
# mocking or integrating with GameState/GameLogic, not testing Player in isolation.

# Add more tests below, e.g., test_player_move, test_player_take_damage etc. 