# Stage B plan — energy-pricing-model: testing the Rosso design note (x01–x06, up to gate G1)

**Status (2026-09-26):** in progress.
- **Steps 1–5 done:**
  - `docs/` was committed in b9291cd.
  - This plan, the theory note and the toy spec were committed in 26abb27.
  - The x06 launch check passed. It cost $0 and is not registered.
  - The six PREREGs were registered in 9b75f38 … f787c4a.
  - The library was committed in 42a75d4.
- **x01 done:**
  - `rule-fails-saturated`: e* = 5.85% (CI 5.68–6.04%). Only office at N = 100 fails.
  - `note-dual-statements` fails: S1 and S2 are contradicted on 100% of eligible instances, and S3
    misclassifies 12.1%.
  - Run `20260926T120707Z`, at commit a504ce3.
- **Next:** x02.

## Context

The user added two notes under `energy-pricing-model/docs/`:
- `tem-rosso-pricing-model-v1.md`, the design note under test;
- `tem-open-pricing-datasets-v2.md`, its companion.

They asked for the design note to be analysed, broken into testable hypotheses, and the experiments pre-registered. Every step below follows the experiment protocol.

**Decisions (the user's, 2026-09-26):**
- The experiments test the note's own claims, against Claude's seeded reference implementation. pi, with the notebook and web-search extensions, is used only for x06, which checks the companion note's claims about open data.
- Scope: register, implement, run and write up every experiment, then stop at gate G1.
- Commit `docs/` as received, and leave the user's uncommitted `AGENTS.md` edit unstaged.
- External look-ups by Claude: **none**, as decided in stage A. In x06, pi's searches and downloads are the method under test, and Claude judges them only from the evidence the run saves.

**Analysis so far.** These points come from hand checks and in-memory calculations made while planning. They are planning inputs, not results.
- **§3, the LP duals.** Three statements are wrong:
  - "μ=0 for inframarginal assets": the correct value is π_k−π_a > 0. μ=0 holds only for the marginal asset and the unused ones.
  - In the generation-scarce regime, μ is (λ−π_a)⁺, not λ−π_a.
  - The regime test should use profitable generation G⁺, not ΣG.

  Also, the first sum in ΔV_j is weighted by λ, where ν̄ is meant.
- **§2 and §7.3, the Jensen gap.** §2 says "5–11%", but the §7.3 table shows 2.9–10.6%. The note says the gap "peaks at balance", yet the table keeps rising up to 1.55. In the pilot, where the peak falls depends on the solar/wind mix of the pool.
- **§2, a new claim.** "Point forecasts … therefore underprice" reverses in saturated books when a prospect is valued.
- **§7.4** reproduces to rounding. For example, the note prints 154.19 where the calculation gives 154.204.
- **§7.5 and §6, jitter cost.**
  - The note's 1.0/4.0/18.1% are the cost of symmetric jitter at the γ=60% pass-through price, and that jitter breaks the cap on half the quotes.
  - At the optimum p*=159.746 the cost is 1.7/6.4/20.7%. The closed form is ½β²(1−P*)σ².
  - Jitter that respects the cap costs to first order: about 19.6% at σ=£1.
- **§5.** "Markup falls as β rises" fails whenever βP*(p_ref−p*) > 1. The note says the match "roughly doubles" the margin, but the ratios are 4.65× and 2.62×. And "two scalars" leaves out p_ref.
- **§4.** φσ is a mean–standard-deviation rule. It is not the second-order certainty equivalent of exponential utility, which is E+(a/2)Var.
- **§6.** In profit terms, both a confounded elasticity and jitter cost second order in the price error. In the pilot, randomisation pays only when prices are confounded.

## Claims → experiments

The full claim inventory goes in `plans/theory-rosso-claims.md`. For each claim it gives the section, a quote, its type and where it is tested.

| Experiment | Note sections | Primary hypothesis (H1 is the note's claim) |
|---|---|---|
| x01-lp-shadow-prices | §3 | `dual-2pct-rule`: at 2% of book volume, the dual valuation errs by ≤5% in every book-size × archetype cell |
| x02-jensen-gap | §2, §7.3 | `jensen-peak-at-balance`: the overstatement peaks for gen/demand in [0.75, 1.33] |
| x03-congestion-vs-shape | §7.1, §7.2, §4 | `congestion-dominates`: R ≥ 2, where R is the range over book size divided by the spread across archetypes |
| x04-price-and-jitter-cost | §5, §6, §7.4, §7.5 | `jitter-cost-at-optimum`: at p*, jitter costs 1.0/4.0/18.1% at σ=1/2/4 |
| x05-confounded-elasticity | §6 | `randomisation-pays`: it pays when prices are confounded, and costs when they are not |
| x06-open-data-access | companion §6.1, note §8 | Tier-1 datasets can be fetched without a key, at their stated resolution and coverage |

**Checked as controls, not hypotheses**, because they are theorems:
- merit-order optimality and the corrected dual table;
- the ΔV identity; that dual ≥ exact;
- Jensen's inequality, per half-hour; that O=0 without noise;
- monotone congestion under common random numbers;
- the first-order condition, and uniqueness by log-concavity;
- Π''(p*)=−βP*Q;
- that IPS is unbiased.

**Untestable here, listed in the theory note with the reason:**
- regulatory facts: A1–A3, κ and the Class A limits, the levy values, P442/ESNA and MHHS;
- proprietary data: the real β and p_ref, π_at, forecast error covariance, and whether LightGBM plus a copula is adequate;
- business opinion: "not a trading edge", the refusal of RL, the build order.

## Shared toy model (`plans/toy_v1_spec.md`; x01–x03 cite it by commit)

- **Grid.** 365×48 half-hours. Day 0 is a Monday.
- **Solar.**
  - Clear sky: a half-sine over the daylength L(d)=12.2+4.3·sin(2π(d−79)/365) h. Seasonal amplitude 1+0.6·sin(·).
  - Clearness: σ(s_c·z), where z is an AR(1) with φ=0.95 and s_c=1.5.
  - Capacity factor calibrated to 0.117. That matches the note's "6 MW gives r=1.23 at 20 sites".
- **Wind.**
  - Capacity factor σ(μ_w + a_w·cos(·) + s_w·w), where w is an AR(1) with φ=0.99, s_w=1.2 and a_w=0.
  - μ_w is calibrated so the mean capacity factor is 0.30.
- **Pools.**
  - P71 is §7.1's pool: 7.8 GWh/yr, with solar share θ_s=0.5.
  - P72 is §7.2's pool: 6 MW of solar only, 6.15 GWh/yr.
- **Archetypes.**
  - Each site is 250 MWh/yr.
  - Office: weekday plateau 09–17, base load b_o=0.35.
  - 24/7: 1+0.10·cos(2π(h−14)/24).
  - Evening venue: peak 18–23, weekend ×1.2.
  - Seasonal factors apply to all three.
- **Demand noise.**
  - Per site: lognormal with s_i=0.15 and AR φ=0.9.
  - Common factor: s_cm=0.05, with weather correlation ρ_DG=0.
- **Book growth.** Nested books, built round-robin: office, then 24/7, then evening.
- **Economics.** λ=45, π=10, ν̄=35. κ=2.5 is inert here: a site draws at most about 0.05 MWh per half-hour.
- **Monte Carlo.**
  - S=120 weather-years.
  - Common random numbers: `SeedSequence([20260926, s, entity])`.
  - Estimators are ratios of scenario sums.
- **Grid of configs.**
  - Base config.
  - 21 one-at-a-time cells: θ_s, s_c, s_w, a_w, b_o, the 24/7 amplitude, the evening level, s_i, s_cm and ρ_DG.
  - 40 Latin-hypercube cells, seed 20260926.
- **AR coefficients.** They cannot move per-half-hour expectations, so the invariance cells φ ∈ {0.5, 0.9} are a negative control, not a robustness dimension.

## The experiments

Every experiment's PREREG follows the protocol's skeleton. Each has:
- a secondary and a descriptive hypothesis in addition to the primary one;
- controls, with an independent checker among them;
- outcome classes with `invalid` first, where each action names the next run or G1;
- predictions, with the planning evidence behind them.

**x01-lp-shadow-prices.**
- **Part A: single half-hour LPs.** 5,000 random instances with heterogeneous π, some above λ, and customer caps, plus 500 deliberately degenerate ones.
  - C1: an exact-rational certificate for the greedy primal and the corrected dual table.
  - C2: agreement with HiGHS. Objectives match to 1e-9. Duals match to 1e-6, or fall inside the set of valid duals where the instance is degenerate.
  - C3, negative control: plant the note's μ=0 and check that C2 rejects it.
  - Secondary `note-dual-statements`. H1: the three §3 statements hold on every eligible instance. Predicted H0 at 99%: counterexamples on every eligible instance for inframarginal μ, and the ΣG test misclassifies 8–18% of instances.
- **Part B: P71 books.**
  - N ∈ {10,20,30,40,60,100} sites.
  - Prospect sizes q ∈ {0.25, 0.5, 1, 2, 4, 8, 16}% of book volume.
  - Compare the dual valuation ν̄Σ1{G>D}d with the exact value ν̄Σmin(d,(G−D)⁺), bootstrapping over scenarios with B=2,000.
- **Other controls:**
  - C4: the ΔV identity against a HiGHS solve of the LP with one variable per site;
  - C5: dual ≥ exact;
  - C6: the closed-form identity for the error;
  - C7: calibration.
- **Classes.** e* is the worst cell's error at q=2%.
  - `rule-holds`: the CI upper bound of e* is ≤ 5%.
  - `rule-fails-saturated`: only cells with N ≥ 60 fail.
  - `rule-fails-broadly`.
  - `inconclusive`.
- **Prediction.** `rule-fails-saturated` at 50%. The pilot's worst cell is 5.3%, for office at N=100. In money the error is at most £0.25/MWh.

**x02-jensen-gap.**
- **Measure.** O(N) is the overstatement: in-sample mean shapes against E[matched].
  - N ∈ {4, …, 200}, so r runs from 7.8 down to 0.156.
  - Bootstrap B=1,000.
- **Classes**, based on P_B ≥ 0.8 of bootstrap resamples: `peak-at-balance`, `peak-above-balance`, `peak-below-balance`, `multimodal`, `inconclusive`.
- **Secondary `pointforecast-underprices`.** H1: s^pt ≥ s in every archetype × N cell. Predicted to fail at 90%: +13–20 pp at N=10, and −1.5 to −2.9 pp at N=100.
- **Descriptive:**
  - the peak across θ_s ∈ {0, .25, .5, .75, 1};
  - magnitudes against the note's 10.6/7.3/4.9/2.9% and "5–11%";
  - the phantom margin at N=40 against the note's £10k;
  - which noise source drives the gap;
  - robustness across the Latin-hypercube cells.
- **Controls:**
  - Jensen per half-hour, in-sample;
  - O=0 exactly with zero noise;
  - an analytic checker, the Gaussian closed form for E min(X,D);
  - AR invariance;
  - finite-S bias;
  - calibration.
- **Prediction.** `peak-above-balance` at 75%. The pilot's peak is at r≈2.6 with O_max≈12.9%.

**x03-congestion-vs-shape.**
- **Measure.** s_a(N) is the marginal matched share of one more site of archetype a.
  - N ∈ {0, …, 100} in P71 and P72.
  - R = (the smallest, over archetypes, of each archetype's range over N) / (the largest, over N, of the spread across archetypes), taking N over {10,20,30,40,60,100}.
- **Classes:**
  - `congestion-dominant`: the CI lower bound of R is ≥ 2.
  - `congestion-larger`: the CI lower bound is ≥ 1.
  - `shape-comparable`: the CI upper bound is < 1.
  - `inconclusive`.
- **Secondary:**
  - `shape-rank-solar`: office > 24/7 > evening in P72 at N=20 and 40.
  - `shape-gap-vs-markup`: ν̄·(office − evening) at N=40 is ≥ £3.86/MWh.
- **Descriptive:**
  - where the ranks reverse (the note says N=30; I predict somewhere in N=60–100);
  - R for the solar-only pool (about 1);
  - standalone against marginal share, i.e. the cost-plus error, about 3× at N=40;
  - RMSE against the note's tables;
  - the note's £7,079 against £163.
- **Controls:**
  - monotone decline under common random numbers;
  - the increment identity;
  - a HiGHS checker;
  - the limits G≡0 and G≡∞;
  - AR invariance;
  - calibration.
- **Prediction.** `congestion-dominant` at 90%, with the pilot's R at 3.7. The shape rank holds at 90%.

**x04-price-and-jitter-cost** is a deterministic audit that uses the note's own inputs.
- **Primary classes:** `note-confirmed` (the note's figures hold at p*), `misattributed-cap`, `misattributed-other`, `unexplained`.
- **Secondary `s74-reproduction`:** `exact`, `rounding` or `mismatch`.
- **Descriptive:**
  - L/σ² tends to 0.01754 as σ→0;
  - jitter that respects the cap (half-normal) costs to first order, with L/σ tending to 0.188;
  - the rule that decides the sign of dm/dβ;
  - the margin ratios 4.65× and 2.62×;
  - the rent split;
  - γ binds from 2.63%.
- **Controls:**
  - the optimum: bisection against a grid search, and log-concavity;
  - Gauss–Hermite against 10⁷ Monte Carlo draws, within 4 SE;
  - Π'' by finite difference;
  - σ=0 gives 0.
- **Prediction.** `misattributed-cap` at 95%, and `rounding` at 90%.

**x05-confounded-elasticity.**
- **Market.** Four segments. u ~ N(0,9). The desk sees s=u+η with corr(s,u)=ρ and prices by plug-in, plus unlogged noise ζ. β=0.33. The estimand is the population slope β_marg≈0.280.
- **Pipelines.**
  - NV: the naive logit fitted on 2,000 historical quotes.
  - RL(σ_j): log with jitter, then refit.
  - RG: a markup grid chosen by IPS.
  - Each runs 2,000 logging quotes, then 8,000 exploiting ones.
- **Grid.** ρ ∈ {0, .3, .5, .8}; σ_j ∈ {1, 2, 4}; R=1,000 replications. One-at-a-time robustness over τ_u, τ_ζ and N_log.
- **Classes:** `pays-when-confounded` (Δ>0 at ρ=.5 and .8, and Δ<0 at ρ=0), `pays-always`, `pays-only-strong`, `never-pays`, `inconclusive`.
- **Secondary `naive-inelastic`:** E[β̂_NV] < β_marg whenever ρ>0.
- **Controls:**
  - IPS is unbiased against the true value;
  - random prices recover β_marg, and recover 0.33 when τ_u=0;
  - negative control: at ρ=0, the naive and randomised estimates are equal;
  - win rates match the simulator;
  - the oracle matches a grid search;
  - no more than 1% of fits are censored.
- **Prediction.** `pays-when-confounded` at 80%. Attenuation ≈ 0, .12, .30 and .58 across the four ρ values.

**x06-open-data-access** is the only experiment that uses pi.
- **Datasets**, from companion §6.1:
  - elexon, neso-demand, neso-ews and pvlive, target date 2026-03-10, half-hourly;
  - om-era5, target date 2026-03-10, hourly;
  - om-hfc, target date 2021-12-15, hourly.
- **Local controls**, served by the harness: feed-a returns 200 with a known CSV, and feed-b returns 401.
- **Launch.** The stage A spec, plus:
  - `--thinking high` (the pinned model supports only off, high and xhigh);
  - an allowlisted environment, so `VIRTUAL_ENV`, `PI_MODEL` and `PI_PYTHON` cannot leak in;
  - `PI_NOTEBOOK_HOME` set per session;
  - workdirs under `~/pi-work/energy-pricing-model/x06/<run-id>/sNN/`.
- **Evidence.**
  - Downloads go only through a registered `fetch.sh`, which saves the body, the headers and curl's `%{json}` write-out.
  - pi writes `evidence.json` (x06-evidence/1).
  - Verdicts come only from the saved evidence, by the registered witness and refutation rules.
  - `recheck.py` recomputes every verdict from the committed files.
  - Claude never re-fetches anything.
- **Controls:**
  - C1, the extension set: exactly {llama, nb, nb-python}, with the `sourceInfo.baseDir` paths; model, thinking level and pi version checked through `get_state`; only allowed tools are called; no `stories.db`.
  - C2, isolation: the main tree, the worktree, the submodule and `settings.json` are unchanged, and no tool call names a repo path.
  - C3, positive: a feed-a witness, checked against the served sha256.
  - C4, negative: no feed-b witness, and no claim of one.
  - The run is `invalid` if C1 or C2 fails, if any feed-b witness exists, or if fewer than 4 of the 6 sessions pass C3 and C4.
- **Classes:** `access-claims-refuted`, `-confirmed`, `-mostly-confirmed`, `inconclusive`.
- **Caps.**
  - 6 sessions, 3 at a time, started 20 s apart.
  - 1,200 s and $0.30 per session.
  - At most 10 searches; the harness aborts at 12.
  - 6 attempts per source, and at most 1 follow-up prompt.
  - Worst case: $1.80 and 72 Tavily calls, with about 2,600 s of wall time.
- **Secrets.** The agent's bash inherits both API keys, so every log is redacted before it is committed, and `events.jsonl` is gzipped.
- **Predictions:** the probability that each dataset is accessible as claimed ranges from 0.55 (om-hfc) to 0.9 (om-era5).

## Library (`energy-pricing-model/experiments/`)

- **uv project.**
  - `pyproject.toml`: build backend `uv_build`, with module root `lib/python`; dependencies numpy and scipy; dev dependencies pytest and hypothesis.
  - `uv.lock` and `.python-version` (3.12).
  - A `.gitignore` covering `.venv/`, `__pycache__/`, `.pytest_cache/` and `.hypothesis/`.
- **`lib/python/epmlib/`:**
  - `config` loads TOML into frozen dataclasses;
  - `jsonio`;
  - `rng` uses SeedSequence streams, never `hash()`;
  - `outcomes` holds the `Rule` table and `first_match`;
  - `runlib`:
    - the UTC run-id;
    - the manifest, with commit, dirty flag, uv.lock sha, config sha, platform and times;
    - `--config --out --resume --workers`;
    - checkpoints;
    - forkserver workers with BLAS threads set to 1;
  - `toy/` holds grid, solar, wind, demand, scenarios with common random numbers, and matching;
  - `allocation` and `lpcheck` (HiGHS through `linprog`);
  - `pricing`, `jitter`, `elasticity`;
  - `pi/` for x06: paths, launch, environment, control server, events, evidence, audit, secrets, session, verdict. It runs `tools/pidrive.py` as a subprocess; it does not copy it.
  - `xp/x0N_*.py` holds each experiment's config, units, summary, rules and `main`.
- **Each experiment directory** holds a thin `run.py`, `config.toml`, a `config_smoke.toml` labelled "smoke, not registered", and `results/`.
- **`tests/`:**
  - hypothesis properties: greedy equals HiGHS, the dual table, the ΔV identity, Jensen, dual ≥ exact, the pricing properties, jitter as σ→0, logit recovery, IPS unbiasedness;
  - runlib tests: `--resume` gives the same result, `--workers` does not change results, a dirty tree is refused;
  - classifier tests: every class reachable, `invalid` first;
  - x06 tests with a fake pi: honest, liar, bad tool and key-leak modes;
  - `test_prereg_sync.py`: the fenced registered blocks equal the configs, `prompt.txt` and `fetch.sh`;
  - golden fixtures for toy-v1 and §7.4.

## Execution order and commits

All commits:
- are made as `Marco Z <ocramz>` (the configured identity) with no Claude attribution;
- stage files by name, and are never pushed;
- never stage `AGENTS.md`.

1. `docs: tem pricing design note v1 and open-datasets note v2 (stage B inputs, as received)`
2. Commit subject: `stage B: plan, and theory note B (claims in the Rosso design note); toy-v1 spec; stage A superseded`. The commit adds:
   - `plans/stage_b_plan.md`, which is this plan;
   - `plans/theory-rosso-claims.md`;
   - `plans/toy_v1_spec.md`;
   - a Status update to `stage_a_plan.md`;
   - a "superseded, carried into x06" banner on `x01_prereg_draft.md`.
3. An x06 launch check. It is unregistered and costs $0, because no prompt is sent. It uses the exact x06 flags and environment and writes to the scratchpad. It is cited as a planning input.
4. Six registration commits, each holding its `PREREG.md` alone, `prereg: x0N-<slug> (<question>)`. All six come before any library code exists.
5. `library: uv project, run machinery, outcome tables; tests`. `uv lock` needs PyPI once, as a dependency install.
6. For each of x01 to x06, in order:
   1. Implement.
   2. Smoke run into the scratchpad.
   3. Commit once `uv run --locked pytest` is green: `x0N: …; tests, run script, config`.
   4. Run the default config from a clean `git worktree` at that commit, at `/home/azureuser/pi-research-worktrees/epm`, with `--out` pointing at the main tree's `results/`. The worktree is needed because the user's AGENTS.md edit keeps the main tree dirty.
   5. Apply the outcome table, with the independent checker.
   6. Write up, update the Status block, and commit `x0N results (<class>: <finding>) and writeup; plan status`.

   x06 also gets three smoke stages first: the fake pi; real pi with no prompt ($0); and one paid session that covers only feed-a and feed-b, capped at $0.05.
7. `stage B gate G1 report: …`. It adds `writeup_generated/stage-b-gate-g1.md`, with verdicts, findings, decisions for the user and reproducibility, plus option drafts as `plans/*_draft.md`. Then **stop**.

## Verification
- `uv run --locked pytest -q` is green at each implementation commit, and again in the worktree before each run.
- Every manifest has `git_dirty=false` and the implementation commit. `git check-ignore` passes on every run directory, and `.venv` is ignored.
- Every control, including the independent checkers, passes. A failure is recorded as `invalid` and a deviation, then re-run.
- x06: `recheck.py` reproduces the verdicts from the committed files, and a secret scan of the run directory finds no key.
- Commit audit: `git log main..` shows the subjects above, all by Marco Z <ocramz>. No commit has a Co-Authored-By line or touches `AGENTS.md`, and nothing is pushed.

## Risks and notes
- **Network.** `uv lock` needs PyPI. x06 needs OpenRouter, Tavily and the dataset hosts. If the sandbox blocks them, I ask before running those commands outside it.
- **Spec errors.** A spec error found after registration becomes a numbered, dated deviation, cross-referenced in every PREREG that uses the spec.
- **pi reliability.** deepseek-v4-flash may be unreliable. Verdicts never rest on the agent's own claims; the fetch script, the validator, the caps, N=6 and the local controls bound that risk.
- **Worktree.** The worktree lacks the submodule, `.cache` and `.env`. The x06 harness takes them from the main tree, after checking that the submodule matches the gitlink and is clean.
