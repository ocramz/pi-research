# x06-open-data-access — pre-registration

- **Registered:** 2026-09-26, in the commit that adds this file, before any code for it exists.
- **Plan:** `energy-pricing-model/plans/stage_b_plan.md`, the x06 entry.
- **Theory / Inputs:**
  - `plans/theory-rosso-claims.md`, claim 45;
  - the companion note `docs/tem-open-pricing-datasets-v2.md` §6.1 and the note §8, both committed
    in b9291cd;
  - `plans/x01_prereg_draft.md` (superseded), whose pi launch and C1/C2 controls are carried here;
  - the stage A launch checks, and the x06 launch check of 2026-09-26. These are unregistered, cost
    $0 and are planning inputs, not results.
  - There are no input runs.

## Why this design
The note's §8 and the companion note's §6.1 say a set of Tier-1 GB datasets is open. They are
accessible without a key, at half-hourly or hourly resolution, with stated coverage. The whole
"reference model from open data" argument rests on this.

These claims can only be checked on the web. The user decided that Claude makes no external
look-ups for this problem. So the instrument is the pi agent, with only pi-notebook-py and
pi-web-search, and Claude judges only from the evidence the run saves.

Verdicts never rest on the agent's own reports:
- every download goes through a registered script that saves the raw response;
- a checker applies registered rules to those files;
- two local feeds give a positive and a negative control on the instrument itself.

## Definitions
- **Datasets under test:**

  | id | Claim (companion §6.1) | Host suffix | Identity rule | Step (min) | Target date (UTC) | Minimum distinct times |
  |---|---|---|---|---|---|---|
  | elexon | Elexon Insights, half-hourly; "All our APIs are public and no API key is required" | elexon.co.uk | none | 30 | 2026-03-10 | 46 |
  | neso-demand | NESO Historic Demand Data or Demand Data Update, half-hourly; CKAN API | neso.energy | the URL or a field name contains "demand" | 30 | 2026-03-10 | 46 |
  | neso-ews | NESO embedded wind and solar forecasts, half-hourly, with archives | neso.energy | the URL or a field name contains "forecast" | 30 | 2026-03-10 | 46 |
  | pvlive | PV_Live, half-hourly; "open and free to access" | sheffield.ac.uk | none | 30 | 2026-03-10 | 46 |
  | om-era5 | Open-Meteo ERA5, hourly; "no authentication" | open-meteo.com | the URL does not contain "forecast" | 60 | 2026-03-10 | 23 |
  | om-hfc | Open-Meteo historical-forecast archive "from 2021" | open-meteo.com | the URL contains "forecast" | 60 | 2021-12-15 | 23 |

  - Excluded from Tier 1: the TNUoS tariffs and the DUoS/CDCM statements. They are not time series
    with an access claim for an API.
  - Neither target date falls near a DST change.
- **Local controls**, served by the harness on 127.0.0.1, with a random port and a random token per
  session:
  - feed-a answers 200 with a CSV `time,value` of 48 half-hourly rows for 2026-03-10 and random
    values. Its sha256 is recorded.
  - feed-b answers 401 with `WWW-Authenticate: Bearer realm="feed-b"` and the JSON body
    `{"error": "API key required"}`.
- **Witness.** For session s, dataset d and attempt n, a witness needs all of the following:
  1. A bash tool result in s's `events.jsonl` contains the curl write-out JSON whose
     `filename_effective` equals `evidence/d/n.body`.
  2. `fetch.sh` is unchanged after the session.
  3. `http_code` is 200 and `exitcode` is 0.
  4. The host of the requested URL (`evidence/d/n.url`) ends with d's host suffix.
  5. There are no credentials: the URL has no userinfo, and no query parameter whose name matches
     `(?i)key|token|auth|password|secret|signature`.
  6. The size of the body equals `size_download`.
  7. After any gzip or zip wrapper is removed, the body parses as CSV or JSON. It must hold at least
     the minimum number of distinct times on the target date, with a modal step equal to d's step.
  8. d's identity rule holds.
