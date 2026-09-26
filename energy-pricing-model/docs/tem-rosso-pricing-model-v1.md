# A Minimal Pricing System for Exempt-Match Portfolio Supply

*Design note. Toy model with numbers; every assumption flagged. Companion to `tem-open-pricing-datasets-v2.md`.*

---

## 0. The claim in one paragraph

tem's margin is not a trading edge; it is **temporal coincidence rent** created under P442, and coincidence rent is a *congestible shared resource*. That single fact determines the whole architecture. The correct object to model is not a customer's standalone cost to serve but the **shadow price of exempt-match capacity in each half-hour**, $\nu_t$. Once you have $\nu_t$, pricing collapses to a textbook markup problem. Almost everything upstream of $\nu_t$ can be built from open data or simulation; almost nothing downstream of it can — the price-response side has no open analogue and must be bought with deliberate experimentation.

---

## 1. Notation and primitives

Half-hourly settlement periods $t \in \mathcal{T}$; customers $i$; generation assets $a$; a prospect $j$ with tenor $T_j$ and shape $d_{jt}$ (MWh/HH).

| Symbol | Meaning | Units |
|---|---|---|
| $F_t$ | commodity cost (forward, or imbalance for residual) | £/MWh |
| $\ell_t$ | **avoidable** levy stack — CfD ILR + CM; + RO + FiT under wider LES | £/MWh |
| $n_{it}$ | non-avoidable network/other — DUoS band rate, TNUoS, BSUoS, CCL, metering | £/MWh |
| $\pi_{at}$ | premium asset $a$ requires above its outside option (wholesale + embedded benefits + REGO) | £/MWh |
| $\kappa$ | per-customer exempt cap, 2.5 MWh/HH | MWh |
| $\lambda_t \equiv \ell_t$ | gross surplus per matched MWh | £/MWh |

**Assumption A1 (settlement).** Only volume both generated and consumed inside the same half-hour is exempt; there is no carry-over, no storage in scope. This is what makes the objective a *coincidence integral* rather than an energy balance.

**Assumption A2 (charge incidence).** Exemption removes $\ell_t$ but not $n_{it}$. Network charges, BSUoS and CCL follow the metered import regardless. *Verify per charge before trusting any margin number — this is the single most consequential accounting assumption in the model.*

**Assumption A3 (retail product).** Customers buy a fixed £/MWh for the tenor. tem therefore holds volume risk, shape risk and match-realisation risk. Everything about risk loading below follows from A3; if the product were pass-through, most of §5 disappears.

---

## 2. Layer 1 — distributional forecasts of *both* legs

Per-site demand $D_{it}$ and per-asset generation $G_{at}$, conditioned on numerical weather prediction, calendar and site features.

Model family: **quantile gradient boosting** (pinball loss, LightGBM) per archetype/asset class, plus a Gaussian copula on standardised residuals to restore cross-sectional dependence. Scenarios are drawn by conditioning demand and generation on the *same* NWP ensemble member — the weather-driven correlation between a solar farm's output and a customer's cooling load is the dominant coupling and must not be destroyed by independent sampling.

**Why distributional, not point.** Matched volume is $\min(G,D)$, which is *concave*. By Jensen,

$$\mathbb{E}\big[\min(G_t,D_t)\big]\;\le\;\min\big(\mathbb{E}G_t,\;\mathbb{E}D_t\big)$$

so a point-forecast pipeline **systematically overstates matched volume and therefore underprices**. This is not a rounding error; §7 measures it at 5–11% of matched volume, worst exactly where the book is best balanced.

---

## 3. Layer 2 — the allocation LP and the shadow price $\nu_t$

For one half-hour and one scenario:

$$
\max_{m_{iat}\ge 0}\;\sum_{i,a}(\lambda_t-\pi_{at})\,m_{iat}
$$
$$
\text{s.t.}\quad \sum_a m_{iat}\le \min(D_{it},\kappa)\ \ [\nu_{it}],\qquad
\sum_i m_{iat}\le G_{at}\ \ [\mu_{at}]
$$

