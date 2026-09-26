# Stage B, gate G1 — the Rosso design note, tested

- **Stage plan:** `energy-pricing-model/plans/stage_b_plan.md`.
- **Theory note:** `plans/theory-rosso-claims.md`, which has the claim inventory and derivations.
- **Toy model:** `plans/toy_v1_spec.md`, at 26abb27.
- **Inputs:** `docs/` at b9291cd.
- **Branch:** `exp/energy-pricing-model`, not pushed.
- **Date:** 2026-09-26.
- **Writeups:** `writeup_generated/x01-…` to `x06-…`.

## Verdicts

| Experiment | The note's claim | Primary class | Secondary | Run (commit) |
|---|---|---|---|---|
| x01-lp-shadow-prices | §3: the dual table; "re-solve whenever Q_j exceeds ~2%" | `rule-fails-saturated`. e* = 5.85%; only office at N = 100 fails. | `note-dual-statements` **fails**: S1 and S2 fail on 100% of eligible instances, S3 misclassifies 12.1% | 20260926T120707Z (a504ce3) |
| x02-jensen-gap | §2, §7.3: "peaks at balance"; "therefore underprices" | `peak-above-balance`. r_peak = 2.23, O_max = 13.5%. | `pointforecast-underprices` **fails**: 12 of 18 cells overprice | 20260926T122425Z (eaa2396) |
| x03-congestion-vs-shape | §7.1–7.2: congestion dominates; shape is margin-sized | `congestion-dominant`. R = 3.62. | shape rank **holds**; shape gap of £4.48/MWh **holds** | 20260926T123334Z (531080c) |
| x04-price-and-jitter-cost | §6, §7.5: "£1/MWh of jitter costs 1.0%" at the optimum | `misattributed-cap`. At p* it is 1.71%; the note's figures are those at the cap. | §7.4 table: `rounding` | 20260926T124644Z (6ecd92f) |
| x05-confounded-elasticity | §6: the naive logit is inelastic; randomisation is "unanswerable" | `pays-when-confounded`. Gain of +2.9% at ρ = 0.5 and +31.7% at ρ = 0.8; −1.0% at ρ = 0. | `naive-inelastic` **holds** | 20260926T130201Z (13f9d09); deviation 1, before the run |
| x06-open-data-access | companion §6.1 and note §8: Tier 1 is open, with no key | `access-claims-mostly-confirmed`. 5 of 6 accessible; NESO forecasts inconclusive. | — | 20260926T135115Z (6a588c4); deviation 1, after an `invalid` first attempt |

**Controls.**
- All registered controls pass in every run reported above, and no run is censored beyond its
  registered limits.
- Two experiments carry a deviation:
  - x05, before its run: C6 is scoped to the primary grid, because the RL refits in one robustness
    cell are completely separated.
  - x06, after its first attempt, which was `invalid`: every session reached the search cap before
    reporting. The fix and the re-run were approved by the user.

## Main findings

### What the note gets right
- **Congestion comes first.** In a mixed pool, congestion is several times larger than load shape
  (R = 3.6), and R ≥ 2 in 92.5% of random toy parameterisations.
- **Shape is margin-sized.** Office against evening venue at 40 sites is £4.48/MWh; the note says
  £4.2.
- **§7.4's price table** is right to rounding.
- **Confounded quote logs bias the logit toward inelasticity:** 12–57% attenuation for desk
  information ρ = 0.3–0.8. Randomised quoting recovers the population response slope.
- **The dual approximation is accurate for small prospects** unless the book is saturated: at most
  2.7% error at 2% of volume for N ≤ 60.
- **The core open-data claim holds.** Elexon, NESO historic demand, PV_Live and Open-Meteo
  (reanalysis and the 2021 forecast archive) each served a target-day sample without a key.

### What the note gets wrong, or overstates
- **§3's dual table has three errors.**
  - Inframarginal generators earn μ = π_k − π_a, not 0.
  - Unprofitable assets have μ = 0, not λ − π.
  - The regime depends on profitable generation.

  Each has certified counterexamples; all 11,328 were re-checked independently in exact
  arithmetic.
- **§2 and §7.3: the Jensen gap does not peak "at balance".**
  - Where it peaks depends on the generation mix: r = 2.23 for the base mix, 1.25 for wind only,
    0.39 for solar only.
  - Point forecasts do not uniformly underprice: they overprice saturated books.
