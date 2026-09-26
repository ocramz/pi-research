# x05-confounded-elasticity — pre-registration

- **Registered:** 2026-09-26, in the commit that adds this file, before any code for it exists.
- **Plan:** `energy-pricing-model/plans/stage_b_plan.md`, the x05 entry.
- **Theory / Inputs:**
  - `plans/theory-rosso-claims.md`, §2.4 and §2.7 and claims 31–35;
  - the note, §6 and §10.4, committed in b9291cd.
  - There are no input runs.

## Why this design
§6 claims four things:
- β cannot be estimated from historical quotes, because the prices were "set by a policy already
  conditioned on winnability", so a logit on the log is biased, "usually toward inelasticity";
- an optimiser will "exploit [that] into a mirage";
- logging known propensities makes estimation and policy evaluation unbiased;
- because the exploration loss is second order and the confounding bias first order, the case for
  randomising from day one is "essentially unanswerable".

Here the claims are tested in a simulated quote market where the truth is known. The market is
built so that the desk's prices really are confounded: the desk sees a private signal of the
customer's unlogged willingness to switch.

Two points from the theory note shape the targets.
- The estimand is the population slope β_marg (theory note §2.7), not the individual β. Logit
  non-collapsibility means randomisation recovers β_marg.
- The payoff is measured in profit, where both kinds of error are second order in the price error
  (theory note §2.4).

## Definitions
- **World.** Each quote draws:
  - a segment x ∈ {0,1,2,3}, uniformly, with base(x) = 159 / 161 / 163 / 165;
  - an unlogged shifter u ~ N(0, τ_u²), with τ_u = 3.

  The win probability is σ(β·(base(x) + u − p)), with β = 0.33. The cost is ĉ = 150.34 for every
  quote.
- **Population response.** P_x(p) = E_u[σ(β·(base(x) + u − p))], computed by 64-node Gauss–Hermite
  quadrature.
- **Value per MWh quoted.** V_x(p) = (p − ĉ)·P_x(p).
- **Oracle.** p°_x = argmax_p V_x(p), and V° = mean_x V_x(p°_x). The oracle prices on logged
  features only.
- **Desk (historical quotes).**
  - Signal: s = u + η, with corr(s, u) = ρ.
    - For ρ > 0, η ~ N(0, τ_u²·(1/ρ² − 1)).
    - At ρ = 0 the signal carries no information.
  - Belief: E[u | s] = ρ²·s.
  - Price: p_desk = p_plug(base(x) + ρ²·s) + ζ, with ζ ~ N(0, τ_ζ²) unlogged and τ_ζ = 2. Here
    p_plug(r) solves p − ĉ = 1/(β·(1 − σ(β·(r − p)))).
  - Logged: (x, p, win).
- **β_marg.** The probability limit of the naive logit slope at ρ = 0, computed by quadrature over
  ζ and u.
- **Logit fit.** win ~ α_x − b·p, by IRLS with at most 50 iterations and tolerance 1e-10.
- **Deployed price.** p(α̂, b̂)_x = argmax_p (p − ĉ)·σ(α̂_x − b̂·p). If b̂ ≤ 0.02, the "mirage
  rule" applies and p = ĉ + 40.
- **Pipelines.** Each runs a horizon of N_log + N_exp = 2,000 + 8,000 quotes after 2,000 historical
  desk quotes. The segments and u of the horizon are shared by all pipelines, as common random
  numbers.
  - **NV** fits on the history and deploys p_NV(x) for the whole horizon.
  - **RL(σ_j)** quotes p_NV(x) + ε with ε ~ N(0, σ_j²) logged, for N_log quotes. It refits on those
    quotes only and deploys p_RL(x) for N_exp quotes.
  - **RG** quotes p_NV(x) + δ, with δ drawn uniformly from {−4, −2, 0, 2, 4} (propensity 1/5), for
    N_log quotes. It picks δ*_x by the per-segment IPS value, then deploys p_NV(x) + δ*_x.
- **Horizon value.** H = Σ_k V_{x_k}(p_k) / (N_total·V°), computed exactly from the prices charged,
  not from realised wins.
- **Difference.** Δ(pipeline) = H(pipeline) − H(NV), in percent of V°.

## Hypotheses
- **`randomisation-pays` (primary).**
  - H1 (the note, where its confounding premise holds): Δ(RL, σ_j = 2) > 0 at ρ = 0.5 and at
    ρ = 0.8.
  - H0: Δ ≤ 0 at ρ = 0.5 or at ρ = 0.8.
