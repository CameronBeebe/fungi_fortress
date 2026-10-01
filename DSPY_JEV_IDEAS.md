# DSPy and Jev ideas

Notes, not a spec. The June 2025 DSPy-centric stack (`DSPY_LLM_STACK.md`) does not match the game. This replaces it.

Last revised: 2026-10-01.

## What the game does now

The simulation stays deterministic. A player order (`m`, `b`, and the rest) goes to the nearest idle dwarf that can reach it. Jev is not on that path.

Jev is an observer. It is called over HTTPS with the standard library (`jev_client.py`), model `jev-latest`. Two judgments exist:

- A meeting with a seeded character, once. Stance is help, wary, or hostile. A secret is shown only when the stance is help and the reveal score is high enough.
- A written mission `success` sentence, once, after the countable requirements are already met. Collect and reach stay in code.

World growth at launch fills a seed: characters, places, and quests. The first quest becomes the mission. If the model returns nothing usable, `seeds/example_world.json` is installed. Keys come from the environment. DSPy and the TypeSafe SDK are intentionally not dependencies. An unpinned extra would float `typesafe-sdk`.

Spice is both a commodity and a sense organ. `spice.py` bands the dose: under 55 is a glimpse, 55 is a voice, 65 is a welcome. Starting exposure is 50. One magic fungus is worth 5. Kin stay themselves at every dose. A revealed figure resolves as the dose rises, and is judged once per band. The built Nexus is a stair into one grown depth (`seeds/example_depth.json`), a higher grade of the same substance. Press `e` again to climb back. The surface mission is held aside and restored.

People are not tiles. The sidebar looks up whoever is standing on the cursor. A revealed figure at a glimpse stays "a shimmer" and does not print their name.

## What Flex is

`dspy.Flex` arrived in DSPy 3.3.0 and is still marked experimental. Docs: https://dspy.ai/current/api/modules/Flex/ and https://dspy.ai/current/diving-deeper/flex/

A Flex is a module whose source, `module_src`, is the thing an optimizer may rewrite. You construct it from a signature. Until `dspy.GEPA` compiles it, it is one `Predict`, or one `RLM` if you passed tools. GEPA can then change the number of predictors, which of `Predict`, `ChainOfThought`, `ReAct`, `ReActV2`, or `RLM` they are, and which steps are plain Python. A candidate that does not parse or crashes is scored as a failure. The search continues.

Generated source does not run in the game process. The default interpreter is `dspy.PythonInterpreter` (Deno and Pyodide), with no filesystem and no network. Only predictor calls and tools you passed bridge back to the host, where the real model call happens. `max_predictor_calls` defaults to 100. `LocalInterpreter` keeps the host filesystem, credentials, and network, and is not a security sandbox. Deno must be installed or the default call raises. Saved state is the source string plus any LM set on the module.

The sandbox `dspy` is a shim. It can build those five predictor types, a string signature, and a `Prediction`. It cannot see `dspy.LM`, `configure`, optimizers, adapters, or another Flex. TypeSafe and Jev are not in that catalog. A host tool could call `jev_client`. The generated code cannot open a socket on its own.

Flex returns the fields you declared. It is a search for a cheaper or more accurate way to fill them, measured on a train set and a val set. It does not patch `game_logic.py`.

## Generative scenes, in baby steps

Flex can play a moment if the moment is a signature and the game already understands the verbs.

A moment is a record supplied by the seed, not a hardcoded person: who is standing there, kin or revealed, the dose band, the tile, and whether a pulse just passed. The output is a small scene (a few lines of characters) and a caption. Glimpse does not print the figure's name. Voice may print the name and the motive. Welcome may print the secret. Kin do not dissolve when the dose changes.

Three patterns are worth printing side by side before any compile:

1. Python draws the frame from the dose. No model.
2. One uncompiled Flex draws the whole picture. That is a single `Predict`.
3. Python chooses the frame. Flex writes only the caption.

Score the page on shape, on whether a low dose leaks a name or a secret, and on how many model calls `program_trace` shows. If the single call already obeys the bands, GEPA is unnecessary. If it leaks, the metric text can say so, and a later compile is allowed to move the band check into Python.

That toy stays beside the tick loop. It does not belong in `requirements.txt` until a DSPy version is pinned.

## Crystal pipes

Re-encounter is what hardens a generative thing.

The first time a dwarf meets a revealed figure in a given band, the program draws the scene and the game keeps it, keyed by that figure's id, the place, and the band. The same meeting in the same band shows the stored picture. A different dose is a different key, so it draws again and then hardens on its own.

That stored scene is memory. The second crystal is the program. Once a bucket of the same kind has been re-encountered, a pipe can hand the bucket to GEPA. The metric is: reproduce the scenes already shown, and spend fewer model calls. If the compiled `module_src` does that, it replaces the live drawer for that kind of meeting. A brand-new kind is still generative the first time.

Nothing in the pipe is named after the prepared grove. The seed supplies the person. The band supplies the slot.

## What stays out for now

- Jev on player orders.
- DSPy or the TypeSafe SDK as a runtime dependency.
- Flex inside a tick, or `LocalInterpreter` with API keys in reach.
- A Game Boy / Chromatic port. Live HTTP does not run on a cartridge. A later ROM would export one grown seed and the lines already crystallized for each band. The terminal remains the place a world is grown and judged.
