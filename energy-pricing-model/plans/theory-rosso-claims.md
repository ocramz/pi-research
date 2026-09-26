# Theory note B — the claims of the Rosso design note

*Dated working note, 2026-09-26, stage B.*

- **Inputs:** `docs/tem-rosso-pricing-model-v1.md` ("the note") and
  `docs/tem-open-pricing-datasets-v2.md` ("the companion"), both committed in b9291cd.
- **External look-ups:** none, by the user's decision. Everything below comes from the two notes and
  from reasoning.
- **Numbers in §4:** planning inputs, not experiment results. They come from hand checks, and from
  in-memory calculations run while planning. Nothing was written to disk and no code for the
  experiments existed yet.

## 1. Claim inventory

Each claim is typed as one of:
- **H** — a hypothesis, tested in the named experiment;
- **T** — a theorem or identity, checked as a control there;
- **D** — descriptive, reported without a decision rule;
- **U** — untestable here, for the stated reason.

| # | § | Claim (short quote or paraphrase) | Type | Where |
|---|---|---|---|---|
| 1 | 0 | Margin is "temporal coincidence rent", "not a trading edge" | U (business framing) | — |
| 2 | 0, 4 | Coincidence rent is "a congestible shared resource" | H | x03 |
| 3 | 1 | A1: only same-half-hour volume is exempt; no storage | U (regulatory). Adopted as a model assumption | toy v1 |
| 4 | 1 | A2: exemption removes ℓ but not n | U (regulatory; needs settlement data) | — |
| 5 | 1 | A3: fixed price for the tenor | U. Adopted in x04 | — |
| 6 | 1, 11 | κ = 2.5 MWh/HH per customer | U (regulatory). Inert in the toy | — |
| 7 | 2 | Quantile GBM plus a Gaussian copula is adequate | U (needs real MPAN and NWP data) | — |
| 8 | 2 | Sampling G and D on the same NWP member matters | T: min is supermodular, so positive dependence raises E min. The size needs real data | — |
| 9 | 2 | E min(G,D) ≤ min(EG, ED) | T | x02 C1 |
| 10 | 2 | A point pipeline "overstates matched volume" | T, at book level | x02 |
| 11 | 2 | "…and therefore underprices" | H | x02 `pointforecast-underprices` |
| 12 | 2 | The gap is "5–11% of matched volume" | D. §7.3 itself shows 2.9–10.6% | x02 |
| 13 | 2, 7.3 | The gap is "worst exactly where the book is best balanced"; "peaks at balance" | H | x02 primary |
| 14 | 3 | The LP is a transportation problem solved by merit order on π | T | x01 C1–C2 |
| 15 | 3 | Generation-scarce regime: ν = 0 and μ = λ − π | H: μ = (λ−π)⁺ is correct | x01 `note-dual-statements` |
| 16 | 3 | Demand-scarce regime: ν = λ − π_(k) | T | x01 C1–C2 |
| 17 | 3 | "μ = 0 for inframarginal assets" | H, predicted false: μ = π_k − π_a | x01 `note-dual-statements` |
| 18 | 3 | The regime is set by ΣG versus Σmin(D, κ) | H: profitable G⁺ is correct | x01 `note-dual-statements` |
| 19 | 3 | ΔV_j = Σλ[min(G,D+d) − min(G,D)] = Σν̄·min(d,(G−D)⁺) | T, with the first sum's weight corrected (§2.2) | x01 C4 |
| 20 | 3 | "Duals overestimate the value of a large prospect" | T (concavity) | x01 C5 |
| 21 | 3 | "Re-solve … whenever Q_j exceeds ~2% of book volume" | H | x01 primary |
| 22 | 3, 7.2 | Equal annual kWh can have different values through shape alone | H | x03 secondary |
| 23 | 4 | Crediting the match at ν, not at the headline levy, is where cost-plus goes wrong | D (standalone versus marginal) | x03 |
| 24 | 4 | φσ is "the certainty equivalent of exponential utility to second order" | T, false as written (§2.6) | — |
| 25 | 4 | φ "should be governed, not learned" | U (opinion) | — |
| 26 | 5 | p* = ĉ + 1/(β(1 − P(p*))), solved by bisection | T | x04 C1 |
| 27 | 5 | "Markup falls as price sensitivity β rises" | D, holds only when βP*(p_ref − p*) < 1 (§2.5) | x04 |
| 28 | 5 | "Markup rises as you become more likely to win" | T (through ĉ or p_ref) | x04 |
| 29 | 5 | "The entire optimiser is two scalars, ĉ_j and β" | T, false as written: p_ref is a third input | — |
| 30 | 5 | Unconstrained pricing "keeps most of the exempt rent (~£9.4/MWh)" | D (rent split) | x04 |
| 31 | 6 | Historical-quote logit is biased, "usually toward inelasticity" | H | x05 `naive-inelastic` |
| 32 | 6 | Known propensities give unbiased IPS/DR | T | x05 C1 |
| 33 | 6 | "Exploration loss is second order; the bias … is first order" | D (§2.4) | x04, x05 |
| 34 | 6, 7.5 | "£1/MWh of jitter costs 1.0% of expected margin"; losses 1.0/4.0/18.1% | H | x04 primary |
| 35 | 6 | The case for day-one randomisation is "essentially unanswerable" | H, conditional on confounding | x05 primary |
| 36 | 6 | Deep RL is unsuitable; use a two-timescale scheme | U (opinion) | — |
| 37 | 7.1 | "Congestion is the dominant effect", and the table 7.1 values | H plus D | x03 primary |
| 38 | 7.1 | "£7,079/yr against a thin book and £163/yr against a saturated one" | D | x03 |
| 39 | 7.2 | 12 pp between office and evening, i.e. £4.2/MWh, "comparable to the entire margin" | H | x03 secondary |
| 40 | 7.3 | "~£10k/yr of phantom margin on a 10 GWh book" | D | x02 |
| 41 | 7.4 | The three-row price table | H (arithmetic) | x04 `s74-reproduction` |
| 42 | 7.4 | The match "roughly doubles expected margin" and raises the win rate from 31% to 93% | D. The ratios are 4.65× and 2.62×, and the win rates come from different rows | x04 |
| 43 | 7.4 | Margin and volume moving together is what "a genuine structural cost advantage looks like" | T, not diagnostic: in the logit model any cut to ĉ raises both P* and the markup | — |
| 44 | 7.5 | "Clean quadratic scaling, as the envelope argument predicts" | D | x04 |
| 45 | 8 | Which inputs are open (the source table) | H, for Tier 1 access | x06 |
| 46 | 8 | Open data "cannot produce elasticity" | U (needs a real quote log) | — |
| 47 | 8 | Forward curves are not open | U (a look-up) | — |
| 48 | 9 | A synthetic reference book "is buildable from open data alone" | U here. x06 tests access only; this is a stage C option | — |
| 49 | 10, 11 | Build order, what not to build, what breaks the model | U (opinion or regulatory) | — |

