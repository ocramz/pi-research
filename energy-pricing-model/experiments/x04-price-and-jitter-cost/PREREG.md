# x04-price-and-jitter-cost — pre-registration

- **Registered:** 2026-09-26, in the commit that adds this file, before any code for it exists.
- **Plan:** `energy-pricing-model/plans/stage_b_plan.md`, the x04 entry.
- **Theory / Inputs:**
  - `plans/theory-rosso-claims.md`, §2.4–2.5 and claims 26–30, 33, 34 and 41–44;
  - the note, §5, §6, §7.4 and §7.5, committed in b9291cd.
  - There are no input runs.

## Why this design
§6 argues that exploration is cheap: at the optimum Π' = 0, so jitter costs O(σ²). It then quotes
"Measured in §7: £1/MWh of jitter costs 1.0% of expected margin". §7.5 lists 1.0 / 4.0 / 18.1% at
σ = 1 / 2 / 4, with "clean quadratic scaling, as the envelope argument predicts".

Every input is given in §7.4, so the claim can be audited exactly.

The planning calculation (theory note §4) has already found that the figures match symmetric jitter
at the γ = 60% pass-through price. They do not match the unconstrained optimum the text refers to.
This experiment makes that finding certain, with independent numerical checks, a committed artefact
and registered tolerances.

It also audits:
- the §7.4 table;
- the markup statics in §5;
- the cost of jitter that respects the pass-through cap.

## Definitions
- **Inputs (§7.4).**
  - Gross cost 157 = 78 + 34 + 45.
  - Credit ν̄·s̄ = 35 × 0.276 = 9.66.
  - Risk loading φ·σ_c = 0.5 × 6 = 3.
  - ĉ = 150.34 with the match, and 160 without it.
  - β = 0.33, p_ref = 162, Q = 250 MWh/yr, γ = 0.6.
- **Model.** P(p) = σ(β(p_ref − p)) and Π(p) = Q·P(p)·(p − ĉ).
- **Prices.**
  - p* is the root of g(p) = p − ĉ − 1/(β(1 − P(p))), found by bisection on [ĉ, ĉ + 100] to 1e-12.
  - p_cap(γ) = 160 − 9.66·γ.
  - The three policies are: unconstrained p*; pass-through min(p*, p_cap(0.6)); and no match, which
    is p* with ĉ = 160.
- **Loss.** L(p₀, σ, design) = 1 − E[Π(p₀ + ε)] / Π(p₀). Two designs:
  - symmetric: ε ~ N(0, σ²);
  - cap-respecting: ε = −σ·|Z|, i.e. half-normal and never above p₀.
- **σ** ∈ {0.25, 0.5, 1, 2, 4}.
- **Match rule.** A (price, design) pair matches §7.5 if L at σ = 1 / 2 / 4 lies within ±0.15 /
  ±0.3 / ±0.6 pp of 1.0 / 4.0 / 18.1%.

## Hypotheses
- **`jitter-cost-at-optimum` (primary).**
  - H1 (the note, §6 and §7.5): symmetric jitter at the unconstrained p* matches §7.5.
  - H0: it does not.
- **`s74-reproduction` (secondary).** The 11 numeric cells of the §7.4 policy table: price, win %,
  markup and margin, for three rows. The no-match markup is not printed, so it is not tested.
  - `exact`: every cell is within display precision: ±£0.005 on price and markup, ±0.05 pp on win,
    ±£0.5 on margin.
  - `rounding`: every cell is within ±£0.02, ±0.1 pp and ±0.5%, but not every cell is exact.
  - `mismatch`: otherwise.
- **Descriptive:**
  - `envelope-second-order`: L(p*, σ)/σ² at σ ∈ {0.25, 0.5}, against ½β²(1 − P*).
  - `cap-respecting-first-order`: cap-respecting L(p_cap, σ)/σ at σ ∈ {0.25, 0.5, 1}, against
    √(2/π)·Π'(p_cap)/Π(p_cap).
  - `quadratic-scaling`: L(σ)/L(1) at σ = 2 and 4, for symmetric jitter at p* and at p_cap, against
    4 and 16.
  - `markup-beta-statics`: the sign of ∂m*/∂β on the grid ĉ × β below, and the share of the grid
    where "markup falls as β rises" holds.
  - `rent-split`: the customer's saving p*_nomatch − p*_match, against tem's markup gain
    m*_match − m*_nomatch.
  - `margin-ratio`: the unconstrained and pass-through margins, each divided by the no-match margin,
    against "roughly doubles".
  - `gamma-binding`: the smallest γ at which the cap binds.

## Method
**Scope of the claim.** The note's own model and inputs; no data. The experiment is deterministic
apart from the Monte Carlo checker.

**Primary integration.** `scipy.integrate.quad` over the normal or half-normal density, with
epsabs = epsrel = 1e-12.

**Checkers.**
- 10⁷ Monte Carlo draws, seed `[20260926, 401]`, antithetic for the symmetric design.
- For the symmetric design, 200-node Gauss–Hermite quadrature.

**Statics grid.** ĉ ∈ {130, 135, …, 160} × β ∈ {0.10, 0.15, …, 0.60}. The derivative is a central
finite difference with step 1e-6.

**Resources.** 1 worker; a cap of 10 min of wall time. There is no censoring.

