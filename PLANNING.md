# Fungi Fortress: Overhaul Plan

Draft, 2026-10-01. Based on `master` (872cbc1) and PR #1 (`seeded-world-jev-observer`). Local uncommitted work is not reflected.

## Goals

1. A portfolio piece that shows LLM work done well: typed, validated model output; Jev (TypeSafe System One) as an observer/judge; DSPy (and later Flex/GEPA) where it earns its place.
2. Playable on cameronbeebe.github.io, a static GitHub Pages site, with no secrets in client code.
3. A codebase that is small, testable, and deterministic everywhere except clearly fenced model calls.

## Guiding idea

PR #1's notes already state the split: "the terminal remains the place a world is grown and judged." Make that the architecture.

- **Grow mode (terminal, Python, keys available):** world growth, Jev judgments, DSPy/Flex programs, and crystallization of scenes.
- **Play mode (terminal or browser):** a deterministic engine that plays a grown seed plus its crystallized scenes. Live model calls are optional and off by default in the browser.

This turns "how do we run DSPy in a browser?" into a non-problem. The browser plays artifacts that grow mode produced. Live calls in the browser are a bonus (bring-your-own key), not a requirement.

## Target architecture

```
fungi_fortress/
  engine/          pure-ish simulation, no curses, no network, no os.environ
    state.py       typed World, Dwarf, NPC, Inventory, Mission (dataclasses)
    commands.py    Move, Mine, Build, Talk, Cast, Descend ... (typed)
    systems/       tasks.py (dwarf_mind), movement.py, magic.py, missions.py, spice.py
    step.py        step(world, commands, rng) -> list[Event]
  worldgen/        map + noise (pure Python or numpy, seeded), seed parsing, spawning
  content/         everything model-shaped, behind interfaces
    schemas.py     Pydantic models: WorldSeed, Encounter, Revelation, MissionVerdict, Scene
    ports.py       Protocols: Grower, Judge, SceneDrawer, Oracle
    mock.py        deterministic fixtures for every port (tests + offline play)
    chat.py        ONE OpenAI-compatible chat client (xAI, OpenAI, Groq, Together...)
    jev.py         Judge implementation over System One
    dspy_oracle.py optional extra, imported only in grow mode
    crystal.py     store/load crystallized scenes keyed by (figure, place, band)
  app/             controller: input -> commands, events -> view model, schedules async content calls
  ui/
    curses_ui.py   terminal renderer
    web/           browser renderer (DOM/canvas grid) + Pyodide bootstrap
  cli.py           `fungi play`, `fungi grow`, `fungi crystallize`
tests/
seeds/             prepared and grown worlds (JSON), plus crystals
```

Rules that hold it together:

- `engine/` never imports `content/`, `ui/`, `os`, `urllib`, or `logging` handlers. It emits `Event`s (e.g. `DwarfMetNPC`, `MissionCountsMet`) and accepts results back as commands (e.g. `ApplyEncounter(npc_id, stance, reveal)`).
- Model calls are async and never block a tick. The controller sees an event, fires the call, and applies the typed result when it lands. Until then the game shows the deterministic fallback.
- Every model output is parsed into a Pydantic model at the boundary. Game code never sees raw JSON or `"Error: ..."` strings.
- One RNG, seeded from the world seed, is passed explicitly.
- I'd soften the "immutable state" idea some reviews push: mutable dataclasses mutated only inside `engine/systems` are fine for a Python sim. The thing that matters is that nothing outside the engine mutates it.

## Where Jev and DSPy fit

- **Jev = `Judge` port.** Encounter stance, revelation per dose band, and written mission success. It keeps PR #1's rule that Jev is never on the player-order path.
- **DSPy = `Grower` / `SceneDrawer` / `Oracle` implementations in grow mode.** Signatures map 1:1 to the Pydantic schemas. Start with plain `Predict` against the three patterns in `DSPY_JEV_IDEAS.md`. Add Flex/GEPA only once there's a metric and a train/val set from crystallized re-encounters.
- **Jev as the metric.** A nice portfolio angle: use Jev judgments (e.g. "does this glimpse-band scene leak the figure's name or secret?") as part of the DSPy/GEPA metric. A typed judge scoring a typed generator is a clean story.
- Keep DSPy and the TypeSafe SDK as optional extras (`pip install fungi-fortress[grow]`) with pinned versions, never runtime deps of play mode.

## Every NPC is a generative character (added 2026-10-01)