The companion's Tier-1 access claims tested in x06 are:
- Elexon Insights, "no API key is required";
- the NESO Data Portal and its CKAN API;
- NESO embedded wind and solar forecasts, half-hourly, up to 14 days ahead, with archives;
- PV_Live, half-hourly, "open and free";
- Open-Meteo: "no authentication", ERA5 from 1940, and a historical-forecast archive "from 2021".

## 2. Derivations

### 2.1 LP duals for one half-hour
Notation: c_i = min(D_i, κ), C = Σc_i, and G⁺ = Σ_{π_a<λ} G_a.
- **Generation-scarce** (G⁺ < C): ν_i = 0 and μ_a = (λ − π_a)⁺.
- **Demand-scarce** (G⁺ > C, with marginal asset k such that Σ_{π<π_k} G < C < Σ_{π≤π_k} G):
  - ν_i = λ − π_k for every i with c_i > 0;
  - μ_a = (π_k − π_a)⁺.

  Inframarginal assets therefore earn π_k − π_a > 0. μ = 0 holds only for asset k and for the
  unused assets.
- **Uniqueness.** The duals are unique when every c_i > 0 and every G_a > 0, there are no ties in
  π, and the regime inequalities are strict. Otherwise they form an interval. For example, when
  Σ_{π<π_k} G = C, ν ∈ [λ − π_k, λ − π_prev].
- **Why the note's toy hides this:** with uniform π (the note's §7), inframarginal rent is zero.

