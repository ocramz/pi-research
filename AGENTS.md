# pi-research

Experiments follow the experiment-protocol skill
(.claude/skills/experiment-protocol/SKILL.md).

## Default pi extensions

New experiments run pi with these extensions :

- **pi-notebook-py**: Python notebooks. Saved notebooks go to `.pi/notebooks/*.py`; commit them.
- **pi-web-search**: `web_search_tavily`; needs `TAVILY_API_KEY` at call time.

Set up once per machine with `make pi-setup`. It installs the pinned pi and registers the three as
submodule paths in `~/.pi/agent/settings.json`, and it is safe to re-run. `pi list` shows the result.

- Keep them in user settings, not `.pi/settings.json`: pi reads project settings from the cwd only,
  and `pi -p` skips untrusted ones silently.
- pi loads the submodule checkout. Don't edit the submodule while an experiment runs.
- An experiment that departs from this set says so in its PREREG's Method (`--no-extensions`, `-e`).
- pi reads API keys from the environment, not `.env`. Run `set -a; . ./.env; set +a` first
  (`OPENROUTER_API_KEY`, `TAVILY_API_KEY`). Never print `.env`.

## Driving a pi session

`tools/pidrive.py` holds one `pi --mode rpc` in the background (`serve`) and drives it from separate
shell calls. `send` a prompt and get the turn back summarised with the session cost, answer extension
dialogs with `ui`, and `wait`, `cmd` (any RPC command) or `stop`. Usage is in its docstring.

- Start `serve` under `pi-agent-experiments/shared/with-versions.sh`, which supplies the pinned model,
  with `.cache/python-shim` first on PATH: pi-notebook-py needs Python 3.12.
- `serve` stops pi after `--max-seconds` (1800) and once the session costs over `--budget-usd` (0.50).
- pi-issue-tracker injects story context into every turn, so the agent may work open stories as well
  as the prompt.
- Offline tests: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools`.
