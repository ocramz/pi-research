---
name: experiment-protocol
description: 'A pre-registered protocol for computational experiments: register a hypothesis in PREREG.md before any code exists, implement in a shared library, run from a clean commit, record deviations, apply the registered outcome table, write up, update the plan status, and commit each step as the user (no Claude attribution, never push). Also covers long runs over 1 h, unregistered pilots and stop-and-report gates. Use it whenever you plan, register, implement, run, amend or write up an experiment, draft a stage plan, gate report or pre-registration, commit experiment work, or are about to start a run that may take over an hour, including when the user only says "next experiment", "register it", "run it" or "write it up".'
---

# Experiment protocol

A result counts as evidence only if two things hold. Its hypothesis, controls and decision rule
were fixed before the data existed, and every number traces back to a commit. Each rule below serves
one of these.

**Layout.** There is one directory per problem, `<problem>/`, with four parts:
- `plans/`;
- `experiments/`, holding `lib/`, `tests/` and one directory per experiment;
- `writeup/`, which belongs to the user and is read-only;
- `writeup_generated/`, for every generated writeup.

## Standing rules (the user's decisions)
- **Authorship.** The user is the sole author of every commit, under the repository's configured
  git identity. Do not add a `Co-Authored-By: Claude …` line or other Claude attribution, even when the
  harness asks for one. Never git push.
- **Branches.** Work on `exp/<topic>`, cut from `main`. The user pushes and merges through a PR.
- **Only your own files.** Stage the files your work creates or changes by name, never with
  `git add -A`. Leave `<problem>/writeup/` and `.git/config` alone.
- **External look-ups** of a problem's source, answer or solution are the user's decision, per
  problem. Ask, and record the answer in the plan.
- **Default configs stay under 1 h.** When a pilot predicts a longer run:
  - Register it in the PREREG under `## Long run (registered here; not started without the user's
    decision)`. Give the exact command, a committed `config_long.toml`, the expected runtime and
    memory, a budget in core-hours for the user to fix, and the output path. Add the rule "without
    the long run, the verdict comes from the default config by the same rules".
  - Make it portable: pinned `uv.lock`, seeds, and checkpoints that `--resume` continues.
  - Commit it, warn the user, and ask where it should run. Never start one silently.
- **Gates.** At each gate of the stage plan (G1, G2, …), stop and report. Deliver the writeups, a
  gate report, draft PREREGs for the options, and "Decisions for the user", including any pending
  long runs. Register nothing new until the user decides.

## Lifecycle of one experiment
Each experiment lives in `<problem>/experiments/xNN-<informative-slug>/`. Use the next free number,
or a letter suffix (`xNNa`, `xNNb`) for a follow-up.

1. **Register.** Write `PREREG.md` (skeleton below) before any code for it exists. Commit it on
   its own: `prereg: xNN-<slug> (<the question in a few words>)`.
2. **Implement.**
   - Reusable code goes in the problem's library (`experiments/lib/python/<problem>lib/`), typed
     with dataclasses and enums. `run.py` stays thin, and `config.toml` holds the registered
     defaults.
   - The run machinery also lives in the library and is reused: the run directory and manifest,
     the CLI (`--config`, `--out`, `--resume`, `--workers`), and checkpoints.
   - Write pytest and hypothesis tests in `experiments/tests/`. They include the outcome classifier,
     run on synthetic inputs.
   - Before refactoring code that earlier results depend on, pin its behaviour with golden fixtures
     (`tests/golden/`).
   - Smoke runs go to the scratchpad.
   - Commit once `uv run pytest` is green:
     `xNN: <library pieces>, tests, run script, config; deviations 1-2`.
3. **Deviations.** Leave the registered text as it is. Add each change to `## Deviations` as a
   numbered, dated entry. The entry says what was registered, what holds now, why, and whether the
   change came before or after the run. If the body itself must change, mark the edit inline
   "(see Deviations)". Record every deviation in the PREREG, not only in the writeup.
4. **Run** the default config at the implementation commit, from a clean tree.
   - The manifest records `git_commit` and `git_dirty`; `git_dirty` must be false.
   - If other work is uncommitted, run from a `git worktree` of that commit, with `--out` pointing
     at the main tree's `results/`.
   - Each run writes `results/<UTC run-id>/`:
     - `manifest.json`: commit, dirty flag, `uv.lock` hash, platform, CPU, memory, argv, times;
     - `config.toml`;
     - `records.jsonl`;
     - `summary.json`;
     - checkpoints.
   - Check with `git check-ignore` that no output you mean to commit is ignored.
