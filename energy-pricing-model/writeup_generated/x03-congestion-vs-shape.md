# x03 — Congestion against load shape in a prospect's matched share

- **PREREG:** `energy-pricing-model/experiments/x03-congestion-vs-shape/PREREG.md`, registered in
  19852ef.
- **Deviations:** none, before or after the run.
- **Code:**
  - `experiments/lib/python/epmlib/`: `toy/` (toy v1) and `xp/x03_congestion_vs_shape.py`;
  - `x03-congestion-vs-shape/run.py`, `config.toml`.
- **Run:** `x03-congestion-vs-shape/results/20260926T123334Z/`, at commit 531080c, from a clean
  worktree (`git_dirty` false at the start and the end). 4 workers; 147 s of wall time; 564 CPU-s in
  the units.

## Verdict

| Class | Result |
|---|---|
| `congestion-dominates` (primary) | **`congestion-dominant`**. R = 3.62 (95% CI 3.58–3.66) in the mixed pool P71. |
| `shape-rank-solar` (secondary) | **`holds`**. In the solar-only pool P72, office > 24/7 > evening at N = 20 and 40. All four gaps have a CI above 0. |
| `shape-gap-vs-markup` (secondary) | **`holds`**. ν̄·(office − evening) at N = 40 in P72 is £4.48/MWh (CI 4.44–4.52), at least the £3.86 floor. |

**Controls.** All pass.

| Control | Result |
|---|---|
| C1, monotone decline | holds in every scenario |
| C2, increment identity | holds |
| C3, per-site HiGHS LP | 57,600 checks, maximum error 6.5e-14 |
| C4, limits (G ≡ 0 and G ≡ 10⁹) | exact |
| C5, AR invariance | worst \|z\| 2.0, against a threshold of 4 |
| C6, calibration | passes in all 69 configs |

- **Censoring:** none.
- **Caps:** met; the base config took 145 s against a 600 s cap.
- **Vacuous passes:** none.

## Question
The note says exempt-match capacity is congestible, and that "congestion is the dominant effect"
(§7.1). It also says shape alone matters: office against evening venue is 12 pp at 40 sites in a
solar-only pool, i.e. £4.2/MWh, "comparable in size to the entire margin" (§7.2). How do the two
effects compare in toy v1?

## Results

### Marginal matched share of one more 250 MWh site (%), mixed pool P71, base config

| N (gen/dem) | 0 | 10 (3.12) | 20 (1.56) | 30 (1.04) | 40 (0.78) | 60 (0.52) | 100 (0.31) |
|---|---|---|---|---|---|---|---|
| office | 99.9 | 81.6 | 60.7 | 43.9 | 31.2 | 16.5 | 4.0 |
| 24/7 | 99.9 | 78.4 | 56.6 | 40.3 | 28.8 | 15.4 | 4.3 |
| evening | 99.3 | 67.9 | 42.6 | 25.9 | 17.0 | 8.7 | 2.3 |

- Over N = 10–100, each archetype's share falls by 65.7–77.6 pp. The spread across archetypes is at
  most 18.1 pp (at N = 20). This gives R = 3.62.
- Against the note's table 7.1 (18 cells), the RMSE is 3.0 pp. The best-fitting solar share is
  θ_s = 0.4, with RMSE 2.8 pp.
- The note's 24/7-over-office reversal at N = 30 appears here only at N = 100: 4.26% against 3.98%.
  At N = 30 the model gives office 43.9 and 24/7 40.3, where the note has 40.3 and 40.4.
- The value of one office site is £7,136 per year at N = 10 (the note says £7,079) and £348 at
  N = 100 (the note says £163): a ratio of 21×, against the note's 43×.

### Solar-only pool P72 (6 MW)

| N | office | 24/7 | evening | note (office / 24/7 / evening) |
|---|---|---|---|---|
| 20 | 42.0 | 34.5 | 23.2 | 43.5 / 33.1 / 23.8 |
| 40 | 27.5 | 23.2 | 14.7 | 26.7 / 21.4 / 14.7 |

- The RMSE against table 7.2 is 1.2 pp.
- The office–evening gap at N = 40 is 12.8 pp, i.e. £4.48/MWh (the note says 12 pp and £4.2).
- In this pool, R = 1.11 (CI 1.11–1.12): shape and congestion are about the same size.

### Standalone against marginal share, and robustness
- **Cost-plus against marginal.** An empty-book (standalone) valuation credits 3.2× (office), 3.5×
  (24/7) and 5.8× (evening) the matched share that one more site actually gets at N = 40.
- **Robustness.**
  - R ≥ 2 in 37 of the 40 Latin-hypercube cells (92.5%).
  - The 3 exceptions have θ_s ≥ 0.73 (R = 1.67, 1.67, 0.95).
  - Across the one-at-a-time (OAT) cells R ranges from 1.94 to 6.2. The only cell below 2 is
    θ_s = 0.75.

## Why
- **Congestion.** Each added site uses up surplus in the half-hours where the book's demand already
  meets the pool, so any prospect's matched share falls steeply as the book grows (C1 makes this
  monotone). Over the toy's range of books, that decline is several times larger than the
  differences between load shapes.
- **Shape.** Shape matters most when the pool is concentrated in time. A solar-only pool rewards
  daytime load, and R ≈ 1 there. A mixed pool spreads generation around the clock and shrinks the
  shape differences.

## What this means
- **"Congestion is the dominant effect" holds in toy v1 for mixed pools,** by a factor of about 3.6.
  It does not hold for solar-heavy pools (θ_s ≳ 0.75), where shape is as large as congestion.
- **§7.2's shape claim reproduces closely**: 12.8 pp, i.e. £4.48/MWh, against the note's 12 pp and
  £4.2. That is at least the low end of the note's own markup range, so shape is margin-sized.
- **Two details of §7.1 do not reproduce:**
  - the 24/7 reversal at N = 30, which comes at N = 100 here;
  - the saturated-book value of £163, which is £348 here.

  Both depend on unstated parameters of the toy.
- **Gate G1.** The result supports the note's congestion-first architecture, with the caveat that
  it is conditional on the pool mix. It goes to G1.
- **Limitations.** Toy v1 is a reconstruction with stylised archetypes. R is this experiment's
  definition of "dominant". The primary claim is decided at the base mix only.

## Predictions against results
| Prediction | Result |
|---|---|
| `congestion-dominant` (90%); R ∈ [3, 5] (70%) | `congestion-dominant`; 3.62 |
| `shape-rank-solar` holds (90%) | holds |
| `shape-gap-vs-markup` holds (70%), at about £4.4 ± 0.7 | holds; £4.48 |
| solar-R ∈ [0.8, 1.8] (65%) | 1.11 |
| Rank reversal at N ∈ (60, 100] (60%) | N = 100 |
| Standalone ÷ marginal at N = 40 about 3 (70%) | office 3.2 and 24/7 3.5, but **evening 5.8** |
| RMSE against table 7.1 ≤ 4 pp (60%) | 3.0 pp |
| R ≥ 2 in ≥ 90% of Latin-hypercube cells (70%) | 92.5% |

## Unregistered work
- **Planning pilot (not registered).** A pilot on a toy close to v1 (`plans/theory-rosso-claims.md`
  §4) gave R = 3.7, with the P72 shares within about 1 pp of the ones above. These are planning
  inputs.
- **Smoke runs (not registered).** Runs at S = 12 went to the scratchpad.

## Deviations
- **Before the run:** none.
- **After the run:** none.
