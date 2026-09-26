# Toy model v1 — specification

*Dated 2026-09-26. Stage B. It reconstructs the synthetic toy of design note §7
(`docs/tem-rosso-pricing-model-v1.md`, committed in b9291cd).*

- x01, x02 and x03 cite this file by the commit that adds it.
- A change after registration is a deviation in every PREREG that cites it.
- The note leaves most of these parameters unstated. The values below were chosen before any code
  existed. Claims are tested at the base config and across the grid in §8.

## 1. Time
- Days d = 0…364 and half-hours h = 0…47, with t = 48d + h (T = 17,520).
- Day 0 is a Monday. The weekday is d mod 7 (0 = Monday), and days 5 and 6 are the weekend.
- Clock time equals solar time, in UTC, with no DST.
- Half-hour midpoints fall at τ_h = (h + 0.5)/2 hours.
- The seasonal phase is S(d) = sin(2π(d − 79)/365). The winter phase is W(d) = cos(2π(d − 15)/365).

## 2. Solar (per MW of capacity)
- Daylength: L(d) = 12.2 + 4.3·S(d) hours. Sunrise is at τ_r = 12 − L/2 and sunset at τ_s = 12 + L/2.
- Clear-sky shape: c(d,h) = A(d)·sin(π(τ_h − τ_r)/L(d)) for τ_r < τ_h < τ_s, and 0 otherwise.
  The amplitude is A(d) = 1 + 0.6·S(d).
- Alternate clear-sky model, used only in the one-at-a-time (OAT) grid, "astro":
  - c = max(0, sin e), where sin e = sin φ·sin δ + cos φ·cos δ·cos H;
  - φ = 52°, δ = 23.44°·S(d), H = 15°·(τ_h − 12).
- Cloud latent: z_{s,t} is a stationary AR(1) over t, with φ_c = 0.95 and unit variance.
  z_{s,0} ~ N(0,1) and z_t = φ_c·z_{t−1} + √(1 − φ_c²)·ε_t.
- Clearness: k = σ(s_c·z), where σ is the logistic function; s_c = 1.5 in the base config.
- Output: g_sol = min(1, η·c·k) × 0.5 MWh per half-hour per MW.
  - η is solved with brentq so that the expected annual capacity factor is 0.117, i.e.
    1,024.92 MWh per MW per year.
  - The expectation over k is taken per half-hour with 64-point Gauss–Hermite quadrature.
  - η is recalibrated whenever s_c or the clear-sky model changes.

## 3. Wind (per MW)
- Latent: w_{s,t} is a stationary AR(1) with φ_w = 0.99 and unit variance.
- Capacity factor: CF = σ(μ_w + a_w·W(d) + s_w·w). Base values: s_w = 1.2, a_w = 0.
- μ_w is solved with brentq so that the expected annual mean CF is 0.30, using 64-point
  Gauss–Hermite quadrature per day. The base value is about −1.08.
- Output: g_wind = CF × 0.5 MWh per half-hour per MW.

## 4. Pools (expected annual energy)
- **P71** (§7.1): 7,800 MWh/yr, with a solar share θ_s by energy (base 0.5).
  - Solar MW = θ_s·7,800 / 1,024.92, which is 3.805 MW at the base.
  - Wind MW = (1 − θ_s)·7,800 / (0.30·8,760), which is 1.484 MW at the base.
- **P72** (§7.2): 6 MW of solar only, about 6,149.5 MWh/yr. The gen/demand ratio r is 1.23 at 20
  sites and 0.615 at 40.
- Premium π = 10 £/MWh on every asset, with λ = 45, so ν̄ = 35. x01 Part A uses its own random
  premiums.

## 5. Demand archetypes
Each shape f_a(d,h) is evaluated at τ_h and then scaled so that Σ_t f_a = 250 MWh/yr.
- **Office.**
  - On weekdays:
    - b_o before 07:00;
    - a linear ramp from b_o to 1 over 07:00–09:00;
    - 1 over 09:00–17:00;
    - a linear ramp from 1 to b_o over 17:00–19:00;
    - b_o after 19:00.
  - At weekends: b_o all day.
  - Base b_o = 0.35. Seasonal factor × (1 + 0.10·W(d)).
- **24/7.** 1 + a_f·cos(2π(τ_h − 14)/24), with base a_f = 0.10. Seasonal factor
  × (1 + 0.05·W(d)).
