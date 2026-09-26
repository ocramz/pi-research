# x06 — Can pi fetch the Tier-1 open datasets without a key?

- **PREREG:** `energy-pricing-model/experiments/x06-open-data-access/PREREG.md`, registered in
  f787c4a.
- **Deviations:** one, after the first attempt. Deviation 1 (2026-09-26) was recorded in 9173473 and
  implemented in 6a588c4:
  - the search cap ends the turn, not the session;
  - one cap follow-up;
  - a CSV parser fix;
  - session cost read from the event log.
- **Code:**
  - `experiments/lib/python/epmlib/pi/` (the harness) and `xp/x06_open_data_access.py`;
  - `x06-open-data-access/`: `fetch.sh`, `prompt.txt`, `followup.txt`, `cap_followup.txt`,
    `recheck.py`.
- **Runs:**
  - `results/20260926T133032Z/`: the first attempt, at 5e5c63a. **`invalid`**, kept for the record
    (see Deviations).
  - `results/20260926T135115Z/`: the run reported here. Commit 6a588c4, clean worktree (`git_dirty`
    false at the start and the end), 6 sessions with 3 running at a time, 458 s of wall time.
- **Agent:** pi 0.84.2 with pi-notebook-py and pi-web-search only, running `openrouter` /
  `deepseek/deepseek-v4-flash` at thinking level `high`.

## Verdict

| Class | Result |
|---|---|
| `access-claims` (primary) | **`access-claims-mostly-confirmed`**. 5 of 6 datasets are accessible without a key as claimed: Elexon, NESO demand, PV_Live, Open-Meteo ERA5, and the Open-Meteo historical-forecast archive from 2021. NESO's embedded wind and solar forecasts are `inconclusive`. None is refuted. |

**Controls and validity.** The run is valid.

| Control | Result |
|---|---|
| C1, extension set | all 6 sessions: commands exactly {llama, nb, nb-python}, with the pi-notebook-py baseDir; pinned model; thinking `high`; pi 0.84.2; no extension errors; only allowed tools; no `stories.db` |
| C2, isolation | main tree changed only under the run directory; worktree clean; submodule unchanged; `settings.json` unchanged; no repo path in any tool argument |
| C3, positive control (feed-a) | 5 of 6 sessions pass. s01 retrieved feed-a with a verified sha256 but never wrote `evidence.json`, so its "agent reports retrieved" item fails |
| C4, negative control (feed-b) | all 6: a 401 was logged, no Authorization header was sent, the agent reported `key_required`, and no witness exists |

- Sessions passing C3 and C4: 5, against a minimum of 4. There is no feed-b witness.
- **Vacuous passes:** none. Every session made 12–14 searches.
- **Independent recheck.** `recheck.py` recomputes every dataset verdict and every session's
  C1/C3/C4 from the committed files, and all of them match.
- **Secrets.** No API key appears anywhere in the run directory, checked by a separate scan.

## Question
The companion note (§6.1) and the design note (§8) say Tier-1 GB datasets are open: no key,
half-hourly or hourly, with stated coverage. With Claude making no look-ups, can a pi agent with only
the notebook and web-search extensions fetch a target-day sample of each, as verifiable evidence?

## Results

### Per dataset (a witness is a saved response that passes all eight registered criteria)

| Dataset | Verdict | Witness (session, endpoint) |
|---|---|---|
| elexon | accessible | s06: `data.elexon.co.uk/bmrs/api/v1/datasets/MID` for 2026-03-10, 48 half-hours |
| neso-demand | accessible | s06: a download from the `api.neso.energy` CKAN resource (historic demand; SETTLEMENT_DATE and SETTLEMENT_PERIOD), 48 half-hours |
| neso-ews | **inconclusive** | none. s06 reached the portal's metadata and then a download that curl stopped at the registered 50 MB limit (empty body, non-zero exit). No other session tried. |
| pvlive | accessible | s05: `api.solar.sheffield.ac.uk/pvlive/api/v4/pes/0`, 48 half-hours |
| om-era5 | accessible | all 6 sessions: `archive-api.open-meteo.com`, 24 hours |
| om-hfc | accessible | s01, s02, s03 and s05: `historical-forecast-api.open-meteo.com/v1/forecast` for 2021-12-15, 24 hours |

**Manual review (registered rule).** Three 200 responses from a registered host could not be parsed:
- s03 Elexon attempt 1;
- s04 Elexon attempt 2;
- s06 Elexon attempt 2.

