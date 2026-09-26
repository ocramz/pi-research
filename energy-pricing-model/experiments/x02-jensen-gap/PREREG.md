# x02-jensen-gap — pre-registration

- **Registered:** 2026-09-26, in the commit that adds this file, before any code for it exists.
- **Plan:** `energy-pricing-model/plans/stage_b_plan.md`, the x02 entry.
- **Theory / Inputs:**
  - `plans/theory-rosso-claims.md`, §2.2–2.3 and claims 9–13 and 40;
  - `plans/toy_v1_spec.md`, cited at 26abb27;
  - the note, §2 and §7.3, committed in b9291cd.
  - There are no input runs.

## Why this design
The note says a pipeline built on point forecasts overstates matched volume (Jensen), "and therefore
underprices". It puts the gap at "5–11% of matched volume, worst exactly where the book is best
balanced", and headlines §7.3 "peaks at balance".

Its own §7.3 table (gen/demand 1.55 / 1.04 / 0.78 / 0.52 → 10.6 / 7.3 / 4.9 / 2.9%) is largest at
the highest ratio it shows. The table does not show a peak.

The sign of the gap is a theorem, so here it is a control. What can be tested is:
- where the gap peaks along the growth curve of the book;
- how large it is;
- whether the pricing consequence the note draws ("underprices") holds for a prospect's marginal
  share.

## Definitions
- **Book and ratio.** Book B_N on pool P71 (toy v1). The ratio r(N) = 7,800 / (250·N) = 31.2/N.
- **Overstatement.** O(N) = [Σ_t min(Ḡ_t, D̄_t) − M̄] / M̄, where:
  - Ḡ_t and D̄_t are the in-sample means over scenarios of G and C_N;
  - M̄ = (1/S)·Σ_s Σ_t min(G, C_N).
- **O_an(N):** the same, with the analytic expected shapes (toy v1) in place of the in-sample means.
  Used only in C5.
- **Balance band:** B = [0.75, 1.33].
- **Peaks.**
  - r_peak is the grid ratio with the largest O.
  - A local peak is a grid point that exceeds both neighbours and has O ≥ 0.8·max O.
  - A peak at the edge of the grid is censored.
- **P_B(X):** the share of bootstrap resamples whose r_peak lies in the region X. Each resample
  recomputes Ḡ, D̄ and M̄.
- **Point-forecast share of a prospect.** For a fresh 250 MWh site of archetype a, with mean shape
  d̄:
  - s^pt_a(N) = Σ_t min(d̄_t, (Ḡ_t − D̄_t)⁺) / Σ_t d̄_t;
  - the true share is s_a(N) = Σ_s Σ_t min(d, (G − C_N)⁺) / Σ_s Σ_t d.

## Hypotheses
- **`jensen-peak-at-balance` (primary).**
  - H1 (the note): r_peak ∈ B at the base config.
  - H0: r_peak ∉ B.
- **`pointforecast-underprices` (secondary).**
  - H1 (the note, §2): s^pt_a(N) ≥ s_a(N) in every cell, N ∈ {10,20,30,40,60,100} × 3 archetypes.
  - H0: some cell has s^pt < s, i.e. the point pipeline overprices there.
- **Descriptive:**
  - `jensen-peak-vs-mix`: r_peak and the local peaks at θ_s ∈ {0, 0.25, 0.5, 0.75, 1}.
  - `jensen-magnitude`: O at N = 20/30/40/60, against the note's 10.6/7.3/4.9/2.9%. Also the range
    of O over r ∈ [0.5, 1.6], against "5–11%".
  - `jensen-balance-ratio`: O(N = 30) / max O.
  - `jensen-noise-source`: O with generation noise only, and with demand noise only.
  - `phantom-margin`: ν̄·(Σ min(Ḡ, D̄) − M̄) at N = 40, against the note's "~£10k/yr".
  - `jensen-robustness`: r_peak in the one-at-a-time (OAT) and Latin-hypercube cells of toy v1 §8,
    and the share of Latin-hypercube cells with r_peak ∈ B.

## Method
**Scope of the claim.** Toy v1, pool P71, books grown round-robin, uniform π. The claim is about the
book's aggregate gen/demand ratio, which is what the note's table uses.

**Grid.**
- N ∈ {4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 28, 30, 32, 35, 38, 40, 45, 50, 60, 70, 80, 100,
  125, 160, 200}, so r runs from 7.8 down to 0.156. S = 120.
- Configs:
  - the base;
  - θ_s ∈ {0, 1}, in addition to the OAT cells at 0.25 and 0.75;
  - "generation noise only" (s_i = s_cm = 0);
  - "demand noise only": G fixed at its analytic expected shape in every scenario;
  - the zero-noise config of C2;
  - the 21 OAT cells;
  - the 40 Latin-hypercube cells;
  - the 3 invariance cells.

**Bootstrap.**
- B = 1,000 resamples of scenarios, seed `[20260926, 202]`.
- Run on the base config for the primary hypothesis and for the secondary one.
- Paired resamples are used to compare configs.

**Resources.** 4 workers; caps of 10 min per config and 50 min of wall time. No censoring is
expected. A config that hits its cap makes the run `invalid`.

**Registered config** (`config.toml` must equal this):

