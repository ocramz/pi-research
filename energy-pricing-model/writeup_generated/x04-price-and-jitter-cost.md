# x04 — The price table and the cost of jitter, audited

- **PREREG:** `energy-pricing-model/experiments/x04-price-and-jitter-cost/PREREG.md`, registered in
  203328d.
- **Deviations:** none, before or after the run.
- **Code:**
  - `experiments/lib/python/epmlib/`: `pricing.py`, `jitter.py` and `xp/x04_price_and_jitter_cost.py`;
  - `x04-price-and-jitter-cost/run.py`, `config.toml`.
- **Run:** `x04-price-and-jitter-cost/results/20260926T124644Z/`, at commit 6ecd92f, from a clean
  worktree (`git_dirty` false at the start and the end). 1 worker; 6 s of wall time.

## Verdict

| Class | Result |
|---|---|
| `jitter-cost-at-optimum` (primary) | **`misattributed-cap`**. At the unconstrained optimum p* = 159.746, symmetric jitter costs 1.71 / 6.37 / 20.65% at σ = £1 / £2 / £4, not the note's 1.0 / 4.0 / 18.1%. The note's figures are what symmetric jitter costs at the γ = 60% pass-through price: 0.96 / 4.05 / 18.00%. |
| `s74-reproduction` (secondary) | **`rounding`**. All 11 cells are within rounding tolerance. 7 of them are not exact at display precision, for example the pass-through price (154.204 against the printed 154.19) and the pass-through margin (£897.49 against £894). |

**Controls.** All pass.

| Control | Result |
|---|---|
| C1, the optimum | bisection and grid search agree within 2e-4 for both optima; log Π is concave on the grid |
| C2, independent integration | quad agrees with 10⁷ Monte Carlo draws within 1.64 SE; for the symmetric design, with Gauss–Hermite within 1e-15 |
| C3, curvature | finite-difference Π'' = −55.921157, against −βP*Q = −55.921158 |
| C4, σ = 0 | L = 0 exactly |
| C5, markup sign rule | agrees at all 77 grid points |

- **Vacuous passes:** none.
- **Censoring:** none.

## Question
§6 argues that jitter costs little because Π' = 0 at the optimum, and cites "Measured in §7:
£1/MWh of jitter costs 1.0% of expected margin". §7.5 then lists 1.0 / 4.0 / 18.1% as "clean
quadratic scaling, as the envelope argument predicts". Do these figures follow from the note's own
model and §7.4 inputs? And does the §7.4 table?

## Results

### Expected margin lost to jitter, % (§7.4 model: β = 0.33, p_ref = 162, ĉ = 150.34 or 160, Q = 250)