All three are the same 926-byte HTML page from `bmrs.elexon.co.uk`, the website's app shell rather
than data, so each fails criterion 7 and is not a witness. Nothing was fetched again.

### Per session

| Session | Searches | Follow-up | Cost ($) | Retrieved claims (true / false) | Notes |
|---|---|---|---|---|---|
| s01 | 14 | cap | 0.0035 | no report | witnesses for om-era5, om-hfc and feed-a exist, but no `evidence.json` |
| s02 | 12 | cap | 0.0081 | 3 / 0 | |
| s03 | 13 | cap | 0.0074 | 3 / 0 | |
| s04 | 12 | cap | 0.0097 | 2 / 0 | |
| s05 | 12 | cap | 0.0058 | 4 / 0 | the only PV_Live witness |
| s06 | 13 | cap | 0.0381 | 4 / 2 | claimed neso-ews (the download never completed) and om-hfc (its URL was the ERA5 endpoint) |

- **Total:** $0.073 of model credit and 76 Tavily calls.
- **Search limits.** The prompt allowed 10 searches. Every session exceeded that and reached the
  harness cap of 12.
- **Claim precision.** Of the agents' 18 "retrieved" claims, 16 are backed by a witness (89%). That
  is why verdicts never rest on the agent's own report.

## Why
- **Instruction-following.** The pinned model does not keep to a stated search budget; all 12 of 12
  sessions across both runs overran it. Without deviation 1, that ended every session before it could
  report.
- **Coverage within the budget.** Once the cap stopped searching, the agents reported on what they
  had already saved. Coverage then depended on which sources each agent reached first. Open-Meteo is
  easy to reach, with direct and well-known query URLs. NESO and PV_Live need portal navigation or
  the right API version (several sessions got 404s from older PV_Live paths).
- **neso-ews stayed inconclusive because of the instrument,** not the source. The one session that
  found the dataset tried to download a file above the 50 MB size limit.

## What this means
- **The core of the notes' open-data claim holds for this sample.** Elexon, NESO historic demand,
  PV_Live and Open-Meteo (reanalysis and the 2021 forecast archive) can each be fetched as a
  target-day half-hourly or hourly sample without a key, from this VM on 2026-09-26.
- **NESO's embedded wind and solar forecasts are unverified.** A follow-up could allow a larger
  download, or a date-filtered API query, and confirm them.
- **As an instrument,** deepseek-v4-flash via pi is cheap (about $0.01 per session) but needs hard
  caps and evidence-based checking. It overran every search budget, left one session unreported, and
  made 2 false "retrieved" claims.
- **Gate G1.** The result goes to G1: the open data can support stage C's reference-book option, and
  neso-ews is an open item.
- **Limitations.**
  - Access was observed from one Azure VM on one date, via the endpoints the agents found.
  - Coverage is tested at the target dates only.
  - "Inconclusive" reflects this budget and instrument.

## Predictions against results
| Prediction | Result |
|---|---|
| Accessible as claimed: elexon 0.85, neso-demand 0.8, neso-ews 0.6, pvlive 0.7, om-era5 0.9, om-hfc 0.55 | all accessible except neso-ews (inconclusive) |
| Class: `access-claims-mostly-confirmed` 50% | `access-claims-mostly-confirmed` |
| C3 passes in ≥ 5 of 6 sessions (75%) | 5 of 6 |
| Median session cost about $0.05 | **not met**: $0.008 |

## Unregistered work
- **Smoke runs (not registered)**, which went to the scratchpad:
  - the fake pi, free;
  - real pi with no prompt, which exercised C1 and C2 for $0;
  - one paid session on the local feeds only, $0.0017.
- **The invalid first attempt.** It is committed but was not analysed for verdicts.

## Deviations
- **Before the first attempt:** none.
- **After the first attempt:** deviation 1 (2026-09-26).
  - **What happened** (run `20260926T133032Z`, `invalid`):
    - All six sessions reached the 12-search cap within 60–165 s.
    - The registered monitor aborted each turn and then stopped pi, so no session wrote
      `evidence.json`, and C3 failed in every session.
    - The checker then crashed on a CSV body with overflow fields.
    - The attempt cost $0.033 and 73 Tavily calls.
  - **Now:**
    - At the cap only the current turn is aborted, and later searches are aborted as they appear.
    - The one allowed follow-up is a registered cap text, `cap_followup.txt`.
    - The parser ignores overflow CSV fields.
    - Cost is summed from the event log.
  - **Unchanged:** everything else in the design.
  - **Approval:** the user approved the re-run and its budget before it ran.