- **Evening venue.**
  - By time of day:
    - 0.6 over 00:00–01:00;
    - 0.15 over 01:00–10:00;
    - a linear ramp from 0.15 to e_m over 10:00–12:00;
    - e_m over 12:00–17:00;
    - a linear ramp from e_m to 1 over 17:00–18:00;
    - 1 over 18:00–23:00;
    - 0.8 over 23:00–24:00.
  - × 1.2 on Fridays and Saturdays from 17:00. Base e_m = 0.45.
  - Seasonal factor × (1 + 0.05·W(d)).

## 6. Demand noise (multiplicative, mean 1)
- **Per site i:** exp(s_i·ξ_i − s_i²/2), where ξ_i is a stationary AR(1) with φ_i = 0.9. Base
  s_i = 0.15.
- **Common to every site and prospect in a scenario:** exp(s_cm·c − s_cm²/2).
  - c = ρ_DG·z + √(1 − ρ_DG²)·c′, where c′ is a stationary AR(1) with φ = 0.99 and z is the cloud
    latent of §2.
  - Base s_cm = 0.05 and ρ_DG = 0.
- D_{i,s,t} = f_a(t) × site factor × common factor.

## 7. Book, prospects, cap and scenarios
- **Book.** Site i (i = 0, 1, 2, …) has archetype order[i mod 3], with order = (office, 24/7,
  evening). B_N is sites 0…N−1, so books are nested.
- **Book demand.** C_{N,s,t} = Σ_{i<N} min(D_{i,s,t}, κ), with κ = 2.5 MWh per half-hour. The cap is
  inert: sites peak near 0.05 MWh per half-hour.
- **Prospect of archetype a.** A fresh site with the stream `900000 + index(a)`, where office = 0,
  24/7 = 1 and evening = 2. It shares the scenario's common factor. An experiment scales it by a
  factor q, or uses it as one 250 MWh site.
- **Scenarios.** s = 0…S−1, with S = 120 weather-years.
  - Stream: `numpy.random.default_rng(SeedSequence([20260926, s, entity]))`.
  - Entities: cloud 1, wind 2, common demand 3, site i 1000 + i, prospect 900000 + index(a).
  - Every config and every experiment reuses the same streams, so draws are common random numbers.
  - The same ε stream feeds the invariance cells, which change φ.
- **Estimators.** Ratios of sums over scenarios and half-hours, never means of per-scenario ratios.
- **Economics.** λ = 45, π = 10, ν̄ = 35.

## 8. Configs
- **Base:** as above.
- **One-at-a-time (21 cells, one parameter changed per cell):**
  - θ_s ∈ {0.25, 0.75}
  - s_c ∈ {1.0, 2.0}
  - s_w ∈ {0.8, 1.6}
  - a_w = 0.4
  - b_o ∈ {0.2, 0.5}
  - a_f ∈ {0, 0.25}
  - e_m ∈ {0.25, 0.65}
  - s_i ∈ {0.05, 0.30}
  - s_cm ∈ {0, 0.10}
  - ρ_DG ∈ {−0.3, 0.3}
  - clear-sky "astro"
  - book order "shuffled": each block of 3 sites is permuted with
    `default_rng(SeedSequence([20260926, 7, block]))`.
- **Latin hypercube (40 cells):**
  - `scipy.stats.qmc.LatinHypercube(d=10, seed=20260926).random(40)`, scaled onto:
    - θ_s [0.2, 0.8]
    - s_c [1, 2]
    - s_w [0.8, 1.6]
    - a_w [0, 0.4]
    - b_o [0.2, 0.5]
    - a_f [0, 0.25]
    - e_m [0.25, 0.65]
    - s_i [0.05, 0.3]
    - s_cm [0, 0.1]
    - ρ_DG [−0.3, 0.3]
  - The columns are in that order.
- **Invariance (controls only; the φ values never enter a claim):** φ_c = 0.5; φ_w = 0.9; φ_i = 0.5.
  Every quantity in x01–x03 is a sum of per-half-hour expectations, so a change of φ moves it only
  by Monte Carlo noise.
- **Calibration control (every config):** these sample means lie within 4 standard errors of their
  targets, the standard errors taken over scenarios:
  - solar CF, target 0.117;
  - wind CF, target 0.30;
  - annual site volume, target 250;
  - P71 volume, target 7,800.
