# x01a-surplus-scaled-rule — pre-registration (DRAFT, not registered)

> **DRAFT, not registered.** This is an option for the user's decision at gate G1. x01's
> `rule-fails-saturated` action asks for it. It becomes a registration only if the user chooses it,
> in which case it is moved to `experiments/x01a-surplus-scaled-rule/PREREG.md` and committed on its
> own before any code for it exists.

- **Plan:** stage B gate G1, option A.
- **Theory / Inputs:**
  - x01 run `20260926T120707Z` at a504ce3: its rule cells and q*₅% per cell;
  - `plans/theory-rosso-claims.md` §2.2, the error of the dual valuation for small q;
  - `plans/toy_v1_spec.md` at 26abb27.

## Why this design
x01 found the error of the dual valuation linear in the prospect's size q:
- rel_err(8%)/rel_err(2%) lies in [3.83, 4.28] in every cell;
- the safe size q*₅% falls from at least 16% of book volume at gen/demand 3.1 to 1.6% at 0.31.

So a threshold stated as a share of *book volume* cannot be safe at all saturations. The theory note
gives the slope as roughly Σ_t f_S(0⁺)·E d̃² / Σ_t P(S > 0)·E d̃, where S = G − C is the half-hourly
surplus. That points to scaling the threshold by the book's **expected unmatched surplus**,
U = Σ_t E(G − C)⁺, rather than by its volume.

## Hypotheses (proposed)
- **`surplus-rule` (primary).**
  - H1: there is a single k such that a prospect with Q_j ≤ k·U keeps the dual valuation's relative
    error ≤ 5%. It must hold in every (N, archetype) cell of x01 Part B, and in ≥ 90% of the 40
    Latin-hypercube cells.
  - H0: no single k does this.
- **Descriptive:** the fitted k with its bootstrap CI; for comparison, the best single threshold as a
  share of book volume.

## Method (proposed)
- Reuse x01's Part B machinery: same books, archetypes, scenarios and seeds.
- Add U(N) per config, and the q grid expressed as a share of U.
- For each cell, find the share of U at which the error reaches 5% (q*₅%/U), interpolated in
  log q. H1 holds if the minimum of that share across cells gives k > 0 at which every cell passes.

## Outcome classes (proposed)
| Class | Condition | Action |
|---|---|---|
| `invalid` | a control fails (x01's C4–C7) | debug, record a deviation, re-run |
| `surplus-rule-holds` | CI lower of k* > 0, and every cell passes at k* | G2: recommend the surplus-scaled rule |
| `surplus-rule-partial` | passes in ≥ 90% of the Latin-hypercube cells | G2: report its scope |
| `inconclusive` | otherwise | G2 |

## Predictions
To be set from x01's recorded per-cell errors before registration. Expected: `surplus-rule-holds`
(60%).

## Deviations
(not registered)
