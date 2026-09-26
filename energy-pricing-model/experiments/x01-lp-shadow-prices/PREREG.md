# x01-lp-shadow-prices — pre-registration

- **Registered:** 2026-09-26, in the commit that adds this file, before any code for it exists.
- **Plan:** `energy-pricing-model/plans/stage_b_plan.md`, the x01 entry.
- **Theory / Inputs:**
  - `plans/theory-rosso-claims.md`, §2.1–2.2 and claims 14–21;
  - `plans/toy_v1_spec.md`, cited at 26abb27;
  - the note, `docs/tem-rosso-pricing-model-v1.md` §3, committed in b9291cd.
  - There are no input runs.

## Why this design
The note's §3 builds pricing on one LP per half-hour and its shadow prices. Three of its statements
about the duals disagree with LP duality (theory note §2.1):
- "μ = 0 for inframarginal assets";
- μ = λ − π in the generation-scarce regime;
- the regime being set by ΣG.

Its operational rule is to "re-solve with and without whenever Q_j exceeds ~2% of book volume". That
is a claim about how large the first-order (dual) error is, and it is testable in the toy book.
- **Part A** tests the statements on random half-hour LPs, against exact certificates and an
  independent solver.
- **Part B** tests the 2% rule in toy v1.

## Definitions
- **Half-hour LP.** max Σ_{i,a} (λ − π_a)·m_ia subject to:
  - Σ_a m_ia ≤ c_i, with dual ν_i, where c_i = min(D_i, κ);
  - Σ_i m_ia ≤ G_a, with dual μ_a;
  - m ≥ 0.
- **Shorthands:** C = Σ c_i and G⁺ = Σ_{π_a<λ} G_a.
- **Greedy.** Fill min(G⁺, C) from assets with π_a < λ, in ascending order of π. Ties are broken by
  index.
- **Table duals** (theory note §2.1):
  - If G⁺ ≤ C: ν = 0 and μ_a = (λ − π_a)⁺.
  - Otherwise, let k be the first asset in merit order at which the cumulative profitable
    generation reaches C. Then ν_i = λ − π_k for every i, and μ_a = (π_k − π_a)⁺.
- **Degenerate instance:** any of the following.
  - G⁺ = C exactly.
  - A cumulative merit sum equals C exactly.
  - Two assets have equal π.
  - Some π_a equals λ.
  - The regime inequalities hold with a gap below 1e-9·max(1, C).
- **Note statements** (on nondegenerate instances):
  - **S1:** demand-scarce, with an asset used in full at π_a < π_k: the note says μ_a = 0.
  - **S2:** generation-scarce, with an asset at π_a > λ: the note says μ_a = λ − π_a.
  - **S3:** the regime is classed by ΣG against C, instead of by G⁺.
- **Part B.** Book B_N on pool P71 (toy v1, base config).
  - The prospect d = qN × (a fresh site of archetype a), so it is q of the book's volume.
  - Per scenario: dual_s = ν̄·Σ_t 1{G > C_N}·d_t and exact_s = ν̄·Σ_t min(d_t, (G − C_N)⁺).
  - rel_err(N,a,q) = Σ_s (dual_s − exact_s) / Σ_s exact_s.
  - err_£ = Σ_s (dual_s − exact_s) / Σ_s Σ_t d_t, in £ per MWh of the prospect.
  - e* is the largest rel_err at q = 2% over the 18 cells N × a.
  - q*_5%(N,a) is the largest q with rel_err ≤ 5%, interpolated in log q. It is censored at ≥ 16%.

## Hypotheses
- **`dual-2pct-rule` (primary).**
  - H1 (the note): rel_err(N,a,2%) ≤ 5% in all 18 cells, N ∈ {10,20,30,40,60,100} ×
    {office, 24/7, evening}, at the base config.
  - H0: some cell exceeds 5%.
- **`note-dual-statements` (secondary).**
  - H1 (the note): S1 and S2 hold on every eligible Part A instance, and S3 never misclassifies.
  - H0: counterexamples exist.
  - Decided without CIs: it is a count of certified counterexamples.