**Structure.** With $\lambda_t$ common across customers, the LP is a transportation problem with a merit order on $\pi_{at}$: fill from cheapest generator upward. Two regimes:

- **Generation-scarce** ($\sum_a G_{at} < \sum_i \min(D_{it},\kappa)$): $\nu_{it}=0$, $\mu_{at}=\lambda_t-\pi_{at}$. Rent accrues to generators. Winning demand is worthless at the margin.
- **Demand-scarce**: $\nu_{it}=\lambda_t-\pi_{(k)t}$ where $k$ is the marginal asset; $\mu=0$ for inframarginal assets. **Demand is the scarce input and $\nu_t>0$.**

$\nu_t$ is the internal transfer price of matchable demand in half-hour $t$. It is the one number the sales engine actually needs from the physical model.

**Marginal value of a prospect.** In the simple one-price case ($\pi$ blended, $\bar\nu = \lambda-\pi$):

$$
\Delta V_j=\sum_t \lambda_t\Big[\min(G_t,D_t+d_{jt})-\min(G_t,D_t)\Big]
=\sum_t \bar\nu\,\min\!\big(d_{jt},\,(G_t-D_t)^+\big)
$$

Read that carefully: **a prospect is worth exactly what it can absorb of the book's unmatched surplus, and nothing more.** Two customers with identical annual kWh have different values purely through where their load sits relative to $(G_t-D_t)^+$.

Using duals is a first-order approximation, exact for prospects small relative to the book; because the value function is concave, duals **over**estimate the value of a large prospect. Rule: re-solve with and without whenever $Q_j$ exceeds ~2% of book volume.

---

## 4. Layer 3 — cost to serve

$$
C_j \;=\; \sum_{t\in T_j}\Big[\,d_{jt}\big(F_t+n_{jt}+\ell_t\big)\;-\;\nu_t\,\min(d_{jt},\kappa)\,\Big]\;+\;\text{credit}_j
$$

Everything is priced *gross* — full levy stack — and the exempt match enters as a **credit**, valued at the shadow price, not the headline levy. That is the correct accounting when capacity is congested, and it is where cost-plus intuition goes wrong.

**Risk loading.** Monte Carlo over $S$ joint scenarios gives the distribution of $C_j$. Quote against

$$\hat c_j=\mathbb{E}[C_j]+\varphi\,\sigma(C_j)\quad\text{or}\quad \mathrm{CVaR}_\alpha(C_j)/Q_j$$

Mean–variance is the certainty equivalent of exponential utility to second order; $\varphi$ is a single tunable risk-aversion knob and should be governed, not learned.

---

## 5. Layer 4 — win probability and the price

$$
\mathbb{P}(\text{win}\mid p,x)=\sigma\big(\beta(x)\,(p_{\text{ref}}(x)-p)\big),\qquad \beta>0
$$

$p_{\text{ref}}$ is the price at which the deal is a coin flip — the competitive benchmark, a function of segment, broker, tenor, season. Expected profit $\Pi(p)=\mathbb{P}(p)\,(p-\hat c_j)\,Q_j$. Since $\mathbb{P}'=-\beta\mathbb{P}(1-\mathbb{P})$:

$$
\Pi'(p)=0\;\Longrightarrow\;\boxed{\,p^\star=\hat c_j+\frac{1}{\beta\,(1-\mathbb{P}(p^\star))}\,}
$$

A fixed point in one dimension; solve by bisection. Sanity checks: markup falls as price sensitivity $\beta$ rises; markup rises as you become more likely to win. **The entire optimiser is two scalars, $\hat c_j$ and $\beta$.** Do not build anything more elaborate until this is beaten in a live A/B.

