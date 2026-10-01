# player.py
from typing import List, Dict, Any, Optional

# Revert constants import to relative
try:
    from .constants import STARTING_PLAYER_STATS, MAX_SPELL_SLOTS # Ensure relative
except ImportError:
    # Define fallback stats if constants isn't found
    STARTING_PLAYER_STATS = {
        'location': "Unknown",
        'completed_quests': [],
        'spore_exposure': 0,
        'spells': [],
        'max_carry_weight': 10,
        'spell_slots': [None] * 5
    }
    MAX_SPELL_SLOTS = 5
    print("Warning: Could not import STARTING_PLAYER_STATS from .constants, using fallback.")

class Player:
    """Represents the player's state and attributes within the game.

    This class holds information directly related to the player, such as
    location, completed quests, spore exposure level, learned spells, spell slots,
    and carrying capacity. It provides methods for managing spell assignments
    and updating player state.

    Attributes:
        location (str): The current named location of the player (e.g., "Surface Camp", "Mycelial Nexus").
        completed_quests (List[str]): A list of descriptions of completed quests.
        spore_exposure (int): The player's current level of spore exposure, used as a resource for casting spells.
        spells (List[str]): A list of all spell names the player has learned.
        spell_slots (List[Optional[str]]): A fixed-size list representing the spell hotbar.
                                          Each element holds a spell name or None.
        max_carry_weight (int): The maximum weight of resources the player can carry between levels.
        state (Dict[str, Any]): A dictionary for storing any additional, less common player state variables.
    """
    def __init__(self, starting_stats: Dict[str, Any] = STARTING_PLAYER_STATS):
        """Initializes the player state from a dictionary of starting stats.

        Populates direct attributes like location, spells, etc., and initializes
        the spell slots based on the starting spells list. Any remaining stats
        from the input dictionary are stored in the `self.state` dictionary.

        Args:
            starting_stats (Dict[str, Any], optional): A dictionary containing initial values
                                                    for player attributes. Defaults to
                                                    `STARTING_PLAYER_STATS` from constants.
        """
        # Use a general state dictionary to hold player attributes
        # self.state: Dict[str, Any] = starting_stats.copy()

        # Add direct attributes instead of using state dict for most things
        self.location: str = starting_stats.get('location', "Unknown")
        self.completed_quests: List[str] = starting_stats.get('completed_quests', [])
        self.spore_exposure: int = starting_stats.get('spore_exposure', 0)
        self.spells: List[str] = starting_stats.get('spells', [])
        self.spell_slots: List[Optional[str]] = starting_stats.get('spell_slots', [None] * MAX_SPELL_SLOTS)
        self.max_carry_weight: int = starting_stats.get('max_carry_weight', 10)

        # Initialize spell slots with starting spells
        for i, spell in enumerate(self.spells[:MAX_SPELL_SLOTS]):
            self.spell_slots[i] = spell

        # If we need to store other misc state, we can keep the dict for that
        self.state: Dict[str, Any] = {k: v for k, v in starting_stats.items() 
                                    if k not in ['location', 'completed_quests', 'spore_exposure', 
                                               'spells', 'max_carry_weight', 'spell_slots']}

        # Ensure essential keys exist, even if not in starting_stats (Less needed now)
        # self.state.setdefault('location', "Unknown")
        # self.state.setdefault('completed_quests', [])
        # self.state.setdefault('spore_exposure', 0)
        # self.state.setdefault('spells', [])
        # self.state.setdefault('max_carry_weight', 10)

        # Removed direct attributes like self.inventory, self.spells etc.
        # GameState manages the actual Inventory object.
        # Player state holds simpler data like location, quests, spells learned.

    def update_state(self, key: str, value: Any):
        """Updates a specific player attribute or state variable.

        Checks if the `key` corresponds to a direct attribute (like `location` or
        `spore_exposure`) and updates it. Otherwise, updates the value in the
        fallback `self.state` dictionary.

        Args:
            key (str): The name of the attribute or state variable to update.
            value: The new value to assign.
        """
        # Check if it's a direct attribute first
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            # Fallback to the state dictionary for other values
            self.state[key] = value
        # Optionally add validation or logging here

    def get_spell_in_slot(self, slot_index: int) -> Optional[str]:
        """Retrieves the name of the spell in the specified hotbar slot.

        Args:
            slot_index (int): The index of the spell slot (0-based).

        Returns:
            Optional[str]: The name of the spell in the slot, or None if the slot
                           is empty or the index is invalid.
        """
        if 0 <= slot_index < MAX_SPELL_SLOTS:
            return self.spell_slots[slot_index]
        return None

    def assign_spell_to_slot(self, spell: str, slot_index: int) -> bool:
        """
        Assigns a learned spell to a specific hotbar slot.

        Args:
            spell (str): The name of the spell to assign (must be in `self.spells`).
            slot_index (int): The index of the spell slot (0-based).

        Returns:
            bool: True if the assignment was successful, False otherwise (invalid slot
                  or spell not learned).
        """
        if 0 <= slot_index < MAX_SPELL_SLOTS and spell in self.spells:
            self.spell_slots[slot_index] = spell
            return True
        return False

    def clear_spell_slot(self, slot_index: int) -> bool:
        """Removes the spell from the specified hotbar slot.

        Args:
            slot_index (int): The index of the spell slot to clear (0-based).

        Returns:
            bool: True if the slot index was valid and cleared, False otherwise.
        """
        if 0 <= slot_index < MAX_SPELL_SLOTS:
            self.spell_slots[slot_index] = None
            return True
        return False

    def get_next_empty_slot(self) -> Optional[int]:
        """Finds the index of the first available (empty) spell slot.

        Returns:
            Optional[int]: The 0-based index of the first empty slot, or None if
                           all spell slots are currently assigned.
        """
        try:
            return self.spell_slots.index(None)
        except ValueError:
            return None

    def get_spell_slot_index(self, spell: str) -> Optional[int]:
        """Finds the hotbar slot index where a given spell is assigned.

        Args:
            spell (str): The name of the spell to find.

        Returns:
            Optional[int]: The 0-based index of the slot containing the spell,
                           or None if the spell is not assigned to any slot.
        """
        try:
            return self.spell_slots.index(spell)
        except ValueError:
            return None

    def cycle_spell_selection(self, current_spell: Optional[str], direction: int = 1) -> Optional[str]:
        """Cycles the selected spell among the spells currently in the hotbar slots.

        Moves forward (direction=1) or backward (direction=-1) through the
        non-empty spell slots, wrapping around the ends.

        Args:
            current_spell (Optional[str]): The name of the spell currently selected,
                                          or None if no spell is selected.
            direction (int, optional): The direction to cycle (1 for forward, -1 for backward).
                                     Defaults to 1.

        Returns:
            Optional[str]: The name of the next spell in the cycle. Returns the
                           `current_spell` if no other spells are slotted, or None
                           if the spell slots are entirely empty.
        """
        if not any(slot is not None for slot in self.spell_slots):
            return None

        # Find current slot index
        current_index = -1
        if current_spell is not None:
            for i, spell in enumerate(self.spell_slots):
                if spell == current_spell:
                    current_index = i
                    break

        # Find next non-empty slot
        num_slots = len(self.spell_slots)
        next_index = (current_index + direction) % num_slots
        while next_index != current_index:
            if self.spell_slots[next_index] is not None:
                return self.spell_slots[next_index]
            next_index = (next_index + direction) % num_slots

        # If we didn't find a next spell but have spells, return the first non-empty slot
        if current_index == -1:
            for i, spell in enumerate(self.spell_slots):
                if spell is not None:
                    return spell

        return current_spell  # Keep current spell if no other options found

# Comment out __main__ block
# if __name__ == "__main__":
#     player = Player() # Now uses STARTING_PLAYER_STATS by default
#     print(f"Initial Location: {player.location}")
#     player.update_state("location", "Mycelial Nexus")
#     print(f"New Location: {player.location}")
#     print(f"Spells: {player.spells}")