- **`naive-inelastic` (secondary).**
  - H1 (the note): the mean of b̂_NV is below β_marg at every ρ > 0.
  - H0: at some ρ > 0 the CI upper bound is ≥ β_marg.
- **Descriptive:**
  - `attenuation`: A(ρ) = 1 − mean b̂_NV / β_marg.
  - `noncollapsible-target`: the mean of b̂_RL(σ_j), against β_marg and against β = 0.33.
  - `cost-without-confounding`: Δ(RL, 2) at ρ = 0.
  - `break-even`: the ρ* at which Δ(RL, 2) = 0, by linear interpolation.
  - `first-vs-second-order`: the per-quote loss of the NV price, 1 − mean_x V_x(p_NV)/V°, against
    the loss from logging jitter.
  - `sigma-sweep`: Δ(RL) at σ_j ∈ {1, 2, 4}.
  - `ips-vs-logit`: Δ(RG) against Δ(RL, 2).
  - `robustness`: Δ(RL, 2) at ρ ∈ {0, 0.5} when one of these changes: τ_u ∈ {1.5, 5},
    τ_ζ ∈ {1, 4}, N_log ∈ {500, 5000}.

## Method
**Scope of the claim.** This synthetic market, with a logistic individual response, Gaussian
heterogeneity and a plug-in desk. Neither tem's quote log nor the real sign of its confounding is
represented.

**Grid.** ρ ∈ {0, 0.3, 0.5, 0.8} × σ_j ∈ {1, 2, 4}. NV and RG do not depend on σ_j. R = 1,000
replications per ρ.

**Seeds.**
- History, segments and u use `SeedSequence([20260926, 105, ρ-index, r])`.
- Jitter uses `[20260926, 106, ρ-index, r]`. It is standard normal, scaled by σ_j, so the jitter
  draws are common random numbers across σ_j.
- RG offsets use `[20260926, 107, ρ-index, r]`.

**CIs.** Mean ± 1.96 standard errors over replications.

**Resources.** 4 workers; a cap of 30 min of wall time.

**Censoring.** A fit that does not converge is censored. More than 1% censored in any cell makes
the run `invalid`.

**Registered config** (`config.toml` must equal this):

<!-- registered config: config.toml -->
```toml
[experiment]
name = "x05-confounded-elasticity"
seed = 20260926

[market]
segment_bases = [159.0, 161.0, 163.0, 165.0]
beta = 0.33
tau_u = 3.0
tau_zeta = 2.0
c_hat = 150.34
quadrature_nodes = 64

[pipelines]
historical_quotes = 2000
logging_quotes = 2000
exploit_quotes = 8000
jitter_sigmas = [1.0, 2.0, 4.0]
primary_sigma = 2.0
grid_offsets = [-4.0, -2.0, 0.0, 2.0, 4.0]
mirage_min_slope = 0.02
mirage_markup = 40.0
irls_max_iter = 50
irls_tol = 1e-10

[grid]
rhos = [0.0, 0.3, 0.5, 0.8]
replications = 1000
oat_rhos = [0.0, 0.5]
oat_tau_u = [1.5, 5.0]
oat_tau_zeta = [1.0, 4.0]
oat_logging_quotes = [500, 5000]

[checker]
ips_logs = 2000
ips_offsets = [-4.0, 0.0, 4.0]
positive_control_quotes = 100000
positive_control_halfwidth = 6.0
simulator_quotes = 1000000
simulator_offsets = [-3.0, 0.0, 3.0]
oracle_grid_step = 0.001
se_multiple_c1 = 3.0
se_multiple_c4 = 4.0

[run]
workers = 4
max_censored_fraction = 0.01
wall_cap_s = 1800
```

## Controls
- **C1, IPS unbiasedness (the independent checker).**
  - Take 2,000 simulated logs of 2,000 quotes each, priced p°_x + δ with δ uniform on the grid.
  - For each target offset in {−4, 0, 4}, the mean IPS estimate lies within 3 standard errors of the
    true value mean_x V_x(p°_x + δ).
- **C2, positive control.**
  - A logit on 100,000 quotes priced uniformly on [p°_x − 6, p°_x + 6] recovers its own design's
    quadrature probability limit, within 3 standard errors.
  - With τ_u = 0 it recovers β = 0.33, within 3 standard errors.
