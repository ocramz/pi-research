# Stage A plan — energy-pricing-model: set-up and x01 draft

**Status (2026-09-26):** in progress.
- Step 1 is done: branch `exp/energy-pricing-model` was cut from main at ea9f687, and this plan was
  copied in.
- Next is step 2, the x01 draft. Nothing is registered.

## Context

The user asked for a new experiment, "energy-pricing-model", in which pi uses only the pi-notebook-py
and pi-web-search extensions. The repo has no problem directory yet. The experiment protocol
(`.claude/skills/experiment-protocol/SKILL.md`) needs a registered hypothesis before any code exists,
and the hypothesis is not decided yet. So this stage builds the scaffold and an unregistered PREREG
draft. The draft fixes everything the extension choice determines, and the user writes in the
science.

Found while exploring (read-only):
- `~/.pi/agent/settings.json` still lists pi-issue-tracker, pi-notebook-py and pi-web-search.
  `make pi-setup` only installs and never removes, so ea9f687 (AGENTS.md) and the Makefile's
  `EXTENSIONS` change left the issue tracker loading in every plain pi session.
- With `pi --no-extensions -e A -e B`, pi loads exactly A and B and ignores the packages in
  settings.json (pi 0.84.2, `dist/core/resource-loader.js`).
  - None of the three packages ships skills, prompts or themes.
  - Neither kept extension opens a UI dialog, so an automated session needs no `ui` answers.
- pi loads every `AGENTS.md`/`CLAUDE.md` from its cwd up to `/`. A session started inside this repo
  would read this repo's AGENTS.md and could read the PREREG. Its `git` commands would also act on
  this repo.
- pi-notebook-py saves notebooks to `<cwd>/.pi/notebooks/`, and its venvs to
  `~/.pi/notebook-py/venvs/`.
- For a local path, `pi remove` only drops the settings.json entry and deletes nothing on disk
  (`dist/core/package-manager.js`).

## Decisions (the user's, 2026-09-26)
- **Layout:** `energy-pricing-model/` is the problem. x01 gets its slug at registration.
  `writeup/` belongs to the user and is not created here.
- **x01 hypothesis:** not decided yet. The user writes it into the draft, and nothing is registered
  in this stage.
- **Scope:** stop once the draft is committed. No code and no paid sessions.
- **Extension set:** per-run flags (`--no-extensions` plus two `-e`), **and** remove pi-issue-tracker
  from `~/.pi/agent/settings.json`.
- **External look-ups by Claude: none.** The design uses only the repo and the user's input.
  `web_search_tavily` is part of the method under test, not a look-up by Claude.

## Steps
1. **Branch and plan copy.** `git switch -c exp/energy-pricing-model main` (main is clean at
   ea9f687). Copy this plan to `energy-pricing-model/plans/stage_a_plan.md` and set its Status.
   Commit: `plans: stage A plan (energy-pricing-model set-up; x01 draft)`.
