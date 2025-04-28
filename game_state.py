# game_state.py
import random
from typing import List, Dict, Tuple, Optional, Any, TypedDict

# Update constants import to relative
from .constants import MAP_WIDTH, MAP_HEIGHT, STARTING_RESOURCES, STARTING_SPECIAL_ITEMS, STARTING_PLAYER_STATS

# Use relative imports for sibling modules
from .task_manager import TaskManager
from .missions import generate_mission
from .map_generation import generate_map, generate_mycelial_network
from .characters import Dwarf, NPC, Animal, Oracle
from .player import Player
from .inventory import Inventory # Renamed from items to inventory
from .tiles import Tile, ENTITY_REGISTRY
from .entities import GameEntity

MapGrid = List[List[Tile]]

# --- Event Structure Definition ---
class GameEvent(TypedDict):
    type: str         # e.g., "interaction", "combat", "mission_update", "dwarf_task_complete"
    tick: int         # Game tick when the event occurred
    details: Dict[str, Any] # Event-specific data

# Example detail structures (optional, but good practice):
class InteractionEventDetails(TypedDict):
    actor_id: str | int # ID of the character performing the interaction (e.g., "player", dwarf.id)
    target_id: str | int # ID or name of the entity/character being interacted with
    target_type: str   # Type of the target (e.g., "Oracle", "Structure", "Dwarf")
    location: Tuple[int, int]
    outcome: Optional[Any] # Result of the interaction, if any (e.g., quest ID, dialogue result)

