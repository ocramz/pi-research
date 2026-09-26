# x05 — Confounded elasticity and whether randomised pricing pays

- **PREREG:** `energy-pricing-model/experiments/x05-confounded-elasticity/PREREG.md`, registered in
  222aa9e.
- **Deviations:** one, made before the run. Deviation 1 (2026-09-26) scopes C6 (fit health) to the
  primary grid; the one-at-a-time robustness cells report their share of censored fits instead. See
  Deviations below.
- **Code:**
  - `experiments/lib/python/epmlib/`: `elasticity.py`, `pricing.py` (`optimal_price_vec`) and
    `xp/x05_confounded_elasticity.py`;
  - `x05-confounded-elasticity/run.py`, `config.toml`.
- **Run:** `x05-confounded-elasticity/results/20260926T130201Z/`, at commit 13f9d09, from a clean
  worktree (`git_dirty` false at the start and the end). 4 workers; 100 s of wall time; 343 CPU-s in
  the units; 16,000 replications.

## Verdict

| Class | Result |
|---|---|
| `randomisation-pays` (primary) | **`pays-when-confounded`**. Δ(RL, σ_j = £2) is +2.89% of V° at ρ = 0.5 (CI 2.69–3.10) and +31.7% at ρ = 0.8 (CI 30.9–32.6). Without confounding it costs: −0.99% at ρ = 0 and −0.47% at ρ = 0.3. |
| `naive-inelastic` (secondary) | **`holds`**. At every ρ > 0 the mean naive slope lies below β_marg = 0.2776: 0.245, 0.197 and 0.119 at ρ = 0.3, 0.5 and 0.8, with CI upper bounds below β_marg. |

**Controls.** All pass.

| Control | Result |
|---|---|
| C1, IPS unbiasedness | \|z\| ≤ 1.7 for the three target offsets |
| C2, positive control | random prices recover their design's probability limit (z = −0.10), and β = 0.33 when τ_u = 0 (z = −2.05) |
| C3, negative control | at ρ = 0 the mean naive slope is 0.2790, against β_marg 0.2776 (within 3 SE) |
| C4, simulator | the win rates match P_x(p) (\|z\| ≤ 1.4) |
| C5, oracle | matches the grid |
| C6, fit health | 0% censored on the primary grid |

- **Censoring in the robustness cells (Deviation 1):** 26.7% of the RL refits at τ_ζ = 1, ρ = 0.5,
  and 0.8% at τ_u = 5, ρ = 0.5. Every other cell has none.
- **Vacuous passes:** none.

## Question
§6 claims four things:
- a logit on historical quotes is biased "toward inelasticity", because the desk priced on
  winnability;
- an optimiser exploits the bias "into a mirage";
- logged propensities fix it;
- randomising from day one is "essentially unanswerable", because exploration costs second order
  while confounding costs first order.

In a market where the truth is known, does the naive estimate attenuate? And does a randomise, refit
and deploy pipeline beat the naive one, net of what the jitter costs?

## Results
The market has four segments. The oracle prices on segment only: 158.35 / 159.49 / 160.72 / 162.04,
worth V° = £6.185 per MWh quoted. β = 0.33, and the population slope is β_marg = 0.2776.

### Horizon value against the naive pipeline, Δ in % of V° (2,000 logging and 8,000 exploit quotes; R = 1,000)

