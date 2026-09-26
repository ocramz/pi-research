# x03-congestion-vs-shape — pre-registration

- **Registered:** 2026-09-26, in the commit that adds this file, before any code for it exists.
- **Plan:** `energy-pricing-model/plans/stage_b_plan.md`, the x03 entry.
- **Theory / Inputs:**
  - `plans/theory-rosso-claims.md`, claims 2, 22, 23 and 37–39;
  - `plans/toy_v1_spec.md`, cited at 26abb27;
  - the note, §4, §7.1 and §7.2, committed in b9291cd.
  - There are no input runs.

## Why this design
The note's structural claims are:
- exempt-match capacity is congestible, so a prospect's value depends on the book it joins;
- "Congestion is the dominant effect" (§7.1);
- shape still matters on its own: office against evening venue is 12 pp at 40 sites, i.e.
  £4.2/MWh, "comparable in size to the entire margin" (§7.2).

Monotone decline with book size is a theorem when the book grows pointwise, so it is a control. Two
things are open:
- the relative size of the two effects, which needs a numeric definition;
- whether the shape ordering and gap hold.

## Definitions
- **Marginal matched share.** s_a(N) = Σ_s Σ_t min(d^a, (G − C_N)⁺) / Σ_s Σ_t d^a, where d^a is a
  fresh 250 MWh site of archetype a.
- **Value.** value_a(N) = 250·ν̄·s_a(N), in £ per year.
- **Book sizes and pools.** N ∈ {0, 1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100}.
  - P71 is the mixed pool, with base θ_s = 0.5.
  - P72 is 6 MW of solar only.
- **Core sizes.** N_core = {10, 20, 30, 40, 60, 100}.
- **Range and spread.**
  - range_a = max over N_core of s_a − min over N_core of s_a.
  - spread(N) = max over a of s_a(N) − min over a of s_a(N).
- **Dominance ratio.** R = min_a range_a / max_{N ∈ N_core} spread(N).
  - This is the worst-case error of the best rule that ignores congestion, divided by that of the
    best rule that ignores shape.
  - Taking the minimum over archetypes makes it conservative.

## Hypotheses
- **`congestion-dominates` (primary).** H1 (the note): R ≥ 2 in P71. H0: R < 2.
- **`shape-rank-solar` (secondary).** H1 (the note, §7.2): s_office > s_24/7 > s_evening in P72 at
  N = 20 and N = 40.
- **`shape-gap-vs-markup` (secondary).** H1 (the note, §7.2): ν̄·(s_office − s_evening) at N = 40 in
  P72 is ≥ £3.86/MWh, the smallest §7.4 markup.
- **Descriptive:**
  - `rank-reversal-71`: the first N at which s_24/7 > s_office in P71. The note says 30.
  - `solar-R`: R in P72.
  - `standalone-vs-marginal`: s_a(0) / s_a(40) in P71. This is the error of the cost-plus credit
    (§4).
  - `note-tables`: per-cell differences and RMSE against the note's tables 7.1 and 7.2, and the θ_s
    in {0.3, …, 0.7} that minimises the RMSE against 7.1.
  - `thin-vs-saturated-value`: value_office(10) and value_office(100), against the note's £7,079 and
    £163.
  - `robustness`: R in the one-at-a-time (OAT) cells, and the share of Latin-hypercube cells with
    R ≥ 2 by point estimate.

## Method
**Scope of the claim.** Toy v1, pools P71 and P72, books grown round-robin, uniform π.

**Configs.**
- the base;
- θ_s ∈ {0.3, 0.4, 0.6, 0.7}, for the fit only;
- the 21 OAT cells;
- the 40 Latin-hypercube cells;
- the 3 invariance cells.

S = 120 in each. The prospect streams are fixed, so the same prospect draw is used at every N.

**Bootstrap.** B = 2,000 resamples of scenarios, seed `[20260926, 302]`, on the base config for P71
and P72. CIs are 2.5–97.5 percentile intervals.

**Resources.** 4 workers; caps of 10 min per config and 50 min of wall time. A config that hits its
cap makes the run `invalid`.

**Registered config** (`config.toml` must equal this):

<!-- registered config: config.toml -->
```toml
[experiment]
name = "x03-congestion-vs-shape"
seed = 20260926

[toy]
spec = "plans/toy_v1_spec.md@26abb27"
scenarios = 120
books = [0, 1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100]
core_books = [10, 20, 30, 40, 60, 100]

[analysis]
dominance_threshold = 2.0
bootstrap = 2000
shape_books = [20, 40]
gap_book = 40
markup_floor_gbp = 3.86
standalone_book = 40
theta_fit = [0.3, 0.4, 0.5, 0.6, 0.7]
value_books = [10, 100]
note_values_gbp = [7079.0, 163.0]
invariance_se = 4.0

[note.table_7_1]
books = [10, 20, 30, 40, 60, 100]
office = [80.9, 57.7, 40.3, 27.6, 11.5, 1.9]
always_on = [78.3, 57.3, 40.4, 28.4, 13.0, 3.6]
evening = [70.6, 48.8, 31.4, 20.7, 8.9, 2.6]

[note.table_7_2]
books = [20, 40]
office = [43.5, 26.7]
always_on = [33.1, 21.4]
evening = [23.8, 14.7]

[checker]
highs_halfhours = 200
highs_scenarios = 3

[run]
workers = 4
config_cap_s = 600
wall_cap_s = 3000
```