The Oracle is the proof of concept; every character should work the same way.
- **Typed persona per character** in the seed: voice, style, motive, secret, knowledge, relationships, quest hooks. All generated content (WorldSeed, Character, Place, Quest, Item) gets a Pydantic schema, mirrored by DSPy signatures in grow mode.
- **Split of roles:** Jev judges (stance, what may be disclosed at this exposure band, quest success); the LLM speaks within those limits. The mock speaks the same schema with no key.
- **Dialogue window for all NPCs** (generalized from the Oracle UI), with per-NPC conversation memory and streaming once the step-2 client lands.
- **Stance is re-judged** when context changes (exposure band, gifts, quest progress), not frozen after the first meeting.
- **Quests come from characters**: multiple quests per seed, new ones offered in dialogue, a quest log.

The running backlog lives in `TODO.md`.

## Spore exposure and perception (draft ideas, open for discussion)

**This section is brainstorming and not decided.** It's open for discussion and subject to change.

- **Exposure should be felt, not read.** Bands change how the world looks rather than showing numbers. Current debug readouts are for development only; real play hides backend values, with a debug/"show stats" toggle (e.g. F1) for development.
- **Perception layers:** as exposure rises, an overlay is drawn over the map (glowing mycelium, hidden figures and paths revealed, drifting colors and glyphs). Part of the overlay is true and part is false (water drawn as solid ground, a wall that looks passable). Skilled players learn tells, e.g. false tiles flicker on a rhythm while real ones stay steady. High-exposure visuals and reveals should be very elaborate and detailed.
- **Pros and cons:** high exposure reveals secrets, unlocks dialogue, and shows what others can't see. It also makes navigation more dangerous (orders sent to things that aren't there, bridges to nowhere), and some creatures may be dangerous or visible only at high exposure.
- **Decay and tolerance:** exposure fades over time, so it's a resource to manage. Repeated doses may build tolerance or leave lasting traces.
- **LLM/Jev fit:** Jev judges what is real and what a figure will disclose at the current band; the LLM writes how it looks and sounds, more elaborate and stranger at deeper bands, but within typed schemas so a hallucination can never break the game rules.
- **Engineering rule:** the engine keeps one true map. Exposure changes only what is drawn and described (a perception layer over a deterministic engine), which keeps it testable.
- **Open questions:** how much is false vs. true at each band; how decay and tolerance work; whether other NPCs react to the player's exposure; how the debug toggle interacts with the overlay.

## Phased plan (small PRs, rough effort with agent help)