| ρ (desk's information on u) | naive slope (attenuation) | NV's per-quote loss against the oracle | RL σ = 1 | **RL σ = 2** | RL σ = 4 | RG (IPS grid) |
|---|---|---|---|---|---|---|
| 0 | 0.279 (−0.5%) | 0.2% | −0.68 | **−0.99** | −3.39 | −4.84 |
| 0.3 | 0.245 (11.8%) | 0.8% | −0.15 | **−0.47** | −2.78 | −4.47 |
| 0.5 | 0.197 (29.1%) | 4.8% | +3.23 | **+2.89** | +0.87 | −0.94 |
| 0.8 | 0.119 (57.1%) | 39.8% | +31.6 | **+31.7** | +31.5 | +20.1 |

- **What RL recovers.** The mean RL slope at σ = 2 is 0.276–0.285 at every ρ: β_marg, not the
  individual β = 0.33.
- **Break-even:** ρ* ≈ 0.33.
- **The cost of the jitter itself** during logging is about 5% of the NV value per logged quote at
  σ = 2. Where NV is already near the oracle (ρ ≤ 0.3), that cost is what Δ shows.
- **Mirages.** The mirage rule (b̂ ≤ 0.02) never fired on the primary grid.

### Robustness (Δ(RL, 2) in %; one change at a time)

| Change | ρ = 0 | ρ = 0.5 |
|---|---|---|
| τ_u = 1.5 (less unlogged heterogeneity) | −1.16 | −0.94 (attenuation 8.4%) |
| τ_u = 5 | −0.75 | +40.1 (attenuation 60.1%) |
| τ_ζ = 1 (less exogenous desk noise) | −0.51 | +54.7 (attenuation 73.7%; 26.7% of refits censored, so conditional on convergence) |
| τ_ζ = 4 | −1.08 | −0.91 (attenuation 8.4%) |
| N_log = 500 | −0.98 | +3.64 |
| N_log = 5,000 | −1.85 | +1.32 |

## Why
- **Attenuation.** The desk prices up when it sees that a customer is more winnable (high u), so
  the price is positively correlated with the unlogged shifter. A logit on (segment, price) then
  reads high prices as winning, which makes the slope too flat: "toward inelasticity", as the note
  says. The size of the effect depends on how much the price moves with u, relative to the exogenous
  desk noise ζ. That is why τ_u and τ_ζ move it so much.
- **Randomisation** makes the logged price independent of u within a segment. The refit then
  recovers the population response slope β_marg, which is what a segment-level pricer needs.
- **Whether it pays** is a comparison of two costs: the mispricing that confounding causes (0.2% of
  V° at ρ = 0; 39.8% at ρ = 0.8) against the cost of jittering for 2,000 quotes. Both are second
  order in the price error. The confounded error is simply large when confounding is strong.
- **Why RG trails RL.** The IPS grid (±£2 and ±£4 around the NV price) is coarse and noisy with
  2,000 quotes. At strong confounding the NV price is so far off that ±£4 cannot reach the
  optimum.

## What this means
- **The note is right about the direction of the bias,** and right that randomisation identifies the
  response. Its "essentially unanswerable" case holds when historical prices are materially
  confounded: from ρ ≈ 0.33 here, or when the desk used much private information with little
  exogenous noise.
- **Without confounding, randomising costs about 0.5–1% of value over the horizon.** Longer logging
  (N_log = 5,000) costs more.
- **Practical corollary:** measure confounding before committing to a randomisation budget. An
  inexpensive check is how far the naive slope is from a small randomised pilot's slope.
- **Combined with x04.** Under the note's pass-through cap, jitter that respects the cap costs to
  first order. The randomisation budget should therefore sit where the cap does not bind, or be
  applied to which customers receive the cap.
- **Gate G1.** The result goes to G1 as a refinement of §6: the case is conditional on confounding,
  and the estimand is β_marg.
- **Limitations.**
  - The market is stylised: a logistic individual response, Gaussian heterogeneity, and a plug-in
    desk that knows β.
  - ρ stands in for the unknown real confounding.
  - The deployed policies price on segment only.
  - The values are computed from the true response, which no firm can observe.

## Predictions against results
| Prediction | Result |
|---|---|
| `pays-when-confounded` (75%) | `pays-when-confounded` |
| Δ(RL, 2) about −1.0 / +3 / +25–40% at ρ = 0 / 0.5 / 0.8 | −0.99 / +2.89 / +31.7% |
| `naive-inelastic` holds (85%); attenuation about 0 / .12 / .30 / .58 (±0.07; 70%) | holds; −0.005 / .118 / .291 / .571 |
| β_marg 0.280 ± 0.005 (90%) | 0.2776 |
| Mean RL slope within ±0.01 of β_marg (80%) | 0.276–0.285, i.e. within 0.007 |
| Break-even ρ* ∈ [0.15, 0.40] (60%) | 0.33 |
| RL at least as good as RG at ρ = 0.8 (60%) | yes: +31.7 against +20.1 |

## Unregistered work
- **Planning pilot (not registered).** A pilot of a similar market, recorded in
  `plans/theory-rosso-claims.md` §4, gave a naive slope of 0.28 / 0.20 / 0.12 and a gain of
  −1.0 / +3 / +33%. These are planning inputs.
- **Smoke runs (not registered).** Runs with 100 replications went to the scratchpad. One of them
  found the separation behind Deviation 1.

## Deviations
- **Before the run:**
  1. **2026-09-26: C6 is scoped to the primary grid.**
     - Registered: at most 1% of fits censored "in every cell".
     - Now: that limit applies to the primary grid, and the one-at-a-time cells report their
       censoring.
     - Why: in the τ_ζ = 1, ρ = 0.5 cell the naive price is £18–30 too high, and jitter of ±£2
       around it wins 0–3 of about 500 quotes per segment. A segment with no wins is completely
       separated, so no maximum-likelihood estimate exists. That is a property of the pipeline, not
       a failure of the estimator.

     The full entry is in the PREREG.
- **After the run:** none.