**Registered config** (`config.toml` must equal this):

<!-- registered config: config.toml -->
```toml
[experiment]
name = "x04-price-and-jitter-cost"
seed = 20260926

[note]
commodity = 78.0
network = 34.0
levies = 45.0
nu_bar = 35.0
matched_share = 0.276
phi = 0.5
sigma_cost = 6.0
beta = 0.33
p_ref = 162.0
volume_mwh = 250.0
gamma = 0.6
jitter_sigmas = [1.0, 2.0, 4.0]
jitter_loss_percent = [1.0, 4.0, 18.1]
jitter_tolerance_pp = [0.15, 0.3, 0.6]

[note.table_7_4.unconstrained]
price = 159.74
win_percent = 67.8
markup = 9.40
margin_gbp = 1593.0

[note.table_7_4.pass_through]
price = 154.19
win_percent = 92.9
markup = 3.85
margin_gbp = 894.0

[note.table_7_4.no_match]
price = 164.39
win_percent = 31.2
margin_gbp = 343.0

[analysis]
sigmas = [0.25, 0.5, 1.0, 2.0, 4.0]
exact_tolerance = { price = 0.005, markup = 0.005, win_pp = 0.05, margin_gbp = 0.5 }
rounding_tolerance = { price = 0.02, markup = 0.02, win_pp = 0.1, margin_rel = 0.005 }
statics_c_hat = [130.0, 135.0, 140.0, 145.0, 150.0, 155.0, 160.0]
statics_beta = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]

[checker]
mc_draws = 10000000
gh_nodes = 200
grid_step = 0.0001
fd_step = 0.001
statics_fd_step = 0.000001
se_multiple = 4.0

[run]
workers = 1
wall_cap_s = 600
```

## Controls
- **C1, the optimum.**
  - p* from bisection agrees within 2e-4 with a grid search, step 1e-4 over [ĉ, ĉ + 50].
  - log Π is concave on that grid: every second difference is < 0.
- **C2, independent integration.**
  - For every (price, σ, design) evaluated, quad agrees with Monte Carlo within 4 Monte Carlo
    standard errors.
  - For the symmetric design, quad also agrees with Gauss–Hermite within a relative 1e-9.
- **C3, curvature.** The central finite difference of Π at p*, step 1e-3, equals −β·P*·Q within a
  relative 1e-6.
- **C4, negative control.** σ = 0 gives L = 0 exactly, in both designs.
- **C5, the statics sign rule.** The finite-difference sign of ∂m*/∂β equals
  sign(β·P*·(p_ref − p*) − 1) at every grid point where |β·P*·(p_ref − p*) − 1| > 1e-3.

Any failure makes the experiment `invalid`.

## Outcome classes
The first matching class wins. The table decides `jitter-cost-at-optimum`.

| Class | Condition | Action |
|---|---|---|
| `invalid` | any control fails | debug, record a deviation, re-run |
| `note-confirmed` | symmetric jitter at p* matches §7.5 | run x05; carry the result to G1 |
| `misattributed-cap` | p* does not match, and symmetric jitter at p_cap(0.6) matches | run x05; G1 records the correct attribution, and that symmetric jitter at a binding cap breaks the cap on half of all quotes |
| `misattributed-other` | neither of the above, but one of the following matches: symmetric at the no-match price; cap-respecting at p_cap(0.6); cap-respecting at p* | run x05; G1 |
| `unexplained` | nothing matches | run x05; G1 |

## Predictions
These are planning inputs from the theory note §4, not results.
- **Primary:** `misattributed-cap` (95%).
  - Symmetric jitter at p* = 159.746: 1.71 / 6.37 / 20.65%.
  - Symmetric jitter at p_cap = 154.204: 0.96 / 4.05 / 18.00%.
- **Secondary:** `rounding` (90%). The note's 154.19 against 154.204, 894 against 897.5, and 159.74
  against 159.746.
- **Descriptive:**
  - L(p*)/σ² at σ = 0.25 is within 1% of 0.01754 (95%).
  - Cap-respecting L/σ at σ = 0.25 is 0.188 ± 0.005 (90%), and cap-respecting L at σ = 1 is about
    19.6%.
  - L(4)/L(1) is about 12.1 at p* and about 18.8 at p_cap (90%).
  - The sign rule agrees everywhere (99%).
  - "Markup falls as β rises" fails on part of the grid, for example at ĉ = 140 (95%).
  - The rent split is about £4.66 to the customer and £5.00 to tem (52%).
  - The margin ratios are 4.65× and 2.62×.
  - The cap binds for γ ≥ 2.63%.

## Outputs
Each run writes `energy-pricing-model/experiments/x04-price-and-jitter-cost/results/<UTC run-id>/`:
- `manifest.json`;
- `config.toml`;
- `records.jsonl`, with one record per (price, σ, design) and per point of the statics grid;
- `summary.json`, holding the class, the §7.4 comparison and the descriptive values.

The writeup goes to `energy-pricing-model/writeup_generated/x04-price-and-jitter-cost.md`.

## Limitations, stated in advance
- This audits the note's arithmetic within its own logistic model. It says nothing about real price
  response, β or p_ref.
- The match tolerances are this experiment's choice. They are wide enough for the note's printed
  rounding.

## Deviations
(none yet)
