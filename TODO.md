# Fungi Fortress: TODO

Living backlog. One small PR per item unless noted. Order is the proposed build order.

## Up next (in order)

1. **Bridge queue and wood.** Wood is only checked when a segment finishes (`game_logic._complete_build_bridge`). Reserve wood at queue time (count wood committed to queued bridges, refuse unaffordable segments). If a segment still fails, cancel the segments that depended on it and say so on screen.
2. **Step 2: one LLM client.** One OpenAI-compatible client replacing the three provider paths, mock provider as default with no key, typed errors, one prompt builder for streaming and non-streaming. Replace the 9 xfail Oracle tests.
3. **Every NPC is an LLM character.** Generalize the Oracle dialogue window to all characters. Each character gets a persona (voice, style, motive, secret, knowledge, relationships) from the seed. Jev's stance decides what they'll disclose, the LLM speaks it, conversation memory per NPC, streaming, mock fallback. Today `t` on an NPC only asks Jev once and prints canned seed lines to the debug log.
4. **Step 3: typed generative content.** Pydantic schemas for everything generated: WorldSeed, Character, Place, Quest, Item, plus result types Encounter, Revelation, MissionVerdict. Judgments become DSPy signatures on Jev (`dspy[typesafe]==3.4.0`, optional extra). Same signatures fall back to a generative model or the mock.
5. **Quests.** Only `seed.quests[0]` is ever used, and after completing it the mission becomes `{}`, so there's no way to get another. Add quest-giving from NPCs (through the dialogue in item 3), multiple quests per seed, a quest log, and generated quests that follow the schema.

## Gameplay and design

- **Stance is frozen.** An NPC's stance is judged once (`npc.judged = True` before the call) and never revisited, and kin stance ignores spore exposure. Re-judge on meaningful change (band, gifts, quest progress) and retry transient errors.
- **Collision.** Pathfinding ignores characters, and the stacking code teleports the displaced one to a neighbor. Decide on real blocking, swapping places, or NPCs stepping aside on their own.
- **Revealed figures are hard to find.** Reveal Mycelium only lights the network, it doesn't reveal people. The seed's one revealed figure is always on the map and drawn as `?` below 55 exposure, `~` at 55 to 64, its initial at 65+. Make the spell actually surface figures and explain the bands in the UI.
- **Debug/"show stats" toggle (F1).** Hide backend readouts (exposure numbers, bands, stances, debug messages) in normal play; F1 toggles them for development.
- **Perception overlay prototype.** As exposure rises, draw an overlay with true and false elements over the map (see PLANNING.md "Reality model: one core, many views" and "Spore exposure and perception" sections for the architectural model; still under discussion).
- **Fail-open mission judge.** With no key or on error the mission counts as accomplished. Show that in the UI.

## Engineering

- Step 4: non-blocking model calls (world growth and Jev currently block, Jev inside the tick).
- Step 5: engine/UI split, save/load, grow mode with DSPy.
- Separate player-facing messages from debug messages (many `add_debug_message` calls are still on screen).
- PR #1 leftovers: unused Jev questions `helpful` and `hostile`, revelation logic as a band x offer table, own constant instead of reusing `REVEAL_YES`, cache per-tick A* in `dwarf_mind._reachable`.
- Housekeeping: drop `requirements.txt` and `pytest.ini` now that `pyproject.toml` covers them, retire `verify_llm_setup.py` and `SETUP_LLM.md` after step 2, delete stale local `fungi_fortress/logs/`.

## Later

- Browser play via Pyodide (replace `noise`, async loop, web renderer), then optional live calls (BYO key or a small proxy).
- Ship grown worlds on cameronbeebe.github.io.

## Done

- PR #1: seeded world, Jev kept off player orders.
- PR #2: package layout, `fungi` command, uv + `uv.lock`, CI on 3.10-3.12, logs in `./logs/`, crash log + pre-crash snapshot, fixes for the entity-stacking crash and the bridge crash.