**Phase 0: make it a real package ✓ COMPLETED (PR #2)**
- Moved modules under `fungi_fortress/`, added `pyproject.toml`, added uv tooling with `uv.lock`
- Added GitHub Actions CI with pytest and mypy
- All tests passing, `fungi` console command working

**Phase 1: consolidate the LLM plumbing (1 day)**
- Replace the three provider paths (`fungi_fortress/llm_interface.py` dispatch, `fungi_fortress/config_manager.py` detect_provider_from_model, `fungi_fortress/world_seed.py` _chat) with one `content/chat.py` OpenAI-compatible client. Anthropic gets its own small adapter or is dropped.
- Typed exceptions only. Delete streaming/non-streaming duplication by building the prompt once.
- Add `content/mock.py` and make it the default when no key is present.

**Phase 2: schemas and ports (1 day)**
- Port `fungi_fortress/world_seed.py` validation to Pydantic (keep the limits: 12 characters, 400-char text, 1 to 99 counts). Keep `_ensure_one_revealed` as an explicit normalization step, separate from validation.
- Define `Grower`, `Judge`, `SceneDrawer`, `Oracle` protocols. Re-home `fungi_fortress/world_judge.py` logic so it returns `Encounter` / `Revelation` / `MissionVerdict` objects instead of setting attributes on NPCs.

**Phase 3: engine extraction (2 to 3 days)**
- Split `GameState` into world state vs UI state (`show_inventory`, prompt buffers, cursor -> `app/`).
- Break `fungi_fortress/game_logic.py` into systems. `fungi_fortress/dwarf_mind.py` is the template.
- Engine emits events; controller schedules content calls asynchronously. Fixed-timestep loop stays.
- Add save/load (JSON of world state + seed + crystals). It's cheap once state is typed, and the browser needs it (localStorage).

**Phase 4: renderer interface (1 to 2 days)**
- `ui/curses_ui.py` renders a view model only. Input maps to commands in `app/`.
- Remove dead code: `fungi_fortress/events.py` stubs, Sporeforge stub, `oracle_streaming_buffer`, unused canned-response lists.

**Phase 5: browser proof of concept (2 to 3 days)**
- Replace the `noise` C extension with a seeded pure-Python or numpy noise (numpy ships with Pyodide).
- Async main loop (`asyncio`, `requestAnimationFrame`-driven ticks).
- `ui/web/`: character-grid renderer and keyboard input, loaded via Pyodide from a static page.
- Play mode only: bundled seeds + crystals, mock content. Ship to a `/fungi-fortress/` path on the site.
- Spike early (half a day, can run in parallel with Phase 0): confirm Pyodide loads the engine + Pydantic and measure load size and time.

**Phase 6: grow mode and DSPy (2 to 4 days)**
- `fungi grow`: DSPy-backed `Grower` produces a seed file. `fungi crystallize`: plays scripted encounters, stores scenes per band.
- Pin DSPy (Flex needs 3.3.0+). Start uncompiled and compare the three patterns. Add GEPA only with a metric.
- Publish a few grown worlds to the site so visitors see real generated content without any key.

**Phase 7: optional live calls in the browser (1 to 2 days)**
- Bring-your-own key: stored in `localStorage` only, sent straight to the provider via `fetch`, clear "this key never leaves your browser" copy, and a forget button. Only for providers whose APIs allow browser CORS (verify each; don't assume).
- Or a small rate-limited proxy (Cloudflare Worker) holding your key, with a daily budget cap. Needed for Jev in the browser unless System One allows browser CORS.

Total: roughly 2 weeks of focused work for everything. Phases 0 to 2 plus the Phase 5 spike is a realistic "next few days."

## PR #1 notes (merge it, then fix forward)

PR #1 is a real step toward this plan: `dwarf_mind.py`, the injectable Jev transport, seed validation with hard limits, fallbacks with no key, and 20 passing tests. Worth fixing (now or in Phase 2):

1. **A third LLM client.** `world_seed._chat` re-implements provider URLs next to `llm_interface.py`. Also, `urls.get(provider, urls["xai"])` after the membership check is dead fallback.
2. **Blocking calls.** World growth can block startup up to 2 x 45 s. Jev calls (2.5 s timeout) run inside the tick via `note_arrivals`, so a slow network freezes the UI. Several NPCs on one tick stack the delay.
3. **Unused Jev questions.** `_encounter_questions` asks `helpful` and `hostile` but only `stance` and `reveal_secret` are read. Drop them or use them; they can contradict `stance` and they cost tokens.
4. **Hard-to-read revelation logic.** In `consider_revelation`, `npc.amenable` is assigned, used by `_cap_offer`, then overwritten. At the Welcome band, Jev's `amenable` answer can't matter. A small table (band x offer -> outcome) would be clearer and testable. `REVEAL_YES` doubles as the amenable threshold; give it its own constant.
5. **Fail-open mission judge.** With no key or on any error, `judge_mission` returns accomplished. That's fine for playability, but say so in the UI, or the Jev verdict is decorative whenever the network hiccups.
6. **Judged before success.** `npc.judged = True` is set before the call, so a transient error locks the NPC to "wary" for the session. That's acceptable to save cost, but worth a one-line comment or a single retry.
7. **Dynamic attributes everywhere.** `getattr(npc, "data", None)`, `game: Any`, and attributes like `stance`, `judged_band`, `offer` added at runtime. This is what the typed `NPC` + result objects in Phase 2 fix.
8. **Per-tick A\*.** `dwarf_mind._reachable` runs A* for every idle dwarf x every pending task each tick, and retries unreachable tasks forever. Cache or rate-limit it before maps or task lists grow.
9. **`urllib` won't run in Pyodide.** That's another reason to put Jev behind the `Judge` port with a `fetch`-based browser transport (or the proxy).

## Key safety rules

- No keys in client code, seeds, crystals, logs, or the repo. Keep the existing key-scanning test and run it in CI.
- Play mode never reads `os.environ`. Only `content/` adapters do, and only in grow mode or the terminal.
- Logs redact Authorization headers and prompt fields marked secret.
- Flex/GEPA generated code runs only in DSPy's sandboxed interpreter, never `LocalInterpreter` with keys in reach (already in your notes).

## Testing

- Engine: unit tests plus a golden-run test (same seed + same command script -> same event log).
- Content: schema tests with good and bad fixtures; every port tested against `mock.py` and a fake transport (PR #1's pattern).
- Browser: one smoke test (Playwright) that loads the page, moves a dwarf, and saves/loads.
- Optional, nightly, keyed: a tiny live eval of Grower and Judge, never in PR CI.

## Open questions for Cameron

1. Is the TypeSafe SDK usable now, or stay on raw HTTP for a while?
2. Does System One allow browser CORS? That decides BYO-key vs proxy for Jev on the site.
3. Keep six providers, or narrow to xAI + one OpenAI-compatible fallback?
4. How much of the curses UI should survive vs a fresh web-first UI later?
5. What should a visitor experience in the first 60 seconds on the site? This shapes which grown worlds and crystals to ship.
