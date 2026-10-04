# AGENTS.md

Guidance for coding agents (Cursor, Codex, Claude Code, etc.) working on Fungi Fortress.

## What This Is

Fungi Fortress is an agentic gaming harness—a deterministic game engine where LLMs generate content and choices through typed interfaces. The architecture uses general mechanisms over hard-coding: every NPC, character, and Oracle goes through the same code paths; all generated content (world seeds, encounters, revelations) follows Pydantic schemas; handcrafted content comes in as data, not bespoke code.

## LLM Contract (Decided Architecture)

Every LLM call that feeds the game declares its output type in code as a Pydantic model. The harness:

1. Generates the JSON Schema from that Pydantic type
2. Sends it to xAI via structured outputs (`response_format` json_schema; tool calling when choosing actions)
3. Lets the API enforce shape and required fields
4. Runs semantic validators (cross-references, counts like exactly-one-revealed) on the parsed result
5. Retries with the specific error message fed back to the model (bounded attempts)
6. Logs every rejection with a preview
7. On final failure, uses a prepared fallback and notifies the player

**Never fix a bad model output by tweaking prompt wording alone or by loosening parsers.** If outputs are wrong, the missing piece is schema/validator/retry.

**Note:** Migration to this architecture is in progress. Today `llm_client.py` has one hard-coded Oracle schema and world-seed calls run without a schema.

## Providers

- **Online:** xAI only (configured in `llm_config.ini.example`, currently `grok-3-mini`)
- **Offline:** Built-in mock provider for game calls (no API key required)
- **Judge:** Jev/TypeSafe is separate as a judge, not a game content provider

**Do not add other providers.** xAI + mock is the decided architecture.

## No Special Cases

Special characters go through the same generic NPC paths. No bespoke code paths or Oracle-only fixes:

- The Oracle is a unique NPC that only becomes visible at high spore exposure, but uses the same dialogue and interaction systems as any NPC
- NPCs spawn wherever they could live (any habitable tile of the final map); no rules tied to specific mechanics like bridges
- Handcrafted content (prebuilt campaigns, characters, narrative arcs) comes in as data through the same seed loader, not as code

## Reality Model: One Core, Many Views

The architecture treats reality as one core world with many views—different filters or prisms onto the same underlying state.

- **Core:** The engine simulates one real, interconnected world. All entities (dwarves, NPCs, items, terrain) exist here, including ones the ordinary view never shows. The core is what's actually simulated; it's the ground truth.
- **View:** A function, prism, or filter from the core to the player's experience. It determines what's visible, how things look, how characters behave, and which actions are available. The "ordinary" view (baseline perception, no spores) is just one view with no special status.
- **Spore exposure shifts views.** Some views are core and repeatable; trips can generate new views on the fly. A trip might render the mycelium network as glowing pathways, reveal hidden figures, or recolor the entire world—all transformations of the same core.
- **Actions act on the core.** If you mine a block in a trip, the block is gone when you sober up. If you give an item to the Oracle, that item is gone in the ordinary view. Relationship changes persist across views.

**Naming:** Use "core" and "view" in code. Avoid the word "layer" because it implies ordinary reality is true and the rest is illusion. Backend values (exposure numbers, band thresholds) are debug-only; real play hides them behind a toggle (F1 planned).

**See [`PLANNING.md`](PLANNING.md#reality-model-one-core-many-views-proposed-open-for-discussion) for full architectural detail and open questions.**

## Player-Facing vs Debug

Backend values—stats, exposure numbers, exposure bands, stance values—are debug-only, visible only via a toggle (F1 planned). Real play doesn't show them. Exposure should be felt through visual transformations, not read as numbers.

## Working Rules for Agents

### Code Changes

- **Small reviewable PRs:** A few files, reviewable in minutes. One fix per commit.
- **Never force-push or rewrite pushed history.** If you need to update a branch that has fallen behind, merge master into it (no rebase).
- **Fix failing tests at the root cause, not by editing the test.** Tests define the contract; if a test fails, the code is wrong.
- **Run `uv run pytest` before pushing.** All tests must pass.

### Security

- **Never log or commit API keys.** Logs go to `logs/` (or `FUNGI_LOG_DIR` if overridden). The repo has a security test that scans for leaked keys; it runs in CI.

### Pull Requests

- **Title format:** Clear, specific, present tense (e.g. "Add AGENTS.md: architecture and working rules for agents")
- **Body must include exact test steps,** saying which folder to run from:
  ```
  Testing:
  1. From workspace root, run `uv run pytest`
  2. All tests pass (227 passing)
  ```
- **Link to related issues** or `TODO.md` items if applicable

### Dependencies and Tooling

- **Package manager:** uv (preferred) or pip
- **Install:** `uv sync` (uses `uv.lock` for exact versions)
- **Run:** `uv run fungi` or `uv run pytest`
- **Python version:** 3.10+ (3.12 recommended)

## Repository Layout

Key modules (as of Oct 2026):

- **`fungi_fortress/`** — Main package
  - `game_logic.py` — Core simulation loop and event processing
  - `game_state.py` — World state, player, NPCs, inventory
  - `map_generation.py` — Procedural map and entity spawning
  - `dwarf_mind.py` — Autonomous dwarf task AI (template for systems)
  - `world_seed.py` — World seed validation and generation (moving to Pydantic)
  - `world_judge.py` — Jev/TypeSafe judge for stance, revelation, mission success
  - `llm_client.py` — LLM client (currently one hard-coded Oracle schema)
  - `llm_oracle.py`, `oracle_logic.py` — Oracle dialogue and encounter logic
  - `jev_client.py` — Jev/TypeSafe integration
  - `renderer.py` — Curses-based UI rendering
  - `input_handler.py` — Keyboard input and command mapping
  - `task_manager.py` — Dwarf task queue and execution
  - `magic.py` — Spell system and spore exposure
  - `missions.py` — Quest and mission tracking
  - `tiles.py`, `entities.py` — Tile and entity definitions
  - `cli.py` — Entry point (`fungi` command)
- **`tests/`** — Test suite (227 passing as of Oct 2026)
- **`logs/`** — Runtime logs (git-ignored)
- **`main.py`** — Legacy entry point (use `uv run fungi` instead)
- **`README.md`** — Project overview, setup, and features
- **`PLANNING.md`** — Overhaul plan, architectural decisions, and phased roadmap
- **`TODO.md`** — Running backlog of work items

**Future refactoring (see [`PLANNING.md`](PLANNING.md#target-architecture)):** The plan is to extract a pure `engine/` (no curses, no network, no os.environ), a `content/` layer with typed schemas and ports (Grower, Judge, SceneDrawer, Oracle), and a `ui/` layer with curses and future web renderers. Not done yet.
