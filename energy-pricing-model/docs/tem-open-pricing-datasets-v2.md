# Open Datasets for a Reference Electricity Pricing Model
 
### Evidence review of tem's market position, inferred data requirements, and a proposed open-data stack
 
*Research date: August 2026. Every substantive claim is linked to a primary or authoritative secondary source; inferences are labelled as such. Charging methodologies, levy rates and settlement rules change at least annually — treat all rate-bearing sources as live feeds, not static downloads.*
 
---
 
## 1. Purpose and method
 
The brief asks three questions in sequence: what markets and customers tem serves; what data must therefore power Rosso; and which **open datasets** could reproduce an equivalent pricing model in public.
 
Method: desk research on tem's own published material and funding coverage, then tracing of the regulatory mechanism that makes the commercial model work, then a catalogue of open data mapped to each component of a pricing engine.
 
**Acronyms are defined at first use.** The GB electricity market is unusually acronym-dense and several of the definitions are load-bearing for the argument.
 
---
 
## 2. What tem is: the public record
 
| Claim | Evidence |
|---|---|
| Not a licensed supplier; does not trade wholesale | *"We don't buy power from the wholesale market, and we don't operate like a traditional supplier… For compliance, we work with a licensed supply partner"* — [tem FAQs](https://www.tem.energy/faqs) |
| Supply delivered via a licensed partner | **P3P Partners Ltd** per [Smart Energy](https://www.smart-energy.uk/supplier-comparison/tem-energy); **Versa Energy** named as registered party for Energy Ombudsman purposes per [Energy Costs](https://www.energycosts.co.uk/articles/tem-energy/) and [Business Energy Deals](https://www.businessenergydeals.co.uk/blog/tem-energy/) |
| Two products: Rosso (infrastructure), RED (the utility) | *"tem is the AI-native energy transaction infrastructure… RED™ is the utility that uses that system"* — [tem FAQs](https://www.tem.energy/faqs); [TechCrunch](https://techcrunch.com/2026/02/09/tem-raises-75m-to-remake-electricity-markets-using-ai/) |
| Scale: >2 TWh transacted in 2025, 2,600+ UK customers | [EU-Startups](https://www.eu-startups.com/2026/02/london-based-energy-transactions-scale-up-tem-raises-e62-9-million-to-become-the-stripe-of-energy/) |
| Earlier snapshot: 3,000+ sites across 1,000+ businesses | [Company profile](https://bitscale.ai/directory/tem) |
| $75m Series B led by Lightspeed; expansion to Texas and Australia | [TechCrunch](https://techcrunch.com/2026/02/09/tem-raises-75m-to-remake-electricity-markets-using-ai/) |
| Generation: solar, wind, hydro, anaerobic digestion; micro-site to large portfolio | [tem FAQs](https://www.tem.energy/faqs) |
| Eligibility skews to half-hourly metered sites; electricity only, no gas | [tem FAQs](https://www.tem.energy/faqs); [Smart Energy](https://www.smart-energy.uk/supplier-comparison/tem-energy) |
| Pass-through charges named by tem: TNUoS, capacity, Climate Change Levy, reactive power, excess capacity, metering | [tem out-of-contract rates](https://www.tem.energy/out-of-contract-rates) |
| tem's own framing of where cost sits | *"Non-commodity costs now make up over 60% of the average electricity bill for many SMEs in the UK"* — [tem blog](https://www.tem.energy/blog/) |
| Actively using the P442 exempt-supply route | *"A 2024 update (known as P442) made it fairer and more accessible, so we moved fast, applying on behalf of RED™ customers"* — [tem FAQs](https://www.tem.energy/faqs) |
 
**Definitions.** *Half-hourly (HH) settlement*: consumption settled across 48 daily periods, versus non-half-hourly (NHH) profile-based settlement ([Elexon, Profiling](https://www.elexon.co.uk/bsc/settlement/profiling/)). *TNUoS*: Transmission Network Use of System — the charge recovering GB transmission network costs, published by NESO ([NESO Data Portal](https://www.neso.energy/data-portal)). *CCL*: Climate Change Levy, a UK tax on business energy.
 
---
 
## 3. Customer and market profile
 
**Segment (inferred).** Applying the earlier ~3-sites-per-business ratio to 2,600+ customers implies roughly 7,000–8,000 sites. Against 2 TWh, that gives **≈250–300 MWh per site per year, or ~30 kW average load** — mid-market commercial (retail units, hotels, care homes, light manufacturing, venues), not micro-SME and not heavy industry. Named customers are consistent: Boohoo Group, Fever-Tree, Silverstone Circuit, Newcastle United FC ([EU-Startups](https://www.eu-startups.com/2026/02/london-based-energy-transactions-scale-up-tem-raises-e62-9-million-to-become-the-stripe-of-energy/)).
 
*This is an order-of-magnitude estimate derived from two published figures at different dates, not a measurement.*
 
**Market size.** DESNZ (Department for Energy Security and Net Zero) records the non-domestic sector as the largest consuming segment in GB — 58% of total electricity consumption in 2020 ([Subnational electricity and gas consumption statistics](https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/1079141/subnational_electricity_and_gas_consumption_summary_report_2020.pdf); [latest summary report](https://assets.publishing.service.gov.uk/media/6945728a033693d5d50eb83d/subnational-electricity-and-gas-consumption-summary-report-2024.pdf)). On roughly 290 TWh total GB demand, 2 TWh is on the order of ~1% of non-domestic volume.
 
**Competitive context.** Ofgem records **72 business energy suppliers currently active**, and business prices are not subject to the domestic price cap ([State of the energy market: retail](https://www.ofgem.gov.uk/research/state-energy-market-report-retail)).
 
**Geography.** UK only today ([tem FAQs](https://www.tem.energy/faqs)); Texas and Australia announced.
 
---
 
## 4. The mechanism that determines the data requirement
 
This is the load-bearing part of the analysis: tem's saving is not primarily a trading edge, it is **temporal coincidence under a regulatory exemption**.
 
- **BSC** — Balancing and Settlement Code, the GB rulebook for how electricity volumes are measured and financially settled ([Elexon](https://www.elexon.co.uk/bsc/mod-proposal/p442/)).
- **P442** *"amends the Balancing and Settlement Code (BSC) to allow for licence-exempt supply volumes to be excluded from the calculation used to assign levies to licensed suppliers that fund the Government Electricity Market Reform (EMR) programme (including the Contracts for Difference and Capacity Market mechanisms)"* — [Ofgem approval decision, May 2024](https://www.ofgem.gov.uk/decision/approval-bsc-modification-p442).
- **ESNA** — Exempt Supply Notification Agent, the third-party role P442 created, which *"would calculate the volumes of licensed and exempt supply, and submit them to central BSC Systems, based on metered data provided by the HHDC or Supplier"* ([Elexon P442](https://www.elexon.co.uk/bsc/mod-proposal/p442/)). ESNAs *"validate and match generation and consumption data"* ([Foot Anstey](https://www.footanstey.com/our-insights/articles-news/a-new-era-for-licence-exempt-supply-p442-and-class-a-guidance-updates/)).
- **The binding constraint:** *"Only electricity that is both generated and consumed within a single half-hourly period is reported as licence-exempt"* ([P442 explainer](https://www.businessenergydeals.co.uk/blog/p442/)), capped at **2.5 MWh per half-hour to commercial customers** ([Renewable Exchange, LES FAQs](https://www.renewable.exchange/renewables-explained/licence-exempt-supply-faqs)).
- **What is avoided:** CfD (Contracts for Difference) and CM (Capacity Market) levies, and under Licence Exempt Supply more broadly, RO (Renewables Obligation) and FiT (Feed-in Tariff) charges ([e-POWER](https://epower.net/navigating-licence-exempt-supply/)).
### Why this reframes the modelling problem
 
Margin is manufactured half-hour by half-hour, under a volume cap, from a finite generator pool. **Exempt-match capacity is therefore a congestible shared resource.** The marginal value of winning a customer depends on how their consumption shape correlates with the *unmatched residual* of the existing book — not on their standalone cost to serve. A daytime-only office and a 24/7 warehouse with identical annual kWh have very different marginal values.
 
That makes this a **portfolio pricing problem, not a cost-plus one** — which in turn determines every dataset below.
 
---
 
## 5. Inferred proprietary data (not open)
 
| Layer | Likely holdings | Role |
|---|---|---|
| Demand | HH consumption per MPAN (Meter Point Administration Number); GSP group, LLFC, profile class, measurement class | Demand leg of the match |
| Generation | HH export per MSID (Metering System Identifier); asset spec, location, availability | Supply leg of the match |
| Commercial | Quote → win/loss logs with price, tenor, broker, outcome; churn and renewal | The **only** source of price elasticity |
| Contractual | Generator offtake prices and tenor; ESNA-reported matched volume per half-hour | Realised vs modelled margin |
| Risk | Credit assessment, payment behaviour, bad debt | Risk-adjusted margin |
 
Corroboration: Crunchbase describes *"half-hourly data matching protocols that optimize electricity allocations using real-time demand and supply parameters"* ([Crunchbase](https://www.crunchbase.com/organization/tem-9f9a)); TechCrunch confirms *"machine learning algorithms and LLMs help predict supply and demand"* ([TechCrunch](https://techcrunch.com/2026/02/09/tem-raises-75m-to-remake-electricity-markets-using-ai/)).
 
---
 
## 6. Proposed open dataset stack
 
Ranked by marginal value to a pricing engine.
 
### 6.1 Tier 1 — irreducible core
 
| Dataset | Content | Access |
|---|---|---|
| **Elexon Insights Solution** (successor to BMRS, the Balancing Mechanism Reporting Service) | HH imbalance prices, system prices, Market Index Price, generation by fuel type, balancing acceptances, demand outturn and forecast | [developer.data.elexon.co.uk](https://developer.data.elexon.co.uk/) — *"All our APIs are public and no API key is required"*; UI at [bmrs.elexon.co.uk](https://bmrs.elexon.co.uk/) |
| **NESO Data Portal** (National Energy System Operator) | [Historic Demand Data](https://www.neso.energy/data-portal/historic-demand-data) — HH demand, interconnector, wind and solar outturn from 2001; [Demand Data Update](https://www.neso.energy/data-portal/daily-demand-update/demand_data_update); BSUoS (Balancing Services Use of System) and AAHEDC (Assistance for Areas of High Electricity Distribution Costs) tariffs; carbon intensity | [neso.energy/data-portal](https://www.neso.energy/data-portal); CKAN API at `api.neso.energy` |
| **NESO Embedded Wind & Solar Forecasts** | *"embedded wind and solar forecast from within day up to 14 days ahead"* at HH resolution, *"updated on an hourly basis"*, with yearly historic archives | [Dataset](https://www.neso.energy/data-portal/embedded-wind-and-solar-forecasts) |
| **NESO TNUoS tariffs (incl. Embedded Export)** | Locational Embedded Export, Avoided GSP Infrastructure Costs (AGIC) and phased residual; quarterly | [Dataset](https://www.neso.energy/data-portal/transmission-network-use-system-tnuos-tariffs/embedded_export_tariffs) |
| **Sheffield Solar PV_Live** | *"generation estimates for solar photovoltaic (PV) systems connected to the GB electricity network"* at HH resolution, national and regional by GSP (Grid Supply Point) or DNO licence area; *"funded by NESO to ensure the data PV_Live provides can remain open and free to access"* | [API](https://www.solar.sheffield.ac.uk/api/) · [Python client](https://github.com/SheffieldSolar/PV_Live-API) · [live dashboard](https://www.solar.sheffield.ac.uk/pvlive/) |
| **DUoS charging statements and CDCM models** | Distribution Use of System charges under the Common Distribution Charging Methodology: red/amber/green time-band unit rates, capacity, excess capacity and reactive power charges by LLFC (Line Loss Factor Class) | [DCUSA network charging](https://www.dcusa.co.uk/network-charges/) — *"updated biannually… by the first Working Day of each April and October"*; per-DNO, e.g. [ENWL](https://www.enwl.co.uk/about-us/regulatory-information/use-of-system-charges/current-charging-information/) publishes *"the fully populated CDCM model used to calculate the current year's charges"* |
| **Open-Meteo** (ERA5 reanalysis, Copernicus/ECMWF) | Hourly temperature, irradiance, wind from 1940; plus a **historical forecast archive from 2021** — essential for training without look-ahead bias | [open-meteo.com](https://open-meteo.com/) — *"HTTP GET, no authentication, CC BY 4.0 data licence"*; [Historical Weather API docs](https://open-meteo.com/en/docs/historical-weather-api); bulk via [AWS Open Data](https://registry.opendata.aws/open-meteo/) |
 
### 6.2 Tier 2 — asset and match layer
 
| Dataset | Content | Link |
|---|---|---|
| **REPD** — Renewable Energy Planning Database (DESNZ) | All UK renewable projects ≥150 kW through inception, planning, construction, operation and decommissioning, with capacity, technology, CfD allocation round and grid coordinates; quarterly | [gov.uk](https://www.gov.uk/government/publications/renewable-energy-planning-database-quarterly-extract) · [data.gov.uk](https://www.data.gov.uk/dataset/a5b0ed13-c960-49ce-b1f6-3a6bbe0db1b7/repd) |
| **ECR** — Embedded Capacity Register | *"generation and storage resources (≥50kW) that are connected, or accepted to connect"* to each distribution network; monthly | [NGED Connected Data Portal](https://connecteddata.nationalgrid.co.uk/dataset/embedded-capacity-register) · [UK Power Networks](https://ukpowernetworks.opendatasoft.com/pages/embedded_capacity_register/) · [Northern Powergrid national combined view](https://northernpowergrid.opendatasoft.com/explore/dataset/ecr_manual_combine_test/) |
| **Ofgem Renewable Electricity Register** (replaced the Renewables & CHP Register, May 2025) | Accredited station details; monthly per-station output underlies REGO issuance — *"One REGO certificate is issued per megawatt hour (MWh) of eligible renewable output"* | [Register](https://www.ofgem.gov.uk/environmental-programmes/renewable-electricity-register) · [REGO public reports](https://www.ofgem.gov.uk/renewables-energy-guarantees-origin-rego/contacts-publications-and-data/public-reports-and-data-rego) · [REGO scheme](https://www.ofgem.gov.uk/environmental-and-social-schemes/renewable-energy-guarantees-origin-rego) |
 
*REGO = Renewable Energy Guarantees of Origin.* Together, REPD + ECR + REGO issuance allow construction of a synthetic generator pool with real geography, technology mix and capacity-factor priors — the entire supply side of a reference matching engine, from public data alone.
 
### 6.3 Tier 3 — demand shape and customer features
 
Individual non-domestic HH data is **not** openly published in GB. These are the best available proxies.
 
| Dataset | Content | Link |
|---|---|---|
| **Elexon Load Profiles** | HH profiles for Profile Classes 3–8: Non-domestic Unrestricted, Non-domestic Economy 7, and four Maximum Demand load-factor bands (0–20%, 20–30%, 30–40%, >40%), by day type and season | [UKERC Energy Data Centre](https://ukerc.rl.ac.uk/cgi-bin/dataDiscover.pl?Action=detail&dataid=5af8ae29-86a7-4e8c-9fe4-1e2d99d9fb96) |
| **Elexon profiling methodology** | The settlement regression uses *"up to seven variables including temperature, sunset and day of the week"* — a free, validated weather→shape baseline | [Elexon Profiling](https://www.elexon.co.uk/bsc/settlement/profiling/) |
| **UKPN Standard Demand Profiles** | Yearly HH load-factor profiles for commercial, industrial, EV charging, bus depots, rail and data centres, *"developed using actual demand data from connected sites"* | [UKPN Open Data](https://ukpowernetworks.opendatasoft.com/explore/dataset/ukpn-standard-profiles-electricity-demand/) |
| **ND-NEED** — Non-Domestic National Energy Efficiency Data-Framework (DESNZ) | Metered electricity and gas for ~1.755m non-domestic buildings in England & Wales, based on Valuation Office Agency rating data, by building use and size | [Collection](https://www.gov.uk/government/collections/non-domestic-national-energy-efficiency-data-framework-nd-need) · [2024 report](https://assets.publishing.service.gov.uk/media/66b4dfe6ab418ab055593520/ND-NEED-2024-report.pdf) · [data.gov.uk](https://www.data.gov.uk/dataset/1715ab16-2a5a-49ac-8aef-0b9d0cf741b2/non-domestic-national-energy-efficiency-data-framework-nd-need) |
| **Non-domestic EPCs and DECs** — Energy Performance Certificates / Display Energy Certificates (MHCLG) | Per-building floor area, use class, postcode, rating; bulk download and REST API | [Guidance](https://epc.opendatacommunities.org/docs/guidance) · [Non-domestic API](https://epc.opendatacommunities.org/docs/api/non-domestic) · [Download guide](https://guides.opendatacommunities.org/article/40-energy-performance-certificates-download) |
| **DESNZ subnational electricity consumption** | Meter-point-based estimates by local authority, domestic/non-domestic split, with meter counts | [Summary report](https://assets.publishing.service.gov.uk/media/6945728a033693d5d50eb83d/subnational-electricity-and-gas-consumption-summary-report-2024.pdf) |
| **UK Business Counts** (ONS via Nomis, from the IDBR — Inter-Departmental Business Register) | Enterprise counts by 5-digit SIC (Standard Industrial Classification) and employment size band, from country down to MSOA | [nomisweb.co.uk/datasets/idbrent](https://www.nomisweb.co.uk/datasets/idbrent) · [ONS methodology](https://www.ons.gov.uk/businessindustryandtrade/business/activitysizeandlocation/methodologies/ukbusinessactivitysizeandlocationqmi) |
| **NREL End-Use Load Profiles** (US DOE) | *"calibrated and validated 15-minute resolution load profiles for all major residential and commercial building types and end uses"* — transfer-learning priors for verticals GB data does not cover | [NREL](https://www.nrel.gov/buildings/end-use-load-profiles) · [AWS Open Data](https://registry.opendata.aws/nrel-pds-building-stock/) |
 
### 6.4 Tier 4 — levy stack and price benchmarks
 
| Dataset | Content | Link |
|---|---|---|
| **LCCC Data Portal** — Low Carbon Contracts Company | Interim Levy Rate (ILR) determinations and daily income, eligible demand, actual and forecast CfD generation and payments, CM forecast cost; CSV, JSON and API | [dp.lowcarboncontracts.uk](https://dp.lowcarboncontracts.uk/dataset/) · [scheme dashboards](https://www.lowcarboncontracts.uk/resources/) |
| **EMRS** — EMR Settlement Ltd | *"the main rates and amounts used in the calculation of payments under both the Contracts for Difference (CfD)… and Capacity Market (CM) schemes"*, including the ILR and total annual capacity payments | [emrsettlement.co.uk](https://www.emrsettlement.co.uk/settlement-data/settlement-data-suppliers/) |
| **DESNZ Quarterly Energy Prices (QEP)** | *"Quarterly and annual gas and electricity prices for the non-domestic sector, including and excluding the Climate Change Levy (CCL), split into consumption size bands"*, plus international industrial comparisons | [gov.uk collection](https://www.gov.uk/government/collections/quarterly-energy-prices) |
| **Ofgem Data Portal** | Wholesale and retail market indicators; *"Every chart includes… a feature to allow you to download chart images and raw data in .csv format"* | [Data portal](https://www.ofgem.gov.uk/news-and-insight/data/data-portal) · [Retail market indicators](https://www.ofgem.gov.uk/news-and-insight/data/data-portal/retail-market-indicators) |
 
**Note.** The LCCC ILR and the EMRS capacity charge are *precisely* the amounts P442 exemption avoids. They are the numerator of the whole value proposition, and both are published openly and updated frequently.
 
### 6.5 International, for announced expansion
 
| Market | Source |
|---|---|
| Texas | [ERCOT Public Data Portal](https://www.ercot.com/services/mdt/data-portal) and [Market Information](https://www.ercot.com/mktinfo) — settlement point prices, load profiles, retail transaction and settlement data |
| Australia | [AEMO Data (NEM)](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem) and [NEMWeb](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/market-data-nemweb) — 5-minute dispatch prices, regional demand, unit-level generation; [aggregated price and demand](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/aggregated-data) |
 
Both are materially more open at the settlement layer than GB — a defensible argument for expansion sequencing.
 
---
 
## 7. Reference open pricing model
 
**Objective.** For a prospect with an expected consumption shape, in a given GSP group, choose a fixed p/kWh quote maximising expected portfolio margin × probability of signing, subject to the exempt-match capacity constraint.
 
**Architecture, in order of where effort belongs:**
 
1. **Probabilistic HH forecasts, both legs.** Quantile gradient-boosted models (or a hierarchical equivalent) for per-site demand and per-asset generation, conditioned on numerical weather prediction ensembles. Point forecasts are inadequate: cost is a *coincidence integral* over two uncertain series, and the covariance dominates the answer.
2. **Cost-to-serve simulator.** Monte Carlo over joint demand/generation scenarios → matched volume (capped at 2.5 MWh/HH), residual priced at forward or imbalance prices, levies netted per LCCC/EMRS rates, network charges applied by LLFC and time band. **This is where the intellectual value sits**, not in the optimiser.
3. **Win-probability model.** Calibrated classifier on quote outcomes. Price is **endogenous** — historical quotes were set by a policy already conditioned on winnability, so a naive elasticity estimate is confounded and an optimiser will confidently maximise a mirage. Requires deliberate price randomisation or a credible instrument.
4. **Optimiser — start with a heuristic.** Price = simulated cost at a chosen risk quantile, plus a margin set by a contextual bandit over a discretised price grid. Escalate to a two-stage stochastic program (first stage: quote price; recourse: balancing and generator procurement) only if portfolio constraints demonstrably bind.
**Why not reinforcement learning.** Feedback is sparse (weeks to a decision), delayed (margin realises over 12–36 months) and non-stationary (levy rates and network charges reset annually), and no simulator is faithful enough to train in. A contextual bandit with logged randomisation delivers most of the adaptive benefit with an auditable exploration budget.
 
**Communication artefact.** A per-quote price decomposition — commodity, expected matched share, avoided levies, network, shape risk premium, credit, margin — with the confidence interval on matched share shown explicitly. This doubles as the internal model-explanation tool and the customer-facing transparency product.
 
---
 
## 8. Gaps, risks and caveats
 
- **No open substitute for the quote/win log.** Open data supports a defensible *cost* model; it cannot yield *elasticity*. The highest-value internal investment is instrumenting the quoting pipeline with randomised price perturbation from day one.
- **No individual non-domestic HH data.** Everything in §6.3 is a class-average or building-stock proxy. Expect a real accuracy gap versus a model trained on actual MPAN data, and quantify it rather than hide it.
- **Regulatory dependence is the dominant model risk.** Practitioners note that *"future policy changes could affect its viability — including adjustments to exemption thresholds or levy rules"* ([e-POWER](https://epower.net/navigating-licence-exempt-supply/)), and DESNZ has signalled refreshed Class A supply-exemption guidance ([Foot Anstey](https://www.footanstey.com/our-insights/articles-news/a-new-era-for-licence-exempt-supply-p442-and-class-a-guidance-updates/)). Scenario-test margin under levy-rule change; do not treat the avoided levy as a constant.
- **A dated shape assumption.** MHHS (Market-wide Half-Hourly Settlement) changes what data exists: Elexon expects *"approximately 80 per cent of meters into the new arrangements by October 2026"*, completion in May 2027, and *"processing up to 500 billion half-hourly meter readings per year"* ([Elexon MHHS](https://www.elexon.co.uk/bsc/operational/market-wide-half-hourly-settlement/)). Models built on profile-class approximations have a defined shelf life.
- **Data-quality caveats to carry forward.** NESO flags *"some data quality issues"* and retrospective corrections to solar capacity and outturn in [Historic Demand Data](https://www.neso.energy/data-portal/historic-demand-data). PV_Live has changed GSP boundary definitions repeatedly (20220314 → 20250109 → 20251204 → 20260209), so regional historical series are **not boundary-stable** ([PV_Live API user guide](https://api.solar.sheffield.ac.uk/pvlive/gdocs)). REPD's threshold was 1 MW until 2021, so *"projects below 1MW that were going through planning system before 2021 may not be represented"* ([gov.uk](https://www.gov.uk/government/publications/renewable-energy-planning-database-quarterly-extract)).
- **Licensing.** Verify terms per source before commercial use. Open-Meteo is CC BY 4.0 ([open-meteo.com](https://open-meteo.com/)); Elexon Insights is public under BMRS Data Licence Terms ([developer portal](https://developer.data.elexon.co.uk/)); EPC data *"contains personal information covered by the Data Protection Act 2018 and the General Data Protection Regulation, as well as data under a restrictive licence"* ([EPC guidance](https://epc.opendatacommunities.org/docs/guidance)).
- **Savings claims are the company's own.** The "up to 30%" figure originates from tem and its investors ([tem FAQs](https://www.tem.energy/faqs); [Hitachi Ventures](https://medium.com/@HitachiVentures/tem-building-the-transaction-infrastructure-for-the-future-of-energy-de6420b0f2e8)) and is not independently verified in the sources reviewed here.
---
 
## 9. Source index
 
**tem primary:** [FAQs](https://www.tem.energy/faqs) · [Out-of-contract rates](https://www.tem.energy/out-of-contract-rates) · [Blog](https://www.tem.energy/blog/)
 
**Coverage and profiles:** [TechCrunch](https://techcrunch.com/2026/02/09/tem-raises-75m-to-remake-electricity-markets-using-ai/) · [EU-Startups](https://www.eu-startups.com/2026/02/london-based-energy-transactions-scale-up-tem-raises-e62-9-million-to-become-the-stripe-of-energy/) · [Hitachi Ventures](https://medium.com/@HitachiVentures/tem-building-the-transaction-infrastructure-for-the-future-of-energy-de6420b0f2e8) · [Crunchbase](https://www.crunchbase.com/organization/tem-9f9a) · [Smart Energy](https://www.smart-energy.uk/supplier-comparison/tem-energy) · [Energy Costs](https://www.energycosts.co.uk/articles/tem-energy/) · [Business Energy Deals](https://www.businessenergydeals.co.uk/blog/tem-energy/)
 
**Regulatory:** [Ofgem P442 decision](https://www.ofgem.gov.uk/decision/approval-bsc-modification-p442) · [Elexon P442](https://www.elexon.co.uk/bsc/mod-proposal/p442/) · [Foot Anstey, P442 and Class A](https://www.footanstey.com/our-insights/articles-news/a-new-era-for-licence-exempt-supply-p442-and-class-a-guidance-updates/) · [Renewable Exchange, LES FAQs](https://www.renewable.exchange/renewables-explained/licence-exempt-supply-faqs) · [e-POWER, Navigating LES](https://epower.net/navigating-licence-exempt-supply/) · [P442 explainer](https://www.businessenergydeals.co.uk/blog/p442/) · [Elexon MHHS](https://www.elexon.co.uk/bsc/operational/market-wide-half-hourly-settlement/) · [Ofgem State of the market: retail](https://www.ofgem.gov.uk/research/state-energy-market-report-retail)
 
**Datasets:** all linked inline in Section 6.