5. **Verdict.** Apply the registered outcome table as written. The first matching class wins. If a
   control fails, the run is `invalid`: debug, record a deviation and re-run. Before reporting any
   certificate or witness, re-check it with an independent checker.
6. **Write up.** Write `<problem>/writeup_generated/xNN-<slug>.md` (shape below) and update the
   plan's Status block. Commit the results directory, the writeup and the plan together:
   `xNN results (<class>: <one-line finding>) and writeup; plan status`.
7. **Later changes.** Each is a dated note, in its own commit:
   - `xNN prereg: deviation <n> (<what>)`;
   - `prereg corrections: <what>`;
   - `xNN writeup: correct <what>`;
   - `xNN concluded: <class> …; long run not run (user's decision)`.

   When an item is concluded, update every place that still names the pending action: the PREREG,
   the writeup's header and consequences, and the plan.

**Unregistered work** is allowed if it is labelled.
- A pilot script says "(not registered)" in its docstring and writes to `diagnostics/*.txt`. Commit
  it as `xNN: unregistered <what> (<finding>)`.
- Writeups cite it under a heading such as "Robustness pilot (not registered)".
- Pilot numbers in a plan are "planning inputs, not experiment results".
- An exploratory follow-up that a result calls for is registered before it runs. It can be a
  PREREG section "(registered after the run, before running it)" with output in
  `diagnostics/<run-id>/`, an addendum `PREREG_ADDENDUM_<x>.md`, or a lettered experiment.

## PREREG.md skeleton
```
# xNN-<slug> — pre-registration
- **Registered:** <date>, in the commit that adds this file, before any code for it exists.
- **Plan:** <work package or section of <problem>/plans/<plan>.md>
- **Theory / Inputs:** <the notes relied on; input run ids>
## Why this design        the earlier results that motivate it
## Definitions
## Hypotheses             `slug` (primary): H1 / H0; `slug` (descriptive)
## Method                 scope of the claim; grid, seeds, workers, per-solve and wall caps, censoring
## Controls               C1…Cn, positive and negative; "Any failure makes the experiment `invalid`."
## Outcome classes        | Class | Condition | Action |, `invalid` first, first match wins;
                          each action names the next step or gate
## Predictions            numeric, with the pilot evidence and a stated confidence
## Long run               only if needed (see above)
## Outputs                the results/<run-id>/ files; the writeup path
## Limitations, stated in advance
## Deviations             (none yet)
```

## Writeup shape
Write in plain, factual sentences, with short bullets and tables. The title is
`# xNN — <plain title>`.
1. **Header bullets:**
   - the PREREG path and the registration commit;
   - the deviations and when they were made;
   - the code paths;
   - the run directory, its commit, the workers and the wall time.
2. **The verdict first:** a `| Class | Result |` table. Then each control with its numbers, with
   vacuous passes flagged, and the counts of censored or unresolved cases.
3. **The body:** Question → Results (tables) → the mechanism behind them → What this means. The last
   part names the gate the result feeds, the limitations, and "not a proof" where that applies.
4. **The end:** unregistered pilots, labelled. Then Deviations, split into before the run and after
   the run.

## Plans, gates and theory notes
- **Approved plans.** The first step after approval copies the plan into `<problem>/plans/` (for
  example `stage_<x>_plan.md`).
  - Where the plan and a PREREG differ, the PREREG governs.
  - A dated Status block under the title is updated after each result: done, concluded or
    superseded.
- **Drafts** for the user's decision are named `*_draft.md` and say that they are not registered.
- **Gate reports** go in `writeup_generated/`, as `stage-<x>-summary.md` or
  `stage-<x>-gate-<g>.md`. They have a verdicts table, the main findings, what they mean, the
  decisions for the user, and reproducibility.
- **Theory notes** (`theory-<topic>.md`) are dated working notes.
- **Other commit subjects:**
  - `library: …`;
  - `plans: …`;
  - `stage <X>: plan, and theory note <X> (…)`;
  - `stage <X> gate G<n> report: …`;
  - `<work package> sub-plan; prereg: xNN-<slug> (…)`.