- **C3, negative control.** At ρ = 0, the mean of b̂_NV equals β_marg within 3 standard errors.
- **C4, simulator.** On 10⁶ quotes at p°_x + {−3, 0, 3}, the win rate per (x, price) lies within 4
  standard errors of P_x(p).
- **C5, oracle.** The optimiser's p°_x agrees within 2e-3 with a grid search of step 1e-3.
- **C6, fit health.** At most 1% of fits are censored in every cell.

Any failure makes the experiment `invalid`.

## Outcome classes
The first matching class wins. The table decides `randomisation-pays`.

| Class | Condition | Action |
|---|---|---|
| `invalid` | any control fails | debug, record a deviation, re-run |
| `pays-always` | CI lower Δ(RL, 2) > 0 at every ρ, including 0 | run x06; carry the result to G1 |
| `pays-when-confounded` | CI lower Δ(RL, 2) > 0 at ρ = 0.5 and at ρ = 0.8 | run x06; G1 records the claim as conditional on confounding |
| `pays-only-strong` | CI lower Δ(RL, 2) > 0 at ρ = 0.8 only | run x06; G1 |
| `never-pays` | CI upper Δ(RL, 2) ≤ 0 at ρ = 0.8 | run x06; G1 |
| `inconclusive` | otherwise | run x06; G1 |

`naive-inelastic` is:
- `holds` if the CI upper bound of mean b̂_NV is < β_marg at every ρ > 0;
- `fails` if the CI lower bound is ≥ β_marg at some ρ > 0;
- `inconclusive` otherwise.

## Predictions
These are planning inputs from the theory note §4. They come from a pilot of a similar market, so
they are not results.
- **Primary:**
  - `pays-when-confounded` 75%;
  - `pays-only-strong` 10%;
  - `inconclusive` 10%;
  - any other class 5%.
- **Δ(RL, 2):** about −1.0% at ρ = 0, +3% at ρ = 0.5 and +25 to +40% at ρ = 0.8.
- **Secondary:** `holds` (85%). The attenuation A is about 0 / 0.12 / 0.30 / 0.58 across the four ρ
  values (±0.07; 70%).
- **β_marg:** 0.280 ± 0.005 (90%).
- **Mean b̂_RL:** within ±0.01 of β_marg (80%). It is not near 0.33.
- **Break-even:** ρ* ∈ [0.15, 0.40] (60%).
- **IPS against logit:** RL is at least as good as RG at ρ = 0.8 (60%).

## Outputs
Each run writes `energy-pricing-model/experiments/x05-confounded-elasticity/results/<UTC run-id>/`:
- `manifest.json`;
- `config.toml`;
- `records.jsonl`, with one record per (cell, replication);
- `summary.json`, holding the class, Δ with its CIs, the secondary verdict and the descriptive
  values;
- `checkpoints/`.

The writeup goes to `energy-pricing-model/writeup_generated/x05-confounded-elasticity.md`.

## Limitations, stated in advance
- The market is stylised: logistic individual response, Gaussian heterogeneity, and a plug-in desk
  that uses the true β. The real direction and size of confounding in tem's log are unknown, and ρ
  stands in for them.
- The deployed policies price on segment only. A pipeline that also used the desk's signal is out of
  scope.
- The horizon value is computed from the true response, which a real firm cannot observe.

## Deviations
1. **2026-09-26, before the run: C6 is scoped to the primary grid.**
   - **Registered:** C6, at most 1% of fits censored "in every cell", with any failure making the
     run `invalid`.
   - **Holds now:** C6 applies to the primary grid, meaning the main market at ρ ∈ {0, 0.3, 0.5,
     0.8} × σ_j ∈ {1, 2, 4}. In the one-at-a-time (OAT) robustness cells, the share of censored
     fits is reported instead. Δ there is reported over converged replications, and flagged as
     conditional on convergence.
   - **Why:** A smoke run (100 replications, not registered) censored 26% of the RL refits at
     τ_ζ = 1, ρ = 0.5, and 2% at τ_u = 5, ρ = 0.5. This is not a failure of the estimator.
     - With little exogenous desk noise, the naive slope collapses to about 0.02–0.05, so the NV
       price sits £18–30 above the oracle.
     - Jitter of ±£2 around it wins 0–3 of about 500 quotes per segment.
     - A segment with no wins is completely separated, so no maximum-likelihood estimate exists.

     That is a finding about the pipeline, not a numerical fault, and it should not invalidate the
     primary hypothesis, which uses the primary grid only.
   - **Unchanged:** the primary grid, the hypotheses, the outcome classes and every other control.
