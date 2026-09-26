# x02 — Where the Jensen gap peaks, and whether point forecasts underprice

- **PREREG:** `energy-pricing-model/experiments/x02-jensen-gap/PREREG.md`, registered in bcd483e.
- **Deviations:** none, before or after the run.
- **Code:**
  - `experiments/lib/python/epmlib/`: `toy/` (toy v1), `toy/matching.py` (`jensen_terms`,
    `resampled_overstatement`) and `xp/x02_jensen_gap.py`;
  - `x02-jensen-gap/run.py`, `config.toml`.
- **Run:** `x02-jensen-gap/results/20260926T122425Z/`, at commit eaa2396, from a clean worktree
  (`git_dirty` false at the start and the end). 4 workers; 184 s of wall time; 710 CPU-s in 72 units.

## Verdict

| Class | Result |
|---|---|
| `jensen-peak-at-balance` (primary) | **`peak-above-balance`**. The overstatement peaks at gen/dem r = 2.23 (N = 14), at O = 13.5%. P_B(r > 1.33) = 1.00 and P_B(balance) = 0.00. The note's "peaks at balance" is refuted in toy v1. |
| `pointforecast-underprices` (secondary) | **`fails`**. In 12 of 18 cells the point forecast *understates* a prospect's matched share, i.e. it overprices. Understatement appears from N = 20 (evening) and in every cell at N = 60 and N = 100. |

**Controls.** All pass.

| Control | Result |
|---|---|
| C1, in-sample Jensen | holds at every half-hour, N and config |
| C2, zero noise | \|O\| ≤ 1e-12 at every N |
| C3, Gaussian closed form | \|z\| ≤ 1.97 across the five μ/D values |
| C4, AR invariance | worst \|z\| 2.18, against a threshold of 4 |
| C5, finite-S bias | O − O_an ≥ −0.51 pp, within limits at N = 20–60 |
| C6, calibration | passes in all 71 configs |

- **Censoring:** none.
- **Caps:** met; the largest unit took 21 s.
- **Vacuous passes:** none.
- **Resolved before the run:**
  - C3 and C6 z-tests where the variance is at rounding level, now "equal up to rounding";
  - an empty book (N = 0) in the scenario engine, used by x03 only.

  Neither changes a registered rule.

## Question
The note says a point-forecast pipeline overstates matched volume, "worst exactly where the book is
best balanced" (§2), with a §7.3 headline of "peaks at balance". It also says the pipeline
"therefore underprices". Where along the book's growth does the overstatement peak? And does the
pricing consequence hold for a prospect's marginal share?

## Results

### Overstatement O along the growth curve (pool P71, base config, S = 120)

| N | 4 | 8 | 10 | 12 | **14** | 16 | 20 | 25 | 30 | 35 | 40 | 50 | 60 | 80 | 100 | 125 | 200 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| r | 7.80 | 3.90 | 3.12 | 2.60 | **2.23** | 1.95 | 1.56 | 1.25 | 1.04 | 0.89 | 0.78 | 0.62 | 0.52 | 0.39 | 0.31 | 0.25 | 0.16 |
| O (%) | 2.2 | 7.2 | 10.5 | 13.3 | **13.5** | 12.7 | 12.0 | 11.3 | 9.5 | 8.3 | 7.8 | 7.1 | 6.8 | 4.7 | 2.5 | 0.9 | 0.0 |

- **At the note's ratios:** the model gives 11.95 / 9.46 / 7.75 / 6.76% at r = 1.56 / 1.04 / 0.78 /
  0.52, against the note's 10.6 / 7.3 / 4.9 / 2.9%.
- **Over r ∈ [0.5, 1.6]** O ranges from 6.8% to 12.0%, against §2's "5–11%".
- **At balance:** O(N = 30)/max O = 0.70.
- **Phantom margin at N = 40 (10 GWh):** £15,777 per year, against the note's "~£10k".

### The peak depends on the pool mix (where the solar/wind energy split is θ_s)

| θ_s (solar share) | 0 (wind only) | 0.25 | 0.5 (base) | 0.75 | 1 (solar only) |
|---|---|---|---|---|---|
| r_peak | 1.25 | 1.56 | 2.23 | 5.20 | 0.39 |

- **Noise source.** With generation noise only, the maximum O is 13.4%. With demand noise only, it
  is 0.29%. The gap comes from generation uncertainty.
- **Robustness.**
  - The peak lies in the balance band in 1 of the 40 Latin-hypercube cells (2.5%).
  - Across the 21 one-at-a-time (OAT) cells the peak stays at r = 2.23. The exceptions are a
    shuffled book order and evening midday level e_m = 0.25 (both 2.60), and θ_s = 0.25 (1.56) and
    0.75 (5.20).

### Point forecast against true marginal share of one more site (pp; 95% CI)