### 2.2 Prospect value
- **Exact identity.** For d ≥ 0, min(G, D+d) − min(G, D) = min(d, (G−D)⁺), in every scenario and at
  every size.
- **Money.** The LP values a matched MWh at λ − π = ν̄. The note's first sum is weighted by λ; read
  literally, it overstates the value by λ/ν̄ = 45/35.
- **With merit-order premiums:** ΔV = Σ_t ∫₀^{d_t} (λ − π_t(C_t + x))⁺ dx.
- **Dual valuation:** ν̄·Σ 1{G>D}·d. Its error is ν̄·Σ 1{G>D}·(d − (G−D))⁺ ≥ 0.
- **For small q** (d = q·d̃ and S = G − D): the relative error ≈ q · [Σ_t f_{S_t}(0⁺)·E d̃_t²/2] /
  [Σ_t P(S_t>0)·E d̃_t]. It is linear in q, and the slope grows as the book saturates.
- **On mean shapes** the prospect's matched share is an S-shaped function of the surplus. A point
  pipeline can therefore under- or overstate a prospect's value (claim 11).

### 2.3 Jensen gap
- min is concave, so Σ_t min(Ḡ_t, D̄_t) ≥ mean_s Σ_t min(G, D) holds per half-hour, in sample.
- O = 0 if the noise is zero.
- **AR invariance.** Every quantity in x01–x03 is a sum of per-half-hour expectations. The
  coefficients of the AR(1) processes therefore cannot move them (toy v1 §8).

### 2.4 Pricing and jitter
- **Profit and win probability:** Π(p) = Q·P(p)·(p − ĉ), with P = σ(β(p_ref − p)), so
  P' = −βP(1−P).
- **Optimum.** The first-order condition gives m* = p* − ĉ = 1/(β(1 − P*)).
  g(p) = p − ĉ − 1/(β(1 − P(p))) is strictly increasing, so the root is unique and bisection is
  valid.
- **Curvature at the optimum:** Π''(p*) = Q[βP*(1 − 2P*) − 2βP*(1 − P*)] = −βP*Q.
- **Relative loss from mean-zero jitter at p*:** ½·β²·(1 − P*)·σ² + O(σ⁴).
- **Mean-zero jitter costs second order at *any* price**, because the Π'·E[ε] term vanishes. The
  envelope theorem is not what makes it second order.