**Strategic constraint.** Unconstrained, this formula prices just under the competitor and keeps most of the exempt rent (§7 shows it retaining ~£9.4/MWh). If tem's positioning is that customers get the saving, encode it as an explicit constraint rather than by corrupting the objective:

$$p\;\le\;\underbrace{F+n+\ell+\varphi\sigma}_{\text{gross}}\;-\;\gamma\,\bar\nu\,s_j,\qquad \gamma=\text{minimum customer pass-through share}$$

with $s_j$ the expected matched share. $\gamma$ is then a board-level dial with a legible price, not a hidden model artefact.

---

## 6. Layer 5 — discovering $\beta$ (the part no dataset gives you)

$\beta$ cannot be estimated from historical quotes. Prices were set by a policy already conditioned on winnability, so $\text{Cov}(p,\varepsilon)\ne 0$ and OLS/logit on the log is biased — usually toward *inelasticity*, which an optimiser will happily exploit into a mirage.

**Fix: log a known propensity.** Quote $p=p^\star+\varepsilon$, $\varepsilon\sim\mathcal{N}(0,\sigma^2)$ or a discretised markup grid under a **contextual bandit** (Thompson sampling on the logistic win model). Randomisation makes propensities known, which gives unbiased IPS/doubly-robust off-policy evaluation of any candidate policy:

$$\hat V(\pi)=\frac1N\sum_k \frac{\pi(m_k\mid x_k)}{\pi_0(m_k\mid x_k)}\,r_k$$

**Why the cost is trivially small.** At the optimum $\Pi'(p^\star)=0$, so by the envelope theorem

$$\mathbb{E}\big[\Pi(p^\star+\varepsilon)\big]\approx \Pi(p^\star)+\tfrac12\Pi''(p^\star)\sigma^2 = \Pi(p^\star)-O(\sigma^2)$$

Exploration loss is **second order**; the bias from a confounded elasticity estimate is **first order**. Measured in §7: £1/MWh of jitter costs 1.0% of expected margin. That is the cheapest information tem will ever buy, and the case for instrumenting the quoting pipeline on day one is essentially unanswerable.

**Reward attribution.** Margin realises over 12–36 months. Use modelled margin at signature as the immediate reward, then reconcile against ESNA-reported matched volume and re-fit — a two-timescale scheme, not end-to-end RL. Feedback here is sparse, delayed and non-stationary (levies and DUoS reset annually); nothing about it suits deep RL, and no simulator is faithful enough to train a policy in.

---

## 7. Toy model — 365 days × 48 HH, synthetic

Solar (daylength + seasonal-amplitude clear-sky × AR(1) cloud) and wind (AR(1) on logit CF, mean 0.30); three demand archetypes at 250 MWh/yr each (matching the ~30 kW average site inferred in the companion note); 120 Monte Carlo scenarios. Illustrative rates: $\lambda=£45$/MWh avoided levy, $\pi=£10$/MWh generator premium, so $\bar\nu=£35$/MWh.

### 7.1 Congestion is the dominant effect

Fixed generation pool (7.8 GWh/yr), growing book. Marginal matched share of *one more* 250 MWh site:

| Sites in book | gen ÷ demand | office | 24/7 | evening venue |
|---|---|---|---|---|
| 10 | 3.11 | 80.9% | 78.3% | 70.6% |
| 20 | 1.55 | 57.7% | 57.3% | 48.8% |
| 30 | 1.04 | 40.3% | 40.4% | 31.4% |
| 40 | 0.78 | 27.6% | 28.4% | 20.7% |
| 60 | 0.52 | 11.5% | 13.0% | 8.9% |
| 100 | 0.31 | 1.9% | 3.6% | 2.6% |

The same customer is worth **£7,079/yr** against a thin book and **£163/yr** against a saturated one. Any pricing model without a congestion term will be catastrophically wrong at one end of the growth curve — and the error is largest precisely when sales momentum is highest.

### 7.2 Shape differentiation (solar-only pool, 6 MW)

