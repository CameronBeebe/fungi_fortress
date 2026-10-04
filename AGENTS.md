# AGENTS.md

Guidance for coding agents (Cursor, Codex, Claude Code, etc.) working on Fungi Fortress.

## What This Is

Fungi Fortress is an agentic gaming harness—a deterministic game engine where LLMs generate content and choices through typed interfaces. The architecture uses general mechanisms over hard-coding: every NPC, character, and Oracle goes through the same code paths; every LLM call that feeds the game must declare a typed (Pydantic) output (migration in progress); handcrafted content comes in as data, not bespoke code.

## LLM Contract (Decided Architecture)

Every LLM call that feeds the game must declare its output type as a Pydantic model. The harness generates JSON Schema from that type, sends it to xAI via structured outputs (`response_format` json_schema; tool calling when choosing actions), lets the API enforce shape and required fields, runs semantic validators, retries with error feedback (bounded attempts), logs rejections, and falls back on final failure.

**Implementation:** `llm_client.structured_call` exists and world/depth seed generation uses it (Pydantic model `WorldSeedSchema`, reused for both; `parse_world_seed` is the single set of semantic rules for both LLM and hand-written seeds). Oracle and other calls are not migrated yet.

**Never fix a bad model output by tweaking prompt wording alone or by loosening parsers.** If outputs are wrong, the missing piece is schema/validator/retry.

## Providers

- **Online:** xAI only. Model is set by `model_name` in `llm_config.ini` (example default `grok-4.3`)
- **Offline:** Built-in mock provider for game calls (no API key required)
- **Judge:** Jev/TypeSafe is separate as a judge, not a game content provider

**Do not add other providers.** xAI + mock is the decided architecture.

## No Special Cases

Special characters go through the same generic NPC paths. No bespoke code paths or Oracle-only fixes:

- The Oracle is a unique NPC planned to only become visible at high spore exposure, using the same dialogue and interaction systems as any NPC
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

- **Small reviewable PRs:** A few files, reviewable in minutes. If a PR grows past a few files, split it before asking for review. One fix per commit.
- **Never force-push or rewrite pushed history.** If you need to update a branch that has fallen behind, merge master into it (no rebase).
- **Fix failing tests:** Find and fix the root cause; never weaken, skip, or delete a test to make it pass. If a test itself is wrong, say so explicitly in the PR.
- **Testing philosophy:** Test core contracts (the typed LLM path, validators, world rules, and things that broke before). Don't write wasteful tests or tests that pin details likely to change. The project changes fast, so don't over-invest in tests or box the design in.
- **Run `uv run pytest` before pushing.** All tests must pass.
- **Greenfield, no outside users:** When something is replaced or deprecated, remove it completely (no backwards-compatibility fallbacks, aliases, or legacy branches) unless there's a stated reason to keep it.

### Security

- **Never log or commit API keys.** Logs go to `logs/` (or `FUNGI_LOG_DIR` if overridden). The repo has a security test that scans for leaked keys; it runs in CI.

### Pull Requests

- **Title format:** Clear, specific, present tense (e.g. "Add AGENTS.md: architecture and working rules for agents")
- **Body must include exact test steps,** saying which folder to run from:
  ```
  Testing:
  From workspace root, run `uv run pytest`
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
  - `app.py` — Startup; `initialize_new_game()` shared by game and tests
  - `game_logic.py` — Core simulation loop and event processing
  - `game_state.py` — World state, player, NPCs, inventory
  - `map_generation.py` — Procedural map and entity spawning
  - `dwarf_mind.py` — Autonomous dwarf task AI (template for systems)
  - `world_seed.py` — World seed Pydantic models and validation; `parse_world_seed` semantic rules
  - `world_judge.py` — Jev/TypeSafe judge for stance, revelation, mission success
  - `llm_client.py` — LLM client with `structured_call` (typed outputs); Oracle not migrated yet
  - `llm_world.py` — World-seed LLM calls
  - `llm_oracle.py`, `oracle_logic.py` — Oracle dialogue and encounter logic
  - `jev_client.py` — Jev/TypeSafe integration
  - `characters.py` — Dwarf, NPC, and character classes
  - `renderer.py` — Curses-based UI rendering
  - `input_handler.py` — Keyboard input and command mapping
  - `task_manager.py` — Dwarf task queue and execution
  - `magic.py` — Spell system and spore exposure
  - `missions.py` — Quest and mission tracking
  - `tiles.py`, `entities.py` — Tile and entity definitions
  - `cli.py` — Entry point (`fungi` command)
  - `seeds/` — Hand-written world/depth seed JSON (data path for handcrafted content)
- **`tests/`** — Test suite
- **`logs/`** — Runtime logs (git-ignored)
- **`main.py`** — Legacy entry point (use `uv run fungi` instead)
- **`README.md`** — Project overview, setup, and features
- **`PLANNING.md`** — Overhaul plan, architectural decisions, and phased roadmap
- **`TODO.md`** — Running backlog of work items

**Future refactoring (see [`PLANNING.md`](PLANNING.md#target-architecture)):** The plan is to extract a pure `engine/` (no curses, no network, no os.environ), a `content/` layer with typed schemas and ports (Grower, Judge, SceneDrawer, Oracle), and a `ui/` layer with curses and future web renderers. Not done yet.