- **Refutation of "no key".** Items 1, 2, 4 and 5 hold, and all of the following:
  - the HTTP status is 401 or 403;
  - there is a `WWW-Authenticate` header, or the body matches
    `(?i)api[ _-]?key|subscription[ _-]?key|access[ _-]?token|unauthori[sz]ed|log ?in|sign ?in|regist`;
  - the response is not a WAF block: no `cf-mitigated` header, and a body that does not match
    `(?i)captcha|just a moment|attention required|access denied`.
- **Refutation of coverage** (om-hfc only). The status is 400, 404 or 422 on a URL that requests
  2021-12-15, and the body matches `(?i)(out of|outside).{0,40}(range|allowed)|not available|no data`.
- **Dataset verdict.**
  - **Accessible as claimed:** at least one witness in any session.
  - **Not as claimed:** no witness, and a refutation in at least 2 sessions that passed C3 and C4.
  - **Inconclusive:** otherwise.
- **Manual review.** A 200 body from a registered host that the parser cannot read is reviewed by
  hand against items 1–8, from the saved files only. Each such decision is listed separately in the
  writeup. Nothing is ever fetched again.

## Hypotheses
- **`access-claims` (primary).**
  - H1 (the notes): all six datasets are accessible as claimed.
  - H0: at least one is not accessible as claimed.
  - The outcome table grades the result.
- **Descriptive:**
  - `agent-accuracy`: the agent's reported outcome against the checker's verdict, for each session
    and dataset;
  - `cost`: session cost, tool calls, searches, follow-ups, wall time, and C1 passes that are vacuous
    because no search was made.

## Method
**Scope of the claim.**
- Access without a key, as observed from this VM's network on the run date.
- Only for the endpoints the agent found, and within this budget.
- Coverage is tested only through the target dates.

**The pi launch, per session.**
- **Working directories:** `~/pi-work/energy-pricing-model/x06/<run-id>/sNN/{work,drive,nbhome,tmp}`,
  outside the repo.
- **Launch command:**
  `<main>/pi-agent-experiments/shared/with-versions.sh python3 <code>/tools/pidrive.py serve <drive>
  --cwd <work> --max-seconds 1200 --budget-usd 0.30 -- --no-extensions -e
  <main>/pi-agent-experiments/pi-notebook-py -e <main>/pi-agent-experiments/pi-web-search --no-skills
  --no-prompt-templates --no-context-files --thinking high --session-dir <drive>/sessions`
  - `<code>` is the clean worktree of the implementation commit.
  - `<main>` is the main tree. Its submodule must match the gitlink at `<code>` and be clean.
- **The environment is an allowlist, and nothing else is passed on:**
  - `HOME`, `USER`, `LOGNAME`;
  - `SHELL=/bin/bash`, `LANG=C.UTF-8`, `TZ=UTC`, `TMPDIR=<sNN/tmp>`;
  - `PATH=<main>/.cache/python-shim:~/.local/bin:/usr/local/bin:/usr/bin:/bin`;
  - `OPENROUTER_API_KEY` and `TAVILY_API_KEY`, from `.env`;
  - `PI_NOTEBOOK_HOME=<sNN/nbhome>` and `PI_SKIP_VERSION_CHECK=1`.

  `VIRTUAL_ENV`, `PI_MODEL`, `PI_PROVIDER`, `PI_PYTHON` and `PYTHONPATH` are never passed.
  `with-versions.sh` supplies the pinned provider and model:
  `openrouter` / `deepseek/deepseek-v4-flash`, from `versions.env` at cc9210a.