- **§6 and §7.5: the quoted jitter costs are misattributed.**
  - 1.0/4.0/18.1% is the cost of symmetric jitter at the γ = 60% pass-through price, and that jitter
    breaks the cap on half of all quotes. At the optimum, £1 of jitter costs 1.7%.
  - Jitter that respects the cap costs 19.6% at £1. That is first order.
- **§5:** "markup falls as β rises" fails whenever the cost advantage is large, which is exactly
  where the exempt match takes a supplier.
- **§6: randomisation pays only when historical prices are confounded.** It costs about 1% of value
  when they are not, with break-even at ρ ≈ 0.33 in the simulated market.
- **§7.1 details that do not reproduce in toy v1:**
  - the 24/7 reversal comes at N = 100, not 30;
  - the saturated-book value is £348, not £163.
- **Companion §6.1:** NESO's embedded wind and solar forecasts could not be verified. The one
  session that found them was stopped by the 50 MB download limit.

## What this means
- **For anyone implementing the note's architecture:**
  - Use the corrected dual table.
  - Scale the re-solve rule by the book's surplus, not its volume (option A).
  - Keep distributional forecasts, but assume no sign for the pricing error of point forecasts.
  - Budget exploration outside the pass-through cap, or randomise which customers receive the cap.
  - Measure confounding before paying for randomisation, for example by comparing the naive slope
    with a small randomised pilot.
- **For the agent programme:** pi with deepseek-v4-flash is cheap, at about $0.01 per session. But
  it overran every stated search budget (12 of 12 sessions) and made false "retrieved" claims (2 of
  18). Hard caps and verdicts drawn only from evidence are necessary.
- **Scope.**
  - x02, x03 and x05 are evidence within a reconstructed toy (v1) or a stylised market.
  - x01 Part A and x04 are exact results about the note's own model and statements.
  - x06 is observational: one VM, one date.

## Decisions for the user
1. **Option A: register x01a**, the surplus-scaled re-solve rule. The draft is
   `plans/x01a_surplus_scaled_rule_draft.md`. It is local compute only.
2. **Option B: stage C, pi replication.** pi audits §7.4–7.5 against x04 as the reference. The
   draft is `plans/x07_pi_replicates_x04_draft.md`. It is capped at $2 of model credit and about 30
   Tavily calls.
3. **Option C: x06a, verifying NESO embedded forecasts** with a date-filtered query or a larger size
   limit. The draft is `plans/x06a_neso_ews_draft.md`. It costs under $0.10 and about 20 Tavily
   calls.
4. **Whether to share the corrections with the note's author:** theory note §2, x01's certified
   witnesses and the x04 audit.
5. **Merge:** push `exp/energy-pricing-model` and open a PR. Nothing is pushed yet.

No long runs are pending, and nothing new is registered until you decide.

## Reproducibility
- **Clean runs.** Every run used a clean `git worktree` at its implementation commit, because the
  main tree carries your uncommitted AGENTS.md edit. Each run wrote to the main tree's `results/`.
- **Manifests** record the commit, the dirty flag (false for all reported runs), the uv.lock sha256,
  the platform, the CPU, the memory and the argv.
- **Commands** (in `energy-pricing-model/experiments/`):
  - `uv sync --locked`;
  - `uv run --locked pytest -q` (102 tests);
  - `uv run --locked python x0N-…/run.py --out <results dir>`.
  - x06 also needs `set -a; . ./.env; set +a`.
- **Independent checks:**
  - x01: `recheck_witnesses.py`, 11,328 of 11,328 verified;
  - x02: a Gaussian closed form;
  - x03: HiGHS on 57,600 half-hours;
  - x04: quad against Gauss–Hermite against 10⁷ Monte Carlo draws;
  - x05: IPS truth, plus the positive and negative controls;
  - x06: `recheck.py`, where every verdict reproduces.
- **Spend** (x06 only):
  - model credit: $0.073 in the reported run, $0.033 in the invalid attempt and $0.002 in smoke
    runs, i.e. about $0.11 in total;
  - Tavily: 149 calls in total.
- **Wall time:** x01 97 s, x02 184 s, x03 147 s, x04 6 s, x05 100 s, x06 458 s.
