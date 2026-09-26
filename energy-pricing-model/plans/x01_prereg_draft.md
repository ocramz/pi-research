# x01-`<slug>` — pre-registration (DRAFT, not registered)

> **Superseded 2026-09-26, and never registered.**
> - Stage B (`stage_b_plan.md`) carries this draft's pi launch and its C1 and C2 controls into
>   `experiments/x06-open-data-access/PREREG.md`.
> - The number x01 now belongs to `x01-lp-shadow-prices`.

> **DRAFT, not registered.** This file is for the user's decision. It becomes the x01 registration
> only when all of the following hold:
> - it has moved to `energy-pricing-model/experiments/x01-<slug>/PREREG.md`;
> - its `TODO (user)` items are resolved;
> - it is committed on its own, as `prereg: x01-<slug> (<question>)`.
>
> Until then, no code for x01 may be written.

- **Registered:** not yet. It will be registered on the date of the commit that adds
  `experiments/x01-<slug>/PREREG.md`, before any code for it exists.
- **Plan:** `energy-pricing-model/plans/stage_a_plan.md`, stage A, x01.
- **Theory / Inputs:** none. This is the problem's first experiment, and there are no earlier runs.

## Why this design
TODO (user): the question x01 answers, and why it comes first.

Stage A already fixes one thing: pi runs with exactly two extensions, pi-notebook-py and
pi-web-search (the user's decision, 2026-09-26).

## Definitions
- **Session:** one `pi --mode rpc` process, started by the launch command in Method. It runs from
  `serve` until pi exits.
- **Extension tools:**
  - `nb_cell`, `nb_run`, `nb_notebook` and `nb_env`, from pi-notebook-py 0.3.0;
  - `web_search_tavily`, from pi-web-search 0.1.0.
- **Allowed tools:** pi's built-in tools and the extension tools.
- TODO (user): the task's terms. These are the market, the price series, the target and horizon,
  what counts as a finished session, and the score.

## Hypotheses
- TODO (user): `<slug>` (primary): H1 / H0.
- TODO (user): `<slug>` (descriptive), if there is one.

## Method
**Scope of the claim.** TODO (user). Whatever the claim is, it holds only for:
- the pinned model, pi version and extension versions below;
- search results as of the run dates.

**Task.** TODO (user):
- the verbatim prompt sent with `tools/pidrive.py send`;
- the follow-up policy, for example one prompt and no follow-ups, or a fixed list;
- the market, target, horizon and data window;
- the files the session must leave in its workdir.

**Sessions.** TODO (user):
- N, the number of sessions.
- The per-session caps, `--max-seconds` and `--budget-usd`. The command below uses pidrive's
  defaults, 1800 s and $0.50, as placeholders.
- The total budget.
- The thinking level. Unless it is set, pi's default applies, and it is recorded from `get_state`.
- How sessions stopped by a cap are counted. They are censored, not failed.

The default config stays under 1 h in total. If N times the per-session cap is more than that, the
PREREG needs a `## Long run` section.

**pi launch.** Run from the repo root, with nothing uncommitted:

```bash
set -a; . ./.env; set +a                             # OPENROUTER_API_KEY, TAVILY_API_KEY
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

- `--no-extensions` drops every package listed in `~/.pi/agent/settings.json`, which leaves the two
  `-e` paths as the only extensions. This holds on any machine, including one whose settings still
  list pi-issue-tracker.
- `--no-skills`, `--no-prompt-templates` and `--no-context-files` stop pi loading anything else it
  would discover. No AGENTS.md or CLAUDE.md reaches the session.
- The workdir is outside the repo. The agent's file edits and `git` commands therefore cannot touch
  the research repo, and this PREREG is not in the agent's tree.
- The paths are absolute because pi resolves `-e` and `--session-dir` against its own cwd.
- pi-notebook-py needs Python 3.12 or later. The shim puts uv's 3.12 first on PATH.
- After the session, the following are copied into `$RUN/`:
  - `$WORK/.pi/notebooks/*.py`, into `notebooks/`;
  - the task's output files, into `workdir/`. TODO (user): which files.

**Pins**, as of 2026-09-26. The manifest records the values in force at run time.
- pi 0.84.2 (`DEFAULT_PI_VERSION`).
- Provider `openrouter` and model `deepseek/deepseek-v4-flash`. These are `DEFAULT_PI_PROVIDER` and
  `DEFAULT_PI_MODEL` in `pi-agent-experiments/shared/versions.env`, supplied by `with-versions.sh`.
- The submodule `pi-agent-experiments` at cc9210a, which gives pi-notebook-py 0.3.0 and
  pi-web-search 0.1.0.
- Python 3.12, through `.cache/python-shim`.

The manifest also records the superproject commit and `git_dirty`. `git_dirty` must be false, and
the submodule must be clean at its recorded commit.

## Controls
- **C1, extension set.**
  - Positive: at the start of the session, `get_commands` lists exactly `llama`, `nb` and
    `nb-python`.
    - `nb` and `nb-python` come from pi-notebook-py.
    - `llama` comes from an extension bundled with pi 0.84.2 (`dist/extensions/llama/`). It
      registers a provider and this one command, and no tools.
    - The check goes by name, because pi reports no `path` for extension commands.
  - Negative: none of pi-issue-tracker's 11 commands appears (`stories`, `plan-stories`,
    `start-epic`, …), and `$WORK/.pi/stories.db` does not exist after the session.
  - `stderr.log` shows no error from loading an extension.
  - Every tool call in `events.jsonl` is to an allowed tool.
  - If a session never calls `web_search_tavily`, its positive check is vacuous and is flagged.
  - Stage A ran this check on 2026-09-26. It cost $0, because no prompt was sent. Settings still
    listed pi-issue-tracker at the time.
    - With the flags, the list was exactly the three commands above, and the workdir stayed empty.
    - Without the flags, the tracker's 11 commands appeared as well, and the tracker wrote
      `.pi/stories.db` into the workdir. So the check can fail.
- **C2, isolation.** After the session, `git status --porcelain` shows no change outside `$RUN`.
- TODO (user): the task's own controls, positive and negative.

Any failure makes the experiment `invalid`.

## Outcome classes
The first matching class wins.

| Class | Condition | Action |
|---|---|---|
| `invalid` | any control fails | debug, record a deviation, re-run |
| TODO (user) | … | … |

## Predictions
TODO (user): numeric predictions, each with a stated confidence. There is no pilot evidence yet.

## Outputs
Each run writes `energy-pricing-model/experiments/x01-<slug>/results/<UTC run-id>/`:
- `manifest.json`: the protocol's fields, plus the pi version, the provider and model, and the
  submodule commit;
- `config.toml`;
- `records.jsonl`, with one record per session;
- `summary.json`;
- checkpoints;
- `pidrive/`, holding `events.jsonl`, `transcript.log`, `stderr.log` and `sessions/`;
- `notebooks/`, holding the session's `.pi/notebooks/*.py`.

The writeup goes to `energy-pricing-model/writeup_generated/x01-<slug>.md`.

## Limitations, stated in advance
- Web search results change with the date, so a re-run on another day sees different pages. Every
  query and every returned URL is kept in `events.jsonl`.
- pi exposes no sampling seed, so sessions do not repeat token for token. Claims are rates over N
  sessions.
- OpenRouter may serve the pinned model from different backends.
- The agent has bash. C2 catches writes into the repo, but not reads outside `$WORK`.
- The results hold for one model, one pi version and one version of each extension, and are not
  claimed to generalise beyond them.

## Deviations
(none yet)