## Controls
- **C1, monotonicity.** Σ_t min(d, (G − C_{N'})⁺) ≤ Σ_t min(d, (G − C_N)⁺) in every scenario, for
  every N' > N, every archetype and both pools.
- **C2, increment identity.** Σ min(G, C_{N+1}) − Σ min(G, C_N) = Σ min(c_N, (G − C_N)⁺), within a
  relative 1e-9. Here c_N is the capped demand of site N.
- **C3, HiGHS checker (independent).** On 200 sampled half-hours × 3 scenarios per (pool, N, a), an
  LP with one variable per site, solved by HiGHS, gives the prospect's matched increment. It must
  equal min(d, (G − C)⁺) within 1e-7·max(1, value).
- **C4, limits.** G ≡ 0 gives s = 0, and G ≡ 1e9 MWh gives s = 1, exactly.
- **C5, AR invariance (negative control).** For each invariance cell, |s_a(N) − s_a,base(N)| < 4
  paired bootstrap standard errors, for every a and every N ∈ N_core, in P71.
- **C6, calibration.** The calibration control of toy v1 §8 passes in every config.

Any failure makes the experiment `invalid`.

## Outcome classes
The first matching class wins. The table decides `congestion-dominates`.

| Class | Condition | Action |
|---|---|---|
| `invalid` | any control fails | debug, record a deviation, re-run |
| `congestion-dominant` | CI lower(R) ≥ 2 | run x04; carry the result to G1 |
| `congestion-larger` | CI lower(R) ≥ 1 | run x04; G1 records congestion as larger than shape, but not dominant |
| `shape-comparable` | CI upper(R) < 1 | run x04; G1 records shape as at least comparable to congestion |
| `inconclusive` | otherwise | run x04; G1 |

The two secondary hypotheses are decided as follows.
- **`shape-rank-solar`:**
  - `holds` if the CI lower bound is > 0 for all four ordered gaps: office − 24/7 and 24/7 − evening,
    at N = 20 and at N = 40;
  - `fails` if any of them has a CI upper bound < 0;
  - `inconclusive` otherwise.
- **`shape-gap-vs-markup`:**
  - `holds` if the CI lower bound of ν̄·(s_office − s_evening) at N = 40 is ≥ 3.86;
  - `fails` if its CI upper bound is < 3.86;
  - `inconclusive` otherwise.

## Predictions
These are planning inputs from the theory note §4, not results.
- **Primary:** `congestion-dominant` (90%), with R ∈ [3, 5] (70%). The pilot gives R = 3.7.
- **`shape-rank-solar`:** `holds` (90%).
  - Pilot, N = 20: 42.2 / 34.6 / 23.7%, against the note's 43.5 / 33.1 / 23.8.
  - Pilot, N = 40: 27.7 / 23.4 / 15.2%, against the note's 26.7 / 21.4 / 14.7.
- **`shape-gap-vs-markup`:** `holds` (70%), with a gap of about 12.5 pp, i.e. £4.4 ± 0.7/MWh.
- **Descriptive:**
  - solar-R ∈ [0.8, 1.8] (65%);
  - the rank reversal comes at N ∈ (60, 100], later than the note's 30 (60%);
  - s(0)/s(40) is about 3 at N = 40 (70%);
  - RMSE against table 7.1 ≤ 4 pp (60%; the pilot gives 2.95);
  - R ≥ 2 in ≥ 90% of the Latin-hypercube cells (70%).

## Outputs
Each run writes `energy-pricing-model/experiments/x03-congestion-vs-shape/results/<UTC run-id>/`:
- `manifest.json`;
- `config.toml`;
- `records.jsonl`, with one record per config × pool × N × archetype;
- `summary.json`, holding the class, R with its CI, the secondary verdicts and the descriptive
  values;
- `checkpoints/`.

The writeup goes to `energy-pricing-model/writeup_generated/x03-congestion-vs-shape.md`.

## Limitations, stated in advance
- Toy v1 is a reconstruction. The archetype shapes are stylised, and R depends on them and on the
  pool mix.
- The primary claim is decided in P71 at the base config. P72 and the grids are reported, not
  decided.
- R is this experiment's operational reading of "dominant". The note gives no metric.

## Deviations
(none yet)