| Price and design | σ = 1 | σ = 2 | σ = 4 | matches §7.5? |
|---|---|---|---|---|
| symmetric at p* = 159.746 (the text's claim) | 1.71 | 6.37 | 20.65 | no |
| **symmetric at p_cap = 154.204 (γ = 0.6)** | **0.96** | **4.05** | **18.00** | **yes** |
| symmetric at the no-match price 164.402 | 3.73 | 14.57 | 52.78 | no |
| cap-respecting (ε = −σ\|Z\|) at p_cap | 19.56 | 40.20 | 83.06 | no |
| cap-respecting at p* | 1.70 | 6.40 | 21.79 | no |

### §7.4 recomputed

| Row | Price | Win | Markup | Margin per site per year | Printed |
|---|---|---|---|---|---|
| unconstrained | 159.746 | 67.78% | 9.406 | £1,593.9 | 159.74 / 67.8% / 9.40 / £1,593 |
| pass-through γ = 0.6 | 154.204 | 92.91% | 3.864 | £897.5 | 154.19 / 92.9% / 3.85 / £894 |
| no match | 164.402 | 31.16% | 4.402 | £342.9 | 164.39 / 31.2% / — / £343 |

### Other audits
- **Second order at the optimum.** L/σ² at σ = 0.25 is 0.017513, against the closed form
  ½β²(1 − P*) = 0.017542 (0.17% apart). Scaling is not "clean quadratic": L(4)/L(1) is 12.1 at p*
  and 18.8 at p_cap, against 16.
- **First order at a binding cap.** Jitter that respects the cap costs L/σ ≈ 0.190 at σ = 0.25,
  against the closed form √(2/π)·Π'/Π = 0.188. It costs 19.6% of margin at σ = £1, 20 times the
  symmetric figure.
- **"Markup falls as β rises"** holds at 44 of 77 grid points (57%). Its sign follows
  sign(βP*(p_ref − p*) − 1) exactly. The markup *rises* with β whenever the cost advantage is large:

  | ĉ | 130 | 135 | 140 | 145 | 150 | 155–160 |
  |---|---|---|---|---|---|---|
  | markup rises with β for | β ≥ 0.2 | ≥ 0.25 | ≥ 0.3 | ≥ 0.35 | ≥ 0.5 | never |

  At the note's point (ĉ = 150.34, β = 0.33) the claim holds.
- **Rent split.** Of the £9.66 exempt credit, the customer's price falls by £4.66 and tem's markup
  rises by £5.00 (52%). The note calls this "keeps most of the exempt rent".
- **"Roughly doubles expected margin"**. The unconstrained margin is 4.65× the no-match margin, and
  the pass-through margin is 2.62×. The win rates the note pairs, 31% → 93%, are the no-match and
  pass-through rows.
- **The cap binds** for every γ ≥ 2.63%.

## Why
- **The note's §7.5 figures are the pass-through price's.** The relative loss from symmetric jitter
  is about ½·|Π''|/Π·σ². That is 0.035 per £² at p* (= β/m*), but only about 0.019 per £² at
  p_cap, where the win probability is 93%. So the pass-through price shows about half the loss.
- **Second order is not special to the optimum.** Mean-zero jitter always costs second order,
  because the Π'·E[ε] term vanishes at any price (theory note §2.4). The envelope theorem is not the
  reason.
- **At a binding cap, the symmetric design is not available.** Half of its quotes would break the
  board's pass-through constraint. Jitter that respects the cap has E[ε] < 0 where Π' > 0, so it
  costs first order.

## What this means
- **Randomising around the unconstrained optimum is still cheap,** but 1.7× dearer than stated: 1.7%
  at £1.
- **Under the note's recommended pass-through constraint, cheap exploration is not available.** The
  symmetric jitter behind §7.5's figures breaches the cap on half the quotes. Jitter that respects the
  cap costs about 20% of margin at £1. So the §6 case for day-one randomisation needs either an
  exploration budget above the cap or randomisation of which customers get the cap. x05 tests the
  value side of that trade-off.
- **§7.4's table is right to rounding.** The note's §5 "sanity check" on β holds at its operating
  point but is not a general property: it fails at the larger cost advantages that the exempt match
  is meant to create.
- **Gate G1.** These are corrections to §6 and §7.5 for G1.
- **Limitations.** This is an audit within the note's own logistic model. It says nothing about real
  price response.

## Predictions against results
| Prediction | Result |
|---|---|
| `misattributed-cap` (95%) | `misattributed-cap` |
| `rounding` (90%) | `rounding` |
| L(p*)/σ² at σ = 0.25 within 1% of 0.01754 (95%) | 0.17% |
| Cap-respecting L/σ at σ = 0.25 of 0.188 ± 0.005 (90%); about 19.6% at σ = 1 | 0.190; 19.56% |
| L(4)/L(1) about 12.1 at p* and 18.8 at p_cap (90%) | 12.08; 18.78 |
| The sign rule agrees everywhere (99%) | 77 of 77 |
| "Markup falls as β rises" fails on part of the grid (95%) | fails at 33 of 77 points |
| Rent split about £4.66 / £5.00; ratios 4.65× and 2.62×; γ ≥ 2.63% | £4.66 / £5.00; 4.65×, 2.62×; 2.63% |

## Unregistered work
- **Planning calculations (not registered).** The theory note §4 records the in-memory calculations
  made while planning. They gave these numbers before the run, so the experiment confirms them with
  independent integrators, committed artefacts and registered tolerances.
- **Smoke runs (not registered).** Runs with 10⁶ Monte Carlo draws went to the scratchpad.

## Deviations
- **Before the run:** none.
- **After the run:** none.