<!-- registered config: config.toml -->
```toml
[experiment]
name = "x02-jensen-gap"
seed = 20260926

[toy]
spec = "plans/toy_v1_spec.md@26abb27"
scenarios = 120
books = [4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 28, 30, 32, 35, 38, 40, 45, 50, 60, 70, 80, 100, 125, 160, 200]

[analysis]
balance_band = [0.75, 1.33]
class_probability = 0.8
local_peak_fraction = 0.8
bootstrap = 1000
secondary_books = [10, 20, 30, 40, 60, 100]
magnitude_books = [20, 30, 40, 60]
note_magnitudes_percent = [10.6, 7.3, 4.9, 2.9]
note_range_percent = [5.0, 11.0]
theta_sweep = [0.0, 0.25, 0.5, 0.75, 1.0]
phantom_book = 40
note_phantom_gbp = 10000.0
finite_s_books = [20, 30, 40, 60]
finite_s_abs_pp = 0.5
finite_s_rel = 0.15
invariance_se = 4.0

[checker]
gaussian_mu_over_d = [0.5, 0.8, 1.0, 1.25, 2.0]
gaussian_sd_over_d = 0.3
gaussian_scenarios = 120
gaussian_halfhours = 1000
replications = 200
se_multiple = 4.0

[run]
workers = 4
config_cap_s = 600
wall_cap_s = 3000
```

## Controls
- **C1, in-sample Jensen.** min(Ḡ_t, D̄_t) ≥ (1/S)·Σ_s min(G, C_N) − 1e-12 at every half-hour, N and
  config.
- **C2, zero noise (negative control).** Set s_c = s_w = s_i = s_cm = 0, recalibrating η and μ_w.
  Then |O(N)| ≤ 1e-12 at every N.
- **C3, analytic checker (independent).**
  - Apply the library's gap estimator to synthetic data: G iid N(μ, σ²) with σ = 0.3·D, and a
    constant D, over S = 120 and T = 1,000, for each μ/D ∈ {0.5, 0.8, 1, 1.25, 2}.
  - Over 200 replications, the means of Σ min(Ḡ, D)/T and M̄/T each lie within 4 standard errors of
    the closed form E min(X, D) = μ − σ·φ(a) − (μ − D)·Φ(a), where a = (μ − D)/σ.
  - For Ḡ the closed form uses σ/√S.
- **C4, AR invariance (negative control).** For each invariance cell,
  |O_cell(N) − O_base(N)| < 4 paired bootstrap standard errors at every N.
- **C5, finite-S bias.** |O(N) − O_an(N)| ≤ max(0.5 pp, 0.15·O(N)) at N ∈ {20, 30, 40, 60}, base
  config.
- **C6, calibration.** The calibration control of toy v1 §8 passes in every config.

Any failure makes the experiment `invalid`.

## Outcome classes
The first matching class wins. The table decides `jensen-peak-at-balance`.

| Class | Condition | Action |
|---|---|---|
| `invalid` | any control fails | debug, record a deviation, re-run |
| `peak-at-balance` | r_peak ∈ B and P_B(B) ≥ 0.8 | run x03; carry the result to G1 |
| `peak-above-balance` | r_peak > 1.33 and P_B(r > 1.33) ≥ 0.8 | run x03; G1 records the note's "peaks at balance" as refuted in toy v1 |
| `peak-below-balance` | r_peak < 0.75 and P_B(r < 0.75) ≥ 0.8 | run x03; G1 records the note's "peaks at balance" as refuted in toy v1 |
| `multimodal` | local peaks lie both above 1.33 and below 0.75 | run x03; G1 |
| `inconclusive` | otherwise | run x03; G1 decides whether to register a larger S |

`pointforecast-underprices` is:
- `holds` if every cell's CI lower bound for s^pt − s is ≥ 0;
- `fails` if some cell's CI upper bound is < 0;
- `inconclusive` otherwise.

## Predictions
These are planning inputs from the theory note §4 (a pilot close to v1), not results.
- **Primary, by class:**
  - `peak-above-balance` 75%;
  - `multimodal` 10%;
  - `peak-at-balance` 10%;
  - `inconclusive` 5%.
  - The pilot has O peaking near r ≈ 2.6 at 12.9%.
- **At the base config:**
  - r_peak ∈ [1.5, 2.7] (70%);
  - max O ∈ [10, 15]% (70%);
  - O(30) / max O ∈ [0.65, 0.95] (70%).
- **Across the pool mix:**
  - wind only: r_peak ∈ [1.0, 1.6] (65%);
  - θ_s = 0.75: multimodal (55%);
  - θ_s = 1: r_peak ≤ 0.5 (75%).
- **Magnitudes** at N = 20/30/40/60: 9–14, 7–11, 5.5–9 and 4.5–8% (65%). The model will not match
  the note's low-r values.
- **Noise source:** demand noise alone gives O ≤ 0.5% at every N (90%).
- **Secondary:** `fails` (90%). In the pilot, s^pt − s is +13 to +20 pp at N = 10 and −1.5 to −2.9 pp
  at N = 100.
- **Phantom margin** at N = 40: £12–17k/yr (65%).
- **Robustness:** r_peak ∈ B in ≤ 25% of the Latin-hypercube cells (70%).

## Outputs
Each run writes `energy-pricing-model/experiments/x02-jensen-gap/results/<UTC run-id>/`:
- `manifest.json`;
- `config.toml`;
- `records.jsonl`, with one record per config × N;
- `summary.json`, holding the class, r_peak with P_B, the secondary verdict and the descriptive
  values;
- `checkpoints/`.

The writeup goes to `energy-pricing-model/writeup_generated/x02-jensen-gap.md`.

## Limitations, stated in advance
- Toy v1 is a reconstruction, and the pool mix drives where the peak falls. The primary claim is
  therefore decided at the base mix θ_s = 0.5 and reported across θ_s. It is not a claim about
  tem's pool.
- Demand in toy v1 is only weakly coupled to weather (ρ_DG ∈ [−0.3, 0.3]). The note's "dominant
  coupling" is not represented.
- "Balance" is taken as the aggregate annual ratio, as in the note's table. Balance half-hour by
  half-hour is a different quantity.

## Deviations
(none yet)