| N | office | 24/7 | evening |
|---|---|---|---|
| 10 | +16.7 [15.9, 16.6] | +20.6 [19.5, 20.4] | +27.8 [25.2, 27.1] |
| 20 | +10.2 [9.0, 9.9] | +9.3 [7.7, 8.8] | **−3.9 [−4.3, −3.8]** |
| 30 | **−0.8 [−1.0, −0.4]** | **−3.3 [−3.4, −2.9]** | **−2.8 [−2.9, −2.5]** |
| 40 | +0.8 [0.5, 1.1] | **−0.6 [−0.9, −0.5]** | **−0.3 [−0.4, −0.1]** |
| 60 | **−0.8 [−1.2, −0.6]** | **−0.4 [−0.6, −0.2]** | **−0.4 [−0.5, −0.3]** |
| 100 | **−3.1 [−3.2, −3.0]** | **−2.8 [−2.9, −2.7]** | **−1.6 [−1.7, −1.5]** |

Bold cells have a CI upper bound below 0: there the point forecast overprices.

In the positive cells at N = 10–20, the percentile CI sits slightly below the point estimate. The
statistic is a min of means, and each bootstrap resample adds its own Jensen bias to it. The
verdict rests on the negative cells, whose point estimates lie inside their CIs.

## Why
- **The book-level gap is Jensen's inequality:** min is concave, so using mean shapes overstates
  matched volume. It is largest where G and D are *often close within a half-hour*, not where they
  balance over the year.
- **Why the peak moves with the pool mix:**
  - Solar is concentrated around midday, so a solar-heavy pool is close to demand in daylight
    half-hours only once the book is large. That pulls the peak below balance: 0.39 when solar only.
  - Wind is spread around the clock. Its variable output meets the book most often when annual
    generation exceeds demand, which pushes the peak above balance: 1.25 for wind only, 2.23 for the
    mixed base.

  The planning pilot showed this mechanism. The first draft of the stage B plan had it backwards.
- **Why "therefore underprices" fails.** A prospect's marginal share on mean shapes is
  min(d̄, (Ḡ − C̄)⁺). That is S-shaped in the surplus, not concave. In thin books it overstates the
  share, which underprices. In saturated books the mean surplus is near zero or negative in hours
  where real scenarios still have surplus, so it understates the share, which overprices.

## What this means
- **"Peaks at balance" is refuted in toy v1 at the base mix,** and it holds in only 1 of 40 random
  parameterisations. Where the gap peaks depends on the generation mix. It is not a property of
  balance.
- **The note's own table is consistent with this.** The table rises through r = 1.55, and in this
  toy the peak lies above it.
- **Magnitudes.** At the note's four ratios the model's gap is 1.3–3.9 pp larger than the note's
  table, and the phantom margin is about 60% larger. The size depends on the unstated noise model.
- **Pricing.** The direction of the pricing error from point forecasts depends on book saturation.
  A pipeline that corrects for it by uniformly shading matched volume down would overprice saturated
  books. The fix the note proposes — distributional forecasts with joint scenarios — is still the
  right one; the one-sided "underprices" is not.
- **Gate G1.** Both verdicts go to G1 as corrections to §2 and §7.3.
- **Limitations.**
  - Toy v1 is a reconstruction.
  - "Balance" is the annual aggregate ratio, as in the note's table.
  - Demand is weakly coupled to weather here, so the note's "dominant coupling" is not represented.
  - This is evidence in one family of synthetic books, not a proof about tem's.

## Predictions against results
| Prediction | Result |
|---|---|
| Class probabilities: `peak-above-balance` 75%, `multimodal` 10%, `peak-at-balance` 10% | `peak-above-balance` |
| r_peak ∈ [1.5, 2.7] (70%); max O ∈ [10, 15]% (70%) | 2.23; 13.5% |
| O(30)/max O ∈ [0.65, 0.95] (70%) | 0.70 |
| Wind only: r_peak ∈ [1.0, 1.6] (65%) | 1.25 |
| θ_s = 0.75: multimodal (55%) | **not met**: a single local peak at 5.2 |
| θ_s = 1: r_peak ≤ 0.5 (75%) | 0.39 |
| Magnitudes at N = 20/30/40/60 in 9–14 / 7–11 / 5.5–9 / 4.5–8% (65%) | 11.95 / 9.46 / 7.75 / 6.76 |
| Demand noise alone: O ≤ 0.5% (90%) | 0.29% |
| Secondary `fails` (90%) | `fails` |
| Phantom margin £12–17k (65%) | £15.8k |
| r_peak in the band in ≤ 25% of Latin-hypercube cells (70%) | 2.5% |

## Unregistered work
- **Planning pilot (not registered).** A pilot on a toy close to v1, run in memory while planning and
  recorded in `plans/theory-rosso-claims.md` §4. It gave r_peak ≈ 2.6 and O_max ≈ 12.9%. These are
  planning inputs, not results.
- **Smoke runs (not registered).** Runs with `config_smoke.toml` at S = 12 went to the scratchpad.
  At S = 12, C5 failed, as a finite-S bias of that size predicts.

## Deviations
- **Before the run:** none.
- **After the run:** none.