- **Jitter that respects the cap** (ε ≤ 0 at a binding pass-through cap, where Π' > 0) costs
  Π'·E|ε|, which is first order.
- **"Both second order."** A confounded elasticity moves p by some δ, and the loss ½|Π''|δ² is also
  second order in the price error. The difference is that δ is large.

### 2.5 Markup comparative statics
- ∂m*/∂β has the sign of β·P*·(p_ref − p*) − 1.
  - So "markup falls as β rises" holds only when βP*(p_ref − p*) < 1.
  - At the note's point the left side is 0.504, so it holds there.
  - It fails for low enough ĉ. At ĉ = 140 the markup rises from 17.22 to 17.86 as β goes from 0.25
    to 0.50.
- A cut in ĉ raises both P* and m*. "Margin and volume move together" follows from any cost
  advantage, so it cannot tell a structural advantage from a trading edge.

### 2.6 Risk loading
Under exponential (CARA) utility with coefficient a, the certainty equivalent of a cost is
E + (a/2)·Var + O(skewness). The note's φ·σ is a mean–standard-deviation rule. It is not that
certainty equivalent.

### 2.7 Logit non-collapsibility (x05)
Suppose wins follow σ(β(p_ref + u − p)) with u ~ N(0, τ²) unlogged.
- The population response is approximately σ(β_marg·(p_ref − p)), with
  β_marg = β/√(1 + πβ²τ²/8).
- At β = 0.33 and τ = 3, β_marg ≈ 0.280.
- Randomisation identifies β_marg, not β, and β_marg is what pricing on logged features needs. x05
  compares estimators against β_marg.

## 3. What cannot be tested here
- **Regulatory facts:**
  - A1–A3;
  - κ and the Class A limits;
  - the levy values that make up λ;
  - how P442/ESNA behave;
  - the MHHS dates.

  Each of these needs primary sources, and the user decided on no look-ups.
- **Proprietary data:**
  - the real β and p_ref;
  - π_at;
  - forecast error covariance;
  - the real sign and size of confounding in tem's quote log;
  - whether LightGBM plus a copula is adequate;
  - the "dominant" size of the G–D weather coupling.
- **Opinion:** the build order, what not to build, the refusal of RL, and governing φ.

## 4. Planning inputs (not results)
- **§7.4, recomputed.**
  - Unconstrained: p* = 159.746, win 0.678, markup 9.41, £1,594 per site per year.
  - Pass-through γ = 0.6: p = 154.204 (the note prints 154.19), win 0.929, £897.5 (the note
    prints 894).
  - No match: 164.40, win 0.312, £343.
- **§7.5, recomputed with Gaussian jitter at σ = 1/2/4.**
  - At p*: 1.71 / 6.37 / 20.65% (0.44% at σ = 0.5). The closed form gives 1.754%·σ².
  - At the γ = 0.6 price: 0.96 / 4.05 / 18.00%. This matches the note's 1.0 / 4.0 / 18.1%.
  - No match: 3.7 / 14.6 / 52.8%.
  - Cap-respecting half-normal jitter at the γ = 0.6 price: 9.60 / 19.56 / 40.20 / 83.05% at
    σ = 0.5 / 1 / 2 / 4.
- **x01 Part A pilot** (2,000 random instances, exact rational arithmetic):
  - the corrected dual table is feasible and optimal on all of them;
  - inframarginal μ > 0 in all 379 demand-scarce instances that have an inframarginal asset;
  - the ΣG regime rule misclassifies 425 of the 2,000.
- **x01 Part B pilot**, relative error of the dual valuation at q = 2%, in % (office / 24/7 /
  evening):

  | N | office | 24/7 | evening |
  |---|---|---|---|
  | 10 | 0.27 | 0.31 | 0.70 |
  | 20 | 0.74 | 0.73 | 1.29 |
  | 30 | 1.25 | 1.12 | 1.61 |
  | 40 | 1.74 | 1.54 | 1.42 |
  | 60 | 2.60 | 2.25 | 1.42 |
  | 100 | 5.29 | 3.77 | 2.49 |
- **x02 pilot**, overstatement O(r) with analytic means, in %:

  | r | 3.93 | 3.15 | 2.62 | 1.97 | 1.57 | 1.26 | 1.05 | 0.79 | 0.63 | 0.52 | 0.39 | 0.31 | 0.25 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | O | 6.5 | 9.7 | 12.9 | 12.2 | 11.4 | 10.9 | 9.0 | 7.2 | 6.6 | 6.2 | 4.0 | 1.7 | 0.1 |

  - Where the peak falls, by the pool's solar share θ_s: wind only ≈ 1.25; θ_s = 0.25 ≈ 1.56;
    0.5 ≈ 2.6; 0.75 bimodal (≈ 5.2 and 0.39); ≥ 0.9 ≈ 0.39.
  - Point-forecast marginal share minus the true share: +13 to +20 pp at N = 10, and −1.5 to −2.9 pp
    at N = 100.
- **x03 pilot**, marginal matched share in pool P71, in % (office / 24/7 / evening):

  | N | office | 24/7 | evening |
  |---|---|---|---|
  | 10 | 81.9 | 78.9 | 68.5 |
  | 20 | 61.1 | 57.2 | 43.5 |
  | 30 | 44.4 | 40.8 | 26.6 |
  | 40 | 31.7 | 29.1 | 17.6 |
  | 60 | 16.8 | 15.7 | 9.2 |
  | 100 | 4.0 | 4.4 | 2.4 |

  - R = 3.7, and the RMSE against the note's 18 cells is 2.95 pp.
  - In the solar-only pool P72: 42.2 / 34.6 / 23.7 at N = 20, and 27.7 / 23.4 / 15.2 at N = 40.
- **x05 pilot.**
  - Naive slope 0.28 / 0.20 / 0.12 at ρ = 0 / 0.5 / 0.8. The population slope β_marg is 0.280.
  - Gain from randomising: −1.0% / +3% / +33% of the horizon value at the same three ρ.

These pilots used a simplified toy close to v1, not v1 itself. The registered predictions carry
confidence levels that allow for the difference.