| Book | office | 24/7 | evening |
|---|---|---|---|
| 20 sites (gen/dem 1.23) | 43.5% | 33.1% | 23.8% |
| 40 sites (gen/dem 0.61) | 26.7% | 21.4% | 14.7% |

At 40 sites, office vs evening venue differ by 12 percentage points of matched share — **£4.2/MWh of cost to serve on identical annual volume**, against an optimal markup of £4–9/MWh. Shape is not a refinement; it is comparable in size to the entire margin.

### 7.3 The Jensen gap is real and peaks at balance

| gen ÷ demand | matched on mean shapes | E[matched] | overstatement |
|---|---|---|---|
| 1.55 | 4,416 MWh | 3,993 MWh | **10.6%** |
| 1.04 | 5,567 | 5,187 | 7.3% |
| 0.78 | 6,326 | 6,029 | 4.9% |
| 0.52 | 7,173 | 6,968 | 2.9% |

A deterministic pipeline books ~£10k/yr of phantom margin on a 10 GWh book here — and the error is worst in the regime you are trying to engineer.

### 7.4 The price

Office site, 40-site book, $\bar s_j=27.6\%$. Illustrative: commodity £78, network £34, avoidable levies £45 → gross £157/MWh. $\beta=0.33$/(£/MWh), $p_{\text{ref}}=£162$.

| | £/MWh |
|---|---|
| gross unit cost | 157.00 |
| exempt credit ($\bar\nu \times \bar s_j$) | −9.66 |
| risk loading ($\varphi\sigma$, $\varphi{=}0.5$, $\sigma{=}6$) | +3.00 |
| **risk-adjusted cost $\hat c_j$** | **150.34** |

| Policy | $p^\star$ | win prob | markup | E[margin/site/yr] |
|---|---|---|---|---|
| Unconstrained | 159.74 | 67.8% | 9.40 | £1,593 |
| Pass-through $\gamma=60\%$ | 154.19 | 92.9% | 3.85 | £894 |
| **No exempt match** | 164.39 | 31.2% | — | £343 |

The exempt match roughly **doubles expected margin per site while raising win probability from 31% to 93%** — margin per unit *and* volume move together, which is what a genuine structural cost advantage looks like and what a trading edge would not do.

### 7.5 Cost of experimentation

| jitter $\sigma$ | expected margin loss |
|---|---|
| £1/MWh | 1.0% |
| £2/MWh | 4.0% |
| £4/MWh | 18.1% |

Clean quadratic scaling, as the envelope argument predicts.

---

## 8. What is open, what is simulated, what must be experimented on

| Quantity | Source | Status |
|---|---|---|
| $\ell_t$ — CfD ILR, CM rates | LCCC Data Portal, EMRS | **Open, authoritative, live.** Literally the numerator of the value proposition |
| $n_{it}$ — DUoS bands, TNUoS, LLFC | DCUSA charging statements + CDCM models, NESO TNUoS | **Open**, biannual/annual. Mechanical, high fidelity |
| $F_t$ spot/imbalance | Elexon Insights (no API key) | **Open.** Forward curves are *not* — real gap; broker/ICE data or a curve model built off spot + seasonality |
| Weather, incl. forecast archive | Open-Meteo ERA5 + historical-forecast archive | **Open.** The archive matters more than the reanalysis: it removes look-ahead bias in training |
| Generation shapes | PV_Live, NESO embedded wind/solar forecasts | **Open**, HH, GSP-level. Beware PV_Live GSP boundary revisions — series are not boundary-stable |
| Asset pool geography and mix | REPD + Embedded Capacity Register + Ofgem REGO register | **Open.** Enough to synthesise a realistic generator pool with capacity-factor priors |
| Demand shapes | Elexon Load Profiles (PC 3–8), UKPN standard profiles, ND-NEED, non-domestic EPC | **Open but class-average only.** No individual non-domestic HH data exists publicly in GB |
| $\pi_{at}$ — generator reservation premium | — | **Discovered.** Procurement/negotiation outcomes; effectively a supply curve you learn by bidding |
| $\nu_t$ | LP over the above | **Computed**, then validated against ESNA-reported matched volume |
| $\beta$, $p_{\text{ref}}$ | — | **Experimentation only.** No open substitute, no proxy, no clever workaround |
| Forecast error covariance | — | Needs real MPAN data; open profiles understate idiosyncratic variance |