- **Pins:** pi 0.84.2, pi-notebook-py 0.3.0, pi-web-search 0.1.0, and the Python 3.12 shim.
- **Session procedure:**
  1. Install `fetch.sh` with mode 0755 in `work/`, and render `prompt.txt`, filling in `${port}`,
     `${token_a}` and `${token_b}`.
  2. Start `serve`.
  3. Send `get_commands`, `get_state` and `get_available_thinking_levels`, and save them. Pre-check
     C1. If the pre-check fails, stop and start no further sessions. Nothing has been spent at that
     point.
  4. Send the prompt, with a timeout of 1,230 s.
     - On a dialog, answer `ui --cancel`.
     - A monitor aborts the session after its 12th `web_search_tavily` call.
  5. If `evidence.json` is missing or invalid while pi is alive, send the registered follow-up
     once.
  6. Send `get_session_stats`, then stop pi, and kill the process group.
  7. Copy the artefacts to `results/<run-id>/sessions/sNN/`. Redact every occurrence of either API
     key. Gzip `events.jsonl` and the session JSONL. Run the checker and the audit. Delete the
     notebook venvs.
- **Sessions:** N = 6, 3 at a time, started 20 s apart.
  - Caps per session: 1,200 s and $0.30.
  - At most 10 searches are allowed by the prompt; the hard cap is 12.
  - 6 attempts per source; at most 1 follow-up.
  - Worst case: $1.80 on the model and 72 Tavily calls, with about 2,600 s of wall time.
  - A session stopped by a cap is censored, but its witnesses count.

**Registered config** (`config.toml` must equal this):

<!-- registered config: config.toml -->
```toml
[experiment]
name = "x06-open-data-access"
seed = 20260926

[pi]
pi_version = "0.84.2"
thinking = "high"
expected_commands = ["llama", "nb", "nb-python"]
notebook_commands = ["nb", "nb-python"]
allowed_tools = ["read", "bash", "edit", "write", "grep", "find", "ls", "nb_cell", "nb_run", "nb_notebook", "nb_env", "web_search_tavily"]
workdir_root = "~/pi-work/energy-pricing-model/x06"

[sessions]
count = 6
concurrent = 3
stagger_s = 20
max_seconds = 1200
budget_usd = 0.30
search_limit_prompt = 10
search_hard_cap = 12
attempts_per_source = 6
max_followups = 1
min_valid_sessions = 4
refutation_sessions = 2

[controls]
feed_rows = 48
feed_date = "2026-03-10"

[[datasets]]
id = "elexon"
host_suffix = "elexon.co.uk"
identity = "none"
step_minutes = 30
target_date = "2026-03-10"
min_distinct_times = 46

[[datasets]]
id = "neso-demand"
host_suffix = "neso.energy"
identity = "url_or_field_contains:demand"
step_minutes = 30
target_date = "2026-03-10"
min_distinct_times = 46

[[datasets]]
id = "neso-ews"
host_suffix = "neso.energy"
identity = "url_or_field_contains:forecast"
step_minutes = 30
target_date = "2026-03-10"
min_distinct_times = 46

[[datasets]]
id = "pvlive"
host_suffix = "sheffield.ac.uk"
identity = "none"
step_minutes = 30
target_date = "2026-03-10"
min_distinct_times = 46

[[datasets]]
id = "om-era5"
host_suffix = "open-meteo.com"
identity = "url_excludes:forecast"
step_minutes = 60
target_date = "2026-03-10"
min_distinct_times = 23

[[datasets]]
id = "om-hfc"
host_suffix = "open-meteo.com"
identity = "url_contains:forecast"
step_minutes = 60
target_date = "2021-12-15"
min_distinct_times = 23

[run]
workers = 3
wall_cap_s = 3300
```

**Registered `fetch.sh`** (installed verbatim):

<!-- registered file: fetch.sh -->
```sh
#!/bin/sh
# ./fetch.sh SOURCE_ID URL -- one unauthenticated GET, saved as evidence. Do not edit this file.
set -eu
[ "$#" -eq 2 ] || { echo "usage: ./fetch.sh SOURCE_ID URL" >&2; exit 2; }
id=$1
url=$2
case $id in ''|*/*|.*) echo "fetch.sh: bad SOURCE_ID" >&2; exit 2 ;; esac
dir=evidence/$id
mkdir -p "$dir"
n=1
while [ -e "$dir/$n.body" ]; do n=$((n + 1)); done
if [ "$n" -gt 6 ]; then echo "fetch.sh: $id already has 6 attempts" >&2; exit 3; fi
: > "$dir/$n.body"
printf '%s\n' "$url" > "$dir/$n.url"
curl -q -sS -L --proto '=http,https' --max-time 60 --max-filesize 50000000 \
  -o "$dir/$n.body" -D "$dir/$n.headers" -w '%{json}\n' --url "$url" | tee "$dir/$n.curl.json"
echo "fetch.sh: attempt $n for $id saved in $dir/"
```

**Registered prompt** (`prompt.txt`, sent verbatim once the placeholders are filled):

<!-- registered file: prompt.txt -->
```text
You are checking whether public electricity and weather data sources can be downloaded without an API key.
Work only in the current directory, and do not ask me questions: decide and carry on.

Rules
- Never use an API key, token, password, login or cookie for these sources, even if a source asks for one.
  If a source needs one, record that and move on.
- Download only with the script in this directory, which saves each response as evidence:
      ./fetch.sh SOURCE_ID 'URL'
  It allows 6 attempts per source and saves them in evidence/SOURCE_ID/. Do not edit fetch.sh or evidence/.
- Ask each source for a small sample: one day, if the source lets you choose dates.
- You may use web_search_tavily (at most 10 searches in all) and the notebook tools, to find the right
  URL and to inspect what you downloaded.

Target date: 2026-03-10, in UTC, for every source except om-hfc, whose target date is 2021-12-15.
For the Open-Meteo sources use latitude 51.51, longitude -0.13 and the variable temperature_2m.

Sources (id: name. What it is said to provide. Where it is said to be.)
1. elexon: Elexon Insights Solution. Half-hourly system and imbalance prices, Market Index Price,
   generation by fuel type, demand outturn. https://developer.data.elexon.co.uk/ ("All our APIs are
   public and no API key is required"). Any one half-hourly series will do.
2. neso-demand: NESO Data Portal, Historic Demand Data or Demand Data Update. Half-hourly demand,
   interconnector, wind and solar outturn from 2001. https://www.neso.energy/data-portal/historic-demand-data,
   with a CKAN API at api.neso.energy.
3. feed-a: Local test feed A. A half-hourly series. http://127.0.0.1:${port}/f/${token_a}/series.csv
4. neso-ews: NESO Embedded Wind and Solar Forecasts. Half-hourly forecasts from within day up to 14 days
   ahead, with yearly historic archives. https://www.neso.energy/data-portal/embedded-wind-and-solar-forecasts
5. pvlive: Sheffield Solar PV_Live. Half-hourly estimates of GB solar PV generation, national and by
   region. https://www.solar.sheffield.ac.uk/api/
6. feed-b: Local test feed B. A half-hourly series. http://127.0.0.1:${port}/f/${token_b}/series.csv
7. om-era5: Open-Meteo Historical Weather API (ERA5 reanalysis). Hourly weather from 1940.
   https://open-meteo.com/en/docs/historical-weather-api ("HTTP GET, no authentication").
8. om-hfc: Open-Meteo historical forecast archive. Archived hourly weather forecasts from 2021.
   https://open-meteo.com/

For each source, try to download data that covers its target date at the source's own time step:
half-hourly for elexon, neso-demand, neso-ews, pvlive, feed-a and feed-b; hourly for om-era5 and om-hfc.

Then write evidence.json in the current directory, with one entry for each of the 8 sources:
{"schema": "x06-evidence/1",
 "sources": [
  {"id": "elexon", "outcome": "retrieved", "attempt": 2, "url": "https://...", "time_field": "startTime",
   "resolution_minutes": 30, "rows_on_target_date": 48, "key_or_login_seen": false,
   "note": "One sentence on what you found."}]}
outcome is one of:
- "retrieved": the body saved by attempt N holds data for the target date at the stated time step.
  Give time_field (the column or field with the times), resolution_minutes and rows_on_target_date
  (the number of distinct times on the target date).
- "key_required": the source said a key, token, login or registration is needed.
- "not_found": you could not find a URL that serves the data.
- "failed": you found the data but could not get a sample for the target date.
- "not_tried".
Use null for fields that do not apply. Stop once evidence.json is written.
```