- **Descriptive:**
  - `dual-error-linear`: rel_err(8%) / rel_err(2%) per cell.
  - `dual-error-gbp`: err_£ at 2%, against the §7.4 markups of £3.86 and £9.41/MWh.
  - `safe-size-curve`: q*_5%(N,a).
  - `rule-robustness`: the share of the 40 Latin-hypercube cells of toy v1 §8 in which H1 holds by
    point estimate.

## Method
**Scope of the claim.**
- Part A: random single-half-hour LPs drawn as below.
- Part B: toy v1 (a reconstruction of the note's §7, not its code), uniform π, one price level.
- κ is inert in Part B, so the cap is exercised only in Part A.

**Part A.**
- 5,000 random instances. Instance k uses `SeedSequence([20260926, 101, k])`.
  - Customer count n_c and asset count n_a are each drawn uniformly from {1,2,3,5,10,20}.
  - Demand D_i ~ LogNormal(0,1) MWh, capped at κ = 2.5.
  - Generation: g ~ LogUniform(0.25, 4), and G = g·C·Dirichlet(1).
  - Premiums π_a ~ U(0,60), with λ = 45.
- 500 degenerate instances, 125 of each of four kinds:
  - G⁺ = C;
  - a merit sum equal to C;
  - duplicate π;
  - π_a = λ.

  They are built from multiples of 1/8, so the ties are exact in floating point. Instance j uses
  `SeedSequence([20260926, 103, j])`.
- Every instance is solved three ways:
  - greedy, in floats and in exact rationals (`fractions.Fraction`);
  - HiGHS through `scipy.optimize.linprog(method="highs-ds")`, with a time limit of 10 s per LP.
    Its duals are the negated `ineqlin.marginals`.

**Part B.**
- Toy v1 with S = 120. The configs are the base and the 40 Latin-hypercube cells.
- q ∈ {0.25, 0.5, 1, 2, 4, 8, 16}%.
- Bootstrap: B = 2,000 resamples of scenarios, with seed `[20260926, 102]`. A cell's CI is the
  2.5–97.5 percentile interval. The CI for e* uses the maximum over cells within each resample.

**Resources.**
- 4 workers.
- Caps: 5 min per config and 45 min of wall time.
- A solve that does not report optimal is censored. More than 0.1% censored makes the run `invalid`.

**Registered config** (`config.toml` must equal this):

<!-- registered config: config.toml -->
```toml
[experiment]
name = "x01-lp-shadow-prices"
seed = 20260926

[part_a]
instances = 5000
degenerate_per_kind = 125
customer_counts = [1, 2, 3, 5, 10, 20]
asset_counts = [1, 2, 3, 5, 10, 20]
demand_lognormal_sigma = 1.0
gen_ratio_range = [0.25, 4.0]
premium_range = [0.0, 60.0]
lam = 45.0
kappa = 2.5
lp_time_limit_s = 10.0
dual_tol = 1e-6
objective_rtol = 1e-9

[part_b]
toy_spec = "plans/toy_v1_spec.md@26abb27"
scenarios = 120
books = [10, 20, 30, 40, 60, 100]
q_percent = [0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0]
rule_q_percent = 2.0
tolerance = 0.05
bootstrap = 2000
lhs_cells = 40
highs_check_halfhours = 200
highs_check_scenarios = 3
highs_check_q_percent = [2.0, 16.0]

[run]
workers = 4
config_cap_s = 300
wall_cap_s = 2700
max_censored_fraction = 0.001
```

## Controls
- **C1, exact certificate (the independent checker).** On every Part A instance, in exact rationals:
  - the greedy primal is feasible;
  - the table duals are feasible (ν, μ ≥ 0 and ν_i + μ_a ≥ λ − π_a);
  - the primal and dual objectives are equal.
- **C2, agreement with HiGHS.**
  - Objectives agree within a relative 1e-9.
  - On nondegenerate instances, the HiGHS duals equal the table duals within 1e-6.
  - On degenerate instances, the HiGHS duals are feasible and reach the optimal objective, within
    1e-9 relative.
- **C3, negative control.** On every instance, a planted wrong dual (ν of customer 0 raised by 1)
  fails the C1 certificate.
- **C4, the ΔV identity against an independent LP.** On 200 sampled half-hours × 3 scenarios × every
  (N, a) cell × q ∈ {2, 16}%:
  - Solve an LP with one variable per site (N sites plus the prospect, each capped at κ), with the
    two assets π = 10, by HiGHS, with and without the prospect.
  - The difference in value equals ν̄·min(d, (G − C)⁺) within 1e-7·max(1, value).
- **C5, concavity.** dual_s ≥ exact_s for every scenario, cell and q.
- **C6, error identity.** dual_s − exact_s equals ν̄·Σ_t 1{G > C}·(d − (G − C))⁺ within a relative
  1e-9.
- **C7, calibration.** The calibration control of toy v1 §8 passes for the base config.

Any failure makes the experiment `invalid`.

## Outcome classes
The first matching class wins. The table decides `dual-2pct-rule`. A "failing cell" is one whose CI
lower bound is above 5%.

| Class | Condition | Action |
|---|---|---|
| `invalid` | any control fails, or more than 0.1% of solves are censored | debug, record a deviation, re-run |
| `rule-holds` | CI upper(e*) ≤ 5% | run x02; carry the result to G1 |
| `rule-fails-saturated` | CI lower(e*) > 5%, every failing cell has N ≥ 60, and every cell with N ≤ 40 has CI upper ≤ 5% | run x02; the G1 report drafts x01a (a surplus-scaled re-solve rule), unregistered |
| `rule-fails-broadly` | CI lower(e*) > 5%, and some failing cell has N ≤ 40 | run x02; G1 flags the rule as unsafe |
| `inconclusive` | otherwise | run x02; G1 decides whether to register a larger S |

`note-dual-statements` is `fails` if any S1, S2 or S3 counterexample passes C1 and C2. Otherwise it
is `holds`.

## Predictions
These are planning inputs from the theory note §4. They come from a pilot on a toy close to v1, so
they are not results.
- **Controls.** C1–C3 pass (99%). They check a theorem.
- **`note-dual-statements`: `fails` (99%).**
  - S1 fails on 100% of eligible instances (99%).
  - S2 fails on 100% of eligible instances (99%).
  - S3 misclassifies 8–18% of nondegenerate instances (80%).
- **`dual-2pct-rule`, by class:**
  - `rule-fails-saturated` 50%;
  - `inconclusive` 25%;
  - `rule-holds` 20%;
  - `rule-fails-broadly` 5%.

  The pilot's rel_err at 2% (%, office / 24/7 / evening):

  | N | office | 24/7 | evening |
  |---|---|---|---|
  | 10 | 0.27 | 0.31 | 0.70 |
  | 20 | 0.74 | 0.73 | 1.29 |
  | 30 | 1.25 | 1.12 | 1.61 |
  | 40 | 1.74 | 1.54 | 1.42 |
  | 60 | 2.60 | 2.25 | 1.42 |
  | 100 | 5.29 | 3.77 | 2.49 |

  The worst cell sits on the 5% line.
- **Descriptive:**
  - the linearity ratio lies in [3.6, 4.6] in every cell (80%);
  - err_£ at 2% is ≤ £0.25/MWh in every cell (85%);
  - q*_5% at N = 10 is censored at ≥ 16% (80%);
  - H1 holds in 25–60% of the Latin-hypercube cells (55%).

## Outputs
Each run writes `energy-pricing-model/experiments/x01-lp-shadow-prices/results/<UTC run-id>/`:
- `manifest.json`;
- `config.toml`;
- `records.jsonl`, with one record per Part A instance and one per Part B cell × q × config;
- `summary.json`, holding the class, e* with its CI, the S1–S3 counts and the descriptive values;
- `checkpoints/`;
- `witnesses.jsonl`, holding the certified S1–S3 counterexamples in exact rationals.

The writeup goes to `energy-pricing-model/writeup_generated/x01-lp-shadow-prices.md`.

## Limitations, stated in advance
- Part B is toy v1, a reconstruction. The 2% rule is tested in one family of synthetic books with
  one price level, not on tem's data.
- The Part A instance distribution is arbitrary. The S3 rate describes that distribution, not tem's
  books; S1 and S2 are statements about every instance.
- The 5% tolerance is this experiment's reading of "small". The note gives no number.
- The per-customer cap never binds in the toy. Cap effects are covered only by Part A.

## Deviations
(none yet)