2. **Write `energy-pricing-model/plans/x01_prereg_draft.md`**, following the PREREG skeleton. Its
   header reads "DRAFT — not registered". It becomes a registration only when it moves to
   `experiments/x01-<slug>/PREREG.md` and is committed on its own. Pre-filled:
   - **Method, pi launch.** This is the launcher: it is specified here, and becomes library code
     only after registration. Paths are absolute because pi resolves `-e` and `--session-dir`
     against its own cwd.
     ```bash
     set -a; . ./.env; set +a                             # at the repo root
     ID=$(date -u +%Y%m%dT%H%M%SZ)
     RUN=$PWD/energy-pricing-model/experiments/x01-<slug>/results/$ID
     WORK=$HOME/pi-work/energy-pricing-model/$ID          # fresh, outside the repo
     mkdir -p "$RUN" "$WORK"
     PATH=$PWD/.cache/python-shim:$PATH pi-agent-experiments/shared/with-versions.sh \
       python3 tools/pidrive.py serve "$RUN/pidrive" --cwd "$WORK" \
         --max-seconds 1800 --budget-usd 0.50 -- \
         --no-extensions \
         -e "$PWD/pi-agent-experiments/pi-notebook-py" \
         -e "$PWD/pi-agent-experiments/pi-web-search" \
         --no-skills --no-prompt-templates --no-context-files \
         --session-dir "$RUN/pidrive/sessions" &
     ```
     After the session, `$WORK/.pi/notebooks/*.py` is copied to `$RUN/notebooks/`.
   - **Method, pins.** Read from the repo:
     - pi 0.84.2;
     - `openrouter` / `deepseek/deepseek-v4-flash`, through `with-versions.sh`;
     - submodule cc9210a (pi-notebook-py 0.3.0, pi-web-search 0.1.0);
     - the Python 3.12 shim.

     The manifest records the superproject commit and `git_dirty`. `git_dirty` must be false,
     submodule included.
   - **C1, extension set.**
     - At start, `get_commands` lists `nb` and `nb-python` from pi-notebook-py.
     - It lists none of pi-issue-tracker's commands (`stories`, `plan-stories`, `start-epic`, …).
     - No tool is called outside pi's built-ins and `nb_cell`, `nb_run`, `nb_notebook`, `nb_env` and
       `web_search_tavily`.
     - If `web_search_tavily` is never called, its positive check is flagged as vacuous.
   - **C2, isolation.** After the session, the repo is unchanged outside `results/`. Any failure of
     C1 or C2 makes the run `invalid`.
   - **Outputs.** The protocol's `results/<run-id>/` files, plus `pidrive/` (events, transcript,
     stderr, sessions) and `notebooks/`. The writeup goes to
     `energy-pricing-model/writeup_generated/x01-<slug>.md`.
   - **Limitations.**
     - Search results change with the date.
     - pi has no sampling seed, so claims must be rates over N sessions.
     - The agent has bash. C2 catches writes to the repo, not reads outside `$WORK`.
     - OpenRouter may route the pinned model to different backends.
   - **Deviations:** none yet.
   - **Left as `TODO (user)`:**
     - the question and slug;
     - Why this design, and Definitions;
     - the verbatim task prompt and the follow-up policy;
     - the market, target, horizon and data window;
     - Hypotheses;
     - N sessions, per-session caps and the total budget;
     - the thinking level;
     - Outcome classes, with the `invalid` row pre-filled;
     - Predictions.
3. **Check the launch, with nothing to pay for.** Do this before step 4, while settings still list
   the tracker, so that what is tested is the flags.
   - Start `serve` into `<scratchpad>/launch-check/`, with a scratchpad workdir, once with the draft's
     pi args and once without them.
   - Run `tools/pidrive.py cmd … '{"type": "get_commands"}'`, then `stop`.
   - Expected with the flags: `nb` and `nb-python` present, no tracker commands, and no extension
     errors in `stderr.log`.
   - Expected without the flags: the tracker commands present. This shows the check can fail.
   - No prompt is sent, so nothing is spent on the model or on search.
4. **pi user settings.** This changes machine state and makes no commit.
   - Back up `~/.pi/agent/settings.json` to the scratchpad.
   - Run `pi remove /home/azureuser/pi-research/pi-agent-experiments/pi-issue-tracker`. It can be
     undone with `pi install` on the same path.
5. **Commit.** Update the Status block, then commit the draft and the plan together:
   `plans: x01 pre-registration draft (not registered); stage A status`. Stop and hand back.

**Commits:**
- They use the configured identity, `Marco Z <ocramz>` from `~/.gitconfig`, with no Claude
  attribution.
- Files are staged by name.
- Nothing is pushed.

## After the user completes the draft (not part of this stage)

**Registration:**
- `git mv` the draft to `experiments/x01-<slug>/PREREG.md` and set the Registered line.
- Commit it on its own: `prereg: x01-<slug> (<question>)`.

**Then:**
- Implementation, as protocol step 2:
  - the library in `experiments/lib/python/epmlib/`, holding the launcher, run directory, manifest
    and CLI;
  - tests in `experiments/tests/`;
  - `uv run pytest`.
- The run, the verdict and gate G1.

## Verification
- `git log --format='%h %an <%ae> %s' main..exp/energy-pricing-model` shows two commits by
  `Marco Z <ocramz>`.
- `git show --stat` lists only the named files.
- No commit message has a `Co-Authored-By` line.
- `git status --porcelain` is empty.
- Step 3's two `get_commands` results match what was expected.
- `pi list --no-approve` shows only pi-notebook-py and pi-web-search under User packages.

## Flagged, not changed
- AGENTS.md still says pi-setup "registers the three", and still describes pi-issue-tracker's
  per-turn story injection. Both are stale after step 4.
- `make pi-setup` never unregisters an extension dropped from `EXTENSIONS`, so this drift can recur on
  other machines. The per-run flags keep the experiment immune to it.