class GameState:
    """Manages all the state information for the Fungi Fortress game.

    Attributes:
        player (Player): The player character's state.
        tick (int): The current game tick count.
        depth (int): The current map depth level (0 for surface, <0 for underground).
        cursor_x (int): The current x-coordinate of the player's cursor.
        cursor_y (int): The current y-coordinate of the player's cursor.
        paused (bool): True if the game logic updates are paused.
        show_inventory (bool): True if the inventory screen should be displayed.
        in_shop (bool): True if the shop screen should be displayed.
        show_legend (bool): True if the map legend should be displayed.
        shop_confirm (bool): State variable for shop confirmation steps.
        selected_spell (Optional[str]): Name of the currently selected spell, if any.
        spore_exposure_threshold (int): Threshold for mycelial network effects.
        mission (dict): The current active mission details.
        entry_x (Optional[int]): X-coordinate of the location before entering a sublevel.
        entry_y (Optional[int]): Y-coordinate of the location before entering a sublevel.
        main_map (MapGrid): The grid representing the surface map.
        nexus_site (Optional[Tuple[int, int]]): Coordinates of the Mycelial Nexus.
        magic_fungi_locations (List[Tuple[int, int]]): Coordinates of magic fungi.
        map (MapGrid): The currently active map grid (could be main_map or a sub-level).
        mycelial_network (Dict[Tuple[int, int], List[Tuple[int, int]]]): Adjacency list representation of the network.
        network_distances (Dict[Tuple[int, int], int]): Shortest distance from each network node to the nexus.
        dwarves (List[Dwarf]): List of active dwarf characters.
        animals (List[Animal]): List of active animal characters.
        characters (List[NPC]): List of active NPC characters.
        inventory (Inventory): The player's/colony's inventory.
        shop_carry (Dict[str, int]): Resources available for sale in the shop.
        mission_complete (bool): True if the current mission objectives are met.
        sub_levels (Dict[str, Dict[str, Any]]): Data for sub-levels (maps, active status).
        debug_log (List[str]): A list of recent debug messages.
        task_manager (TaskManager): Manages tasks assigned to dwarves.
        buildings (Dict[str, Dict]): Definitions of buildable structures.
        event_queue (List[GameEvent]): A list of game events.
        show_oracle_dialog (bool): True if the Oracle dialogue window should be displayed.
    """
    def __init__(self) -> None:
        """Initializes the game state.

        Sets up the player, initial map, mission, dwarves, inventory,
        task manager, building definitions, and other core game attributes.
        Also generates the initial mycelial network and calculates distances.
        """
        self.player = Player(STARTING_PLAYER_STATS)
        self.tick = 0
        self.depth = 0
        self.cursor_x = MAP_WIDTH // 2
        self.cursor_y = MAP_HEIGHT // 2
        self.paused = False
        self.show_inventory = False
        self.in_shop = False
        self.show_legend = False
        self.show_oracle_dialog = False
        self.shop_confirm = False
        self.selected_spell = None
        self.spore_exposure_threshold = 20  # Threshold for path illumination
        self.entry_x: Optional[int] = None
        self.entry_y: Optional[int] = None
        
        self.mission = generate_mission(self)
        self.main_map, self.nexus_site, self.magic_fungi_locations = generate_map(
             MAP_WIDTH, MAP_HEIGHT, self.depth, self.mission
         )
        self.map = self.main_map
        
        # Generate mycelial network for the map
        if self.nexus_site:
            self.mycelial_network = generate_mycelial_network(self.main_map, self.nexus_site, self.magic_fungi_locations)
        else:
            self.mycelial_network = {} # Initialize as empty if no nexus
            self.add_debug_message("Warning: Nexus site not found, mycelial network not generated for main map.")
        self.network_distances = self.calculate_network_distances()
        
        self.dwarves: List[Dwarf] = []
        self.animals: List[Animal] = []
        self.characters: List[NPC] = []
        self.inventory = Inventory(STARTING_RESOURCES, STARTING_SPECIAL_ITEMS)
        self.shop_carry = {k: 0 for k in self.inventory.resources.keys()}
        
        spawn_found = False
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                if self.main_map[y][x].walkable:
                    self.dwarves = [Dwarf(x, y, 0)]  # Only spawn one dwarf
                    self.cursor_x, self.cursor_y = x, y
                    spawn_found = True
                    break
            if spawn_found:
                break
        if not spawn_found:
            self.dwarves = [Dwarf(MAP_WIDTH // 2, MAP_HEIGHT // 2, 0)]  # Only spawn one dwarf
            self.cursor_x, self.cursor_y = MAP_WIDTH // 2, MAP_HEIGHT // 2
            self.add_debug_message("Warning: No walkable spawn found, placed dwarf at center")

        self.mission_complete = False
        self.sub_levels: Dict[str, Dict[str, Any]] = {
            # Initialize dynamically or use names from ENTITY_REGISTRY
            # "Shadowed Grotto": {"active": False, "map": None},
        }
        self.debug_log: List[str] = []
        self.task_manager = TaskManager()

        # Define buildable structures: Name -> {requirements, ticks}
        # Requirements: {'resources': {res_name: qty}, 'special_items': {item_name: qty}}
        # Ticks: Time cost for a dwarf to build it.
        self.buildings: Dict[str, Dict] = {
            "Mycelial Nexus": {"resources": {"wood": 10, "fungi": 5}, "special_items": {"Sclerotium": 1}, "ticks": 20},
            "Dwarven Sporeforge": {"resources": {"stone": 15, "wood": 5}, "special_items": {}, "ticks": 15}
        }

        # --- Initialize Event Queue ---
        self.event_queue = []

        self.add_debug_message(f"Map initialized: {len(self.main_map)}x{len(self.main_map[0]) if self.main_map else 0}")
        self.add_debug_message(f"Dwarves spawned: {len(self.dwarves)}")
        self.add_debug_message(f"Fungi locations cached: {len(self.magic_fungi_locations)}")
        self.add_debug_message(f"Mission initialized: description={self.mission.get('description', 'None')}, objectives={self.mission.get('objectives', [])}")

        # --- Spawn Initial Oracle (Depth 0 only) ---
        if self.depth == 0:
            self._spawn_initial_oracle("Whispering Fungus")
        # --- End Oracle Spawn ---

    def add_debug_message(self, msg: str) -> None:
        """Adds a message to the debug log, keeping only the most recent 5.

        Args:
            msg (str): The debug message string to add.
        """
        self.debug_log.append(msg)
        if len(self.debug_log) > 5: 
            self.debug_log.pop(0)

    def get_locations_of_type(self, entity_name: str) -> List[Tuple[int, int]]:
        """Find all coordinates (x, y) of a given entity type name on the current map."""
        locations = []
        if self.map: # Check if map exists
            map_height = len(self.map)
            map_width = len(self.map[0]) if map_height > 0 else 0
            for y in range(map_height):
                for x in range(map_width):
                    # Compare the name of the entity on the tile
                    if self.map[y][x].entity.name == entity_name:
                        locations.append((x, y))
        return locations

    def _initialize_empty_map(self) -> MapGrid:
        """Creates an empty map grid filled with a default entity.

        Used internally as a fallback or potentially for specific map types.

        Returns:
            MapGrid: A list of lists of Tile objects, representing the empty map.
        """
        default_entity = ENTITY_REGISTRY["grass"] # Or choose another default like stone_floor
        return [[Tile(default_entity, x, y) for x in range(MAP_WIDTH)] for y in range(MAP_HEIGHT)]

    def get_tile(self, x: int, y: int) -> Optional[Tile]:
        """Safely get the tile at given coordinates."""
        if 0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT:
            return self.map[y][x]
        return None

    def update_tile_entity(self, x: int, y: int, entity_name: str) -> None:
        """Updates the entity on a specific tile using the entity registry.

        Safely gets the tile and replaces its `entity` attribute with the
        one found in `ENTITY_REGISTRY` under `entity_name`.
        Logs an error if the tile is invalid or the entity name is not found.

        Args:
            x (int): The x-coordinate of the tile to update.
            y (int): The y-coordinate of the tile to update.
            entity_name (str): The key of the new entity in `ENTITY_REGISTRY`.
        """
        tile = self.get_tile(x, y)
        if tile:
            if entity_name in ENTITY_REGISTRY:
                tile.entity = ENTITY_REGISTRY[entity_name]
            else:
                self.add_debug_message(f"Error: Tried to update tile with unknown entity '{entity_name}'")

    def calculate_network_distances(self) -> Dict[Tuple[int, int], int]:
        """Calculates shortest distances from the nexus site to all reachable nodes
        within the current `mycelial_network` using Breadth-First Search (BFS).

        Requires `self.mycelial_network` and `self.nexus_site` to be set.

        Returns:
            Dict[Tuple[int, int], int]: A dictionary mapping network node coordinates
                                        (x, y) to their shortest distance (number of steps)
                                        from the nexus_site. Returns empty if no network/nexus.
        """
        distances: Dict[Tuple[int, int], int] = {}
        
        # If no network or no nexus, return empty distances
        if not self.mycelial_network or not self.nexus_site:
            return distances
            
        # Breadth-first search to find shortest paths
        queue = [(self.nexus_site, 0)]  # (node, distance)
        visited = {self.nexus_site}
        
        while queue:
            node, distance = queue.pop(0)
            distances[node] = distance
            
            for neighbor in self.mycelial_network.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, distance + 1))
        
        return distances
        
    def get_mycelial_distance(self, coords: Tuple[int, int]) -> int:
        """Gets the shortest distance from given coordinates to the nexus site,
        utilizing the pre-calculated mycelial network distances if possible.

        If the `coords` are part of the network, it returns the stored distance.
        If not, it finds the nearest node in the network (Manhattan distance)
        and returns the sum of the distance to that node plus the node's distance
        to the nexus.
        If the network is empty or unreachable, it falls back to the direct
        Manhattan distance between `coords` and `self.nexus_site`.

        Args:
            coords (Tuple[int, int]): The (x, y) coordinates to check.

        Returns:
            int: The calculated distance to the nexus, or 0 if no nexus exists.
        """
        # If coords is already in the network, return its distance
        if coords in self.network_distances:
            return self.network_distances[coords]
            
        # If not in network, find closest network node
        min_dist = 999999 # Use a large int instead of float('inf')
        closest_node = None
        for node in self.network_distances:
            dist = abs(node[0] - coords[0]) + abs(node[1] - coords[1])
            if dist < min_dist:
                min_dist = dist
                closest_node = node
        
        # Return combined distance: to network + through network
        if closest_node:
            return min_dist + self.network_distances.get(closest_node, 0)
            
        # If no network nodes found, use direct distance to nexus as fallback
        if self.nexus_site:
            return abs(coords[0] - self.nexus_site[0]) + abs(coords[1] - self.nexus_site[1])
            
        return 0  # Default if no nexus or network

    # --- New Event Queue Methods ---
    def add_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Adds a structured event to the game's event queue.

        Args:
            event_type (str): The type of event (e.g., 'interaction').
            details (Dict[str, Any]): A dictionary containing event-specific data.
                                       It's recommended this matches a defined TypedDict structure.
        """
        event: GameEvent = {
            "type": event_type,
            "tick": self.tick,
            "details": details
        }
        self.event_queue.append(event)
        # Optional: Add a debug message when events are added
        # self.add_debug_message(f"Event added: {event_type} at tick {self.tick}")

    def consume_events(self) -> List[GameEvent]:
        """Retrieves all current events and clears the queue.

        Returns:
            List[GameEvent]: The list of events that were in the queue.
        """
        events = self.event_queue
        self.event_queue = []
        return events
    # --- End New Event Queue Methods ---

    # --- Helper to spawn initial Oracle ---
    def _spawn_initial_oracle(self, name: str) -> None:
        """Finds a random walkable tile and spawns the initial Oracle.
        
        Args:
            name (str): The name for the Oracle.
        """
        possible_locations: List[Tuple[int, int]] = []
        dwarf_pos = (self.dwarves[0].x, self.dwarves[0].y) if self.dwarves else None
        
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                tile = self.get_tile(x, y)
                # Check if walkable and not where the dwarf spawns
                if tile and tile.walkable and (x, y) != dwarf_pos:
                    possible_locations.append((x, y))
        
        if possible_locations:
            ox, oy = random.choice(possible_locations)
            oracle = Oracle(name, ox, oy)
            self.characters.append(oracle)
            self.add_debug_message(f"Oracle '{name}' spawned at ({ox}, {oy}).")
        else:
            self.add_debug_message(f"Warning: Could not find suitable location to spawn Oracle '{name}'.")
    # --- End Helper --- 