**Registered follow-up** (`followup.txt`, sent at most once; `${errors}` is the validator's list):

<!-- registered file: followup.txt -->
```text
evidence.json is missing or does not match the required shape. Problems found: ${errors}. Write a corrected evidence.json with one entry for each of the 8 sources. Do not download anything again unless an entry needs it. Then stop.
```

**Evidence schema (`x06-evidence/1`).**
- `sources` has 8 entries, and each id appears exactly once.
- `outcome` is one of `retrieved`, `key_required`, `not_found`, `failed`, `not_tried`.
- `attempt` is an integer from 1 to 6, or null.
- `url`, `time_field` and `note` are strings or null.
- `resolution_minutes` is 30, 60 or null.
- `rows_on_target_date` is an integer or null.
- `key_or_login_seen` is a boolean.
- For `retrieved`, the attempt, URL, time field, resolution and rows are required, and
  `evidence/<id>/<attempt>.body` must exist.

## Controls
- **C1, extension set** (per session).
  - `get_commands` names exactly {llama, nb, nb-python}.
  - The `sourceInfo.baseDir` of `nb` and `nb-python` is the realpath of the pi-notebook-py `-e`
    path.
  - `get_state` reports the provider and model pinned in `versions.env`, at thinking level `high`.
  - `pi --version` is 0.84.2.
  - There are no `extension_error` events and no extension error in `stderr.log`.
  - Every tool name called is in `allowed_tools`.
  - There is no `work/.pi/stories.db`.
  - A session that makes no web search passes C1 vacuously for pi-web-search, and is flagged.
- **C2, isolation** (per run).
  - The main tree's `git status --porcelain=v1 --untracked-files=all` after the run equals its
    status before, plus paths under the run directory.
  - The worktree is clean before and after.
  - The submodule is at its gitlink, and clean.
  - `~/.pi/agent/settings.json` is byte-identical.
  - No tool-call argument contains `/home/azureuser/pi-research` or the worktree path.
- **C3, positive control** (per session).
  - The server log shows at least one 200 for the session's feed-a token.
  - The checker finds a feed-a witness whose body has the served sha256 and 48 half-hourly rows.
  - The agent reports `retrieved` for feed-a.
- **C4, negative control** (per session).
  - The server log shows at least one 401 for the session's feed-b token.
  - No request carried an `Authorization` header.
  - The agent does not report `retrieved` for feed-b.
  - The checker finds no feed-b witness.
- **Run validity.** The run is `invalid` if any of the following holds:
  - any session fails C1;
  - the run fails C2;
  - there is any feed-b witness;
  - fewer than 4 of the 6 sessions pass both C3 and C4.

## Outcome classes
The first matching class wins.

| Class | Condition | Action |
|---|---|---|
| `invalid` | the run fails the validity rule above | debug, record a deviation, re-run |
| `access-claims-refuted` | at least 1 dataset is not as claimed | G1: a corrected access table for the notes |
| `access-claims-confirmed` | all 6 datasets are accessible as claimed | G1 |
| `access-claims-mostly-confirmed` | at least 4 are accessible, and none is refuted | G1: options for the inconclusive datasets |
| `inconclusive` | otherwise | G1: the limit is the instrument, pi at this budget |

## Predictions
These are priors, with no look-ups and no pilot.
- **Probability each dataset is accessible as claimed:**
  - elexon 0.85;
  - neso-demand 0.8;
  - neso-ews 0.6;
  - pvlive 0.7;
  - om-era5 0.9;
  - om-hfc 0.55.
- **Class:**
  - `access-claims-mostly-confirmed` 50%;
  - `inconclusive` 25%;
  - `access-claims-confirmed` 15%;
  - `access-claims-refuted` 10%.
- **Controls:** C3 passes in at least 5 of 6 sessions (75%).
- **Cost:** the median session costs about $0.05.

## Outputs
Each run writes `energy-pricing-model/experiments/x06-open-data-access/results/<UTC run-id>/`:
- `manifest.json`;
- `config.toml`;
- `records.jsonl`, with one record per session;
- `summary.json`, holding the class, the per-dataset verdicts, the controls and the descriptive
  values;
- `control_server.jsonl`, holding status and header names, never values;
- `environment.json`, holding the sha256 of the pins and of the settings files;
- `sessions/sNN/`, holding:
  - `evidence.json`, `evidence/**` and `fetch.sh`;
  - `notebooks/`;
  - `drive/`: `events.jsonl.gz`, `transcript.log`, `stderr.log`, `cmds.jsonl`, `exit_code` and
    `sessions/*.jsonl.gz`;
  - `nb_env_lock.txt`;
  - `checks.json` and `audit.json`.

Every API key is redacted before commit. `recheck.py <run-dir>` recomputes every verdict from the
committed files. The writeup goes to
`energy-pricing-model/writeup_generated/x06-open-data-access.md`.

## Limitations, stated in advance
- The instrument is pi, running deepseek-v4-flash. An `inconclusive` verdict may mean the agent
  failed, not the source.
- Access is observed from one Azure VM on one date. A WAF block is excluded from refutation, but it
  still stops a witness.
- "No key" is tested only on the endpoints the agent reached. Coverage is tested only at the target
  dates, not "from 2001" or "14 days ahead".
- A body in a format the parser cannot read goes to manual review, which is listed separately.

## Deviations
1. **2026-09-26, after the first run attempt: the search cap ends the turn, not the session; CSV
   parser fix; costs from the event log.**
   - **What happened.** Run `20260926T133032Z` (commit 5e5c63a, clean worktree) is `invalid` and is
     kept in `results/` for the record.
     - Every session called `web_search_tavily` 12–13 times within 60–165 s; the prompt allows 10.
     - At the 12th call the harness sent `abort` and then stopped pi, so no session wrote
       `evidence.json`.
     - So C3 (the agent reports feed-a as retrieved) failed in all six sessions.
     - Separately, the checker crashed on a CSV body whose rows had more fields than its header, so
       no summary was produced.
     - The attempt cost $0.033 of model credit and 73 Tavily calls.
   - **Registered:**
     - "A monitor aborts the session after its 12th `web_search_tavily` call";
     - one follow-up, with the registered text, "if `evidence.json` is missing or invalid while pi is
       alive".
   - **Holds now:**
     - At the 12th search the monitor sends the RPC `abort` for the current turn only, and pi stays
       alive. Any later `web_search_tavily` call is aborted as soon as it is seen.
     - Suppose the cap was reached and `evidence.json` is missing or invalid. Then the one allowed
       follow-up is the cap follow-up below. Otherwise the registered follow-up applies unchanged.
       Whether the cap was reached is read from the event log.
     - The body parser ignores CSV fields beyond the header. This is a bug fix; the witness rules are
       unchanged.
     - A session's cost is the sum of the `message_end` usage costs in its event log.
       `get_session_stats` is unavailable once pi has stopped.
   - **Why:**
     - The cap is there to bound search spend. Ending the whole session also ended the agent's
       report, which made the positive control impossible to pass.
     - The fix keeps the bound: at most 12 completed searches per session, plus any that are aborted
       as they start. It also lets the agent report once.
   - **Unchanged:** the datasets, the prompt, `fetch.sh`, the witness and refutation rules, the
     controls and validity rule, the classes, N = 6, and the time and budget caps. The re-run uses
     the registered `config.toml`.
   - **Budget:** the user approved the re-run on 2026-09-26: up to $1.80 of model credit and about 72
     more Tavily calls.

The cap follow-up of deviation 1, sent verbatim and at most once:

<!-- registered file: cap_followup.txt -->
```text
You have used the search budget for this task. Do not search again and do not download anything more. Write evidence.json now, with one entry for each of the 8 sources, from what you have already saved in evidence/. Then stop.
```