**Bright line:** open data can build a defensible *cost* model to within a quantifiable error. It cannot produce *elasticity*. Everything on the physics side is a data-engineering problem; everything on the human side is an experimental-design problem.

---

## 9. The case for simulating

Three distinct reasons, only the first of which is about missing data:

1. **The objective is a nonlinear functional of two uncertain series.** $\mathbb{E}[\min(G,D)]$ has no closed form under realistic dependence. Scenario simulation is not a convenience, it is the estimator.
2. **The counterfactual is unobservable.** "What would this book have earned had we won that customer / procured that farm?" is never in the data. A digital twin of the book is the only way to compute $\Delta V_j$ honestly, and it is the only way to backtest a pricing policy at all.
3. **A synthetic reference book is buildable from open data alone.** REPD + ECR give the asset pool with real geography and technology mix; PV_Live and NESO forecasts give shapes; Elexon/UKPN profiles and ND-NEED give demand archetypes and a plausible size distribution; nomis/IDBR gives the SIC-by-size-band population to sample customers from. That reproduces the entire physical layer in public — which is both a useful open benchmark and a sobering statement about where the real moat sits (the win/loss log and the generator relationships, not the physics).

Division of labour, stated bluntly: **simulate the physics, experiment on the humans.** Use the simulator to pre-screen policies and set risk loadings; never use it to learn price response.

---

## 10. Build order, and what I would refuse to build

1. **Instrument the quoting pipeline with logged randomisation.** Week one, before any modelling. It is the only irreversible decision here — every quote sent without a logged propensity is information destroyed forever.
2. **Scenario simulator + LP + $\nu_t$.** The cost engine. This is where the intellectual value sits.
3. **Quantile forecasters**, replacing archetype priors with real MPAN data as it accrues. Measure the improvement; the class-average gap is a number, not a vibe.
4. **Logistic win model + closed-form markup**, with $\beta$ from randomised data. Contextual bandit over a discretised markup grid once there are a few thousand logged quotes.
5. **Per-quote decomposition artefact** — commodity / matched share (with its confidence interval) / avoided levies / network / shape premium / credit / margin. Same object serves model debugging and customer-facing transparency, which is a rare alignment and worth exploiting.

**Would not build, in order of temptation:** deep RL (sparse, delayed, non-stationary, no faithful simulator); a monolithic multi-stage stochastic program before evidence that portfolio constraints bind across quotes; a learned end-to-end price policy that bypasses $\hat c_j$ — it will be unauditable exactly when a regulator or a customer asks why their price moved.

## 11. What breaks this

- **A2 is wrong somewhere.** If BSUoS or a network charge behaves differently than assumed under exempt supply, every margin number shifts. Audit against realised settlement before trusting the model.
- **$\lambda_t$ is a policy variable.** DESNZ refreshing Class A guidance or adjusting exemption thresholds moves the entire objective. Scenario-test margin under a levy-rule change; never treat avoided levy as constant in a 36-month contract.
- **MHHS changes what data exists** — ~80% of meters by October 2026, completion May 2027. Models resting on profile-class approximations have a defined shelf life, and that is good news: build the interfaces now so the archetype layer can be swapped for real HH data without touching the LP.
- **The cap.** The 2.5 MWh/HH per-customer figure and the aggregate Class A limits need confirming against current guidance; they set the shape of the feasible region and I have taken them on secondary sources.