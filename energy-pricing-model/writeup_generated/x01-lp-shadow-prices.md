# x01 — LP shadow prices and the 2% re-solve rule

- **PREREG:** `energy-pricing-model/experiments/x01-lp-shadow-prices/PREREG.md`, registered in
  9b75f38.
- **Deviations:** none, before or after the run.
- **Code:**
  - `experiments/lib/python/epmlib/`: `toy/` (toy v1), `allocation.py`, `lpcheck.py` and
    `xp/x01_lp_shadow_prices.py`;
  - `x01-lp-shadow-prices/run.py`, `config.toml`;
  - the independent witness checker `x01-lp-shadow-prices/recheck_witnesses.py`.
- **Run:** `x01-lp-shadow-prices/results/20260926T120707Z/`, at commit a504ce3, from a clean
  worktree (`git_dirty` false at the start and the end). 4 workers; 97 s of wall time; 357 CPU-s in
  the units.

## Verdict

| Class | Result |
|---|---|
| `dual-2pct-rule` (primary) | **`rule-fails-saturated`**. e* = 5.85% (95% CI 5.68–6.04%). The only failing cell is office at N = 100. Every cell with N ≤ 40 is at most 1.79%. |
| `note-dual-statements` (secondary) | **`fails`**. All three of the note's §3 dual statements have certified counterexamples. |

**Controls.** All pass.

| Control | Result |
|---|---|
| C1, exact certificate | 5,500 of 5,500 Part A instances, including 500 degenerate ones |
| C2, HiGHS | objectives agree on all instances; duals agree within 1e-6 on nondegenerate ones; on degenerate ones the HiGHS duals are optimal |
| C3, planted wrong dual | rejected on all 5,500 instances |
| C4, ΔV identity against a per-site HiGHS LP | 21,600 checks, maximum error 5.7e-14 |
| C5, dual ≥ exact | holds everywhere |
| C6, error identity | holds everywhere |
| C7, calibration | \|z\| ≤ 1.64 |

- **Censoring:** 0 of 30,700 LP solves.
- **Caps:** met; the largest unit took 61 s against a 300 s cap.
- **Vacuous passes:** none.
- **Independent re-check.** `recheck_witnesses.py` re-derives every witness in exact rationals, with
  no shared code, and verifies all 11,328: S1 4,917, S2 5,804, S3 607. The output is in
  `diagnostics/20260926T120707Z-witness-recheck.txt`.

## Question
The note's §3 makes three statements about the duals of its per-half-hour LP. It also gives a rule:
re-solve rather than use duals "whenever Q_j exceeds ~2% of book volume". Do the statements hold? And
is the dual valuation within 5% of the exact one at 2% of book volume, in the toy book?

## Results

### The note's dual statements (Part A)
These are 5,000 random half-hour LPs, and the statements are tested on the nondegenerate ones.

| Statement (the note) | Eligible | Counterexamples | What holds instead |
|---|---|---|---|
| S1: "μ = 0 for inframarginal assets" (demand-scarce) | 1,249 | 1,249 (100%) | μ_a = π_k − π_a > 0 |
| S2: μ = λ − π_a in the generation-scarce regime | 2,269 | 2,269 (100%) | μ_a = (λ − π_a)⁺; an asset priced above λ has μ = 0 |
| S3: the regime is set by ΣG against C | 5,000 | 607 (12.1%) | the regime is set by profitable generation G⁺ |

The instances fall into regimes as follows: 3,240 generation-scarce, 2,131 demand-scarce, and 129
balanced (all of them constructed ties).

### The dual valuation at q = 2% of book volume (Part B, toy v1, base config)
rel_err is in %, with the 95% bootstrap CI.

| N (gen/dem) | office | 24/7 | evening |
|---|---|---|---|
| 10 (3.12) | 0.27 [0.26, 0.28] | 0.31 [0.30, 0.32] | 0.68 [0.66, 0.70] |
| 20 (1.56) | 0.73 [0.72, 0.75] | 0.71 [0.69, 0.73] | 1.31 [1.28, 1.35] |
| 30 (1.04) | 1.29 [1.26, 1.32] | 1.14 [1.12, 1.16] | 1.72 [1.67, 1.76] |
| 40 (0.78) | 1.75 [1.71, 1.79] | 1.51 [1.48, 1.54] | 1.43 [1.39, 1.48] |
| 60 (0.52) | 2.68 [2.60, 2.76] | 2.36 [2.30, 2.42] | 1.48 [1.43, 1.53] |
| 100 (0.31) | **5.85 [5.68, 6.04]** | 4.29 [4.16, 4.42] | 2.81 [2.71, 2.92] |

- **In money**, the overestimate at 2% is at most £0.20/MWh of the prospect's volume, in any cell.
  In the failing cell it is £0.079/MWh.
- **Linearity.** rel_err(8%) / rel_err(2%) lies in [3.83, 4.28] in every cell, so the error is
  linear in the prospect's size.
- **The largest safe size, q*₅%:**
  - ≥ 16% (censored) for office and 24/7 at N = 10;
  - 13.8% for evening at N = 10;
  - 3.7% for office at N = 60;
  - 1.64% for office at N = 100.
- **Robustness.** H1 holds, by point estimate, in 14 of the 40 Latin-hypercube cells of toy v1
  (35%).

## Why
- The dual valuation charges the full prospect at ν̄ in every half-hour with a surplus. The exact
  value caps each half-hour at the surplus.
- The overestimate is therefore ν̄·Σ 1{G > C}·(d − (G − C))⁺ (C6). It comes from half-hours whose
  surplus is smaller than the prospect.
- As the book saturates, surpluses become rare and small, so a fixed 2% prospect overshoots a larger
  share of them.
- Office load sits on the thin midday surplus that remains at N = 100, so office fails first.
- The note's statements miss inframarginal rent (S1) and the clipping at zero for unprofitable
  assets (S2 and S3). Its toy has a single uniform premium, π = 10, where none of the three shows.

## What this means
- **The 2% rule of thumb is safe in toy v1 except at the saturated end.** The one failing cell is at
  gen/dem 0.31, and there the error in money (£0.08/MWh) is small beside the §7.4 markups of £3.86
  and £9.41. The rule's safe size shrinks as the book saturates: from about 16% at gen/dem 3.1 to
  1.6% at 0.31.
- **The rule is not robust across toy parameterisations.** It holds in only 35% of the
  Latin-hypercube cells.
- **Gate G1.** This result feeds the G1 draft of x01a: a re-solve rule scaled by the book's surplus,
  not by its volume. That draft is unregistered.
- **The §3 corrections.** The dual table in theory note §2.1 replaces the note's. Anyone
  implementing §3 with heterogeneous generator premiums would misprice inframarginal generation.
  They would also misclassify about 12% of half-hours when some assets are priced above λ.
- **Limitations.**
  - Toy v1 is a reconstruction, not the note's code.
  - Part B uses one price level, and the per-customer cap is inert there.
  - The 5% tolerance is this experiment's choice.
  - Part A's 12.1% describes the random instance distribution, not tem's book.
  - The statements S1 and S2 are refuted as statements about every instance: that is a theorem
    checked by certified counterexamples, not a statistical claim.

## Predictions against results
| Prediction | Result |
|---|---|
| C1–C3 pass (99%) | pass |
| `note-dual-statements`: `fails` (99%); S1 and S2 fail on 100% of eligible instances | `fails`; 100% and 100% |
| S3 misclassifies 8–18% (80%) | 12.1% |
| Class probabilities: `rule-fails-saturated` 50%, `inconclusive` 25%, `rule-holds` 20% | `rule-fails-saturated` |
| Linearity ratio in [3.6, 4.6] in every cell (80%) | [3.83, 4.28] |
| err_£ ≤ £0.25/MWh in every cell (85%) | at most £0.20 |
| q*₅% at N = 10 censored at ≥ 16% (80%) | **not met**: office and 24/7 are censored, but evening is 13.8% |
| H1 holds in 25–60% of the Latin-hypercube cells (55%) | 35% |

## Unregistered work
- **Planning pilot (not registered).** A pilot on a toy close to v1, run in memory while planning
  and recorded in `plans/theory-rosso-claims.md` §4, predicted the table above. For example, it gave
  office at N = 100 as 5.29% against the registered run's 5.85%. Its numbers are planning inputs,
  not results.
- **Smoke runs (not registered).** Runs with `config_smoke.toml` went to the scratchpad and are not
  cited.

## Deviations
- **Before the run:** none.
- **After the run:** none.
