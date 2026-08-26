# CoolBench

**A global, open benchmark for urban heat adaptation planning.**

Research proposal v3 . 2026-08-26 . Phases 0 and 1 passed.
Repo and library: `shadecast`. Benchmark artifact: **CoolBench**. Interactive instrument: **Umbra**.

---

## 1. The claim

WRI's Cool Cities Lab solved the forward model: given an intervention, how much cooler?
Nobody has solved the inverse problem: **given a budget, what should you build?**

CoolBench is a reproducible, physics-grounded environment in which an agent allocates a
finite adaptation budget across a real city to minimise heat-attributable exposure under
equity and robustness constraints. Built entirely from open global data requiring no
account, key or quota, with baselines spanning greedy, MILP, evolutionary,
quality-diversity and deep RL, plus zero-shot transfer to held-out cities.

**Target venues:** NeurIPS Datasets and Benchmarks, ICLR, Nature Cities, Climate Change AI.

## 2. Phase 0 result (passed 2026-08-26)

One square kilometre of Ahmedabad's old walled city, design day 2024-05-23 with a 46.4 C
peak, every input from open sources with no credentials. A greedy planner was given
10 million USD and told to plant trees.

| | Baseline | With plan | Change |
|---|---|---|---|
| Population-weighted outdoor Tmrt, daylight mean | 55.35 C | 49.42 C | **-5.93 C** |
| People above the 45 C stress threshold | 41,002 | 32,631 | **-8,370** |
| Canopy cover above 2 m | 10.3% | 21.7% | +11.4 pp |

Greedy targets correctly, planting where baseline Tmrt averages 64.8 C against an outdoor
mean of 55.8 C. Local cooling where planted: **17.84 C mean, 27.19 C max**.

### The finding that shapes the benchmark

Cooling spilled over to **unplanted** outdoor pixels by **1.52 C**. That is spatial
interaction: a tree shades its neighbours, so the marginal value of any placement depends
on every other placement. Greedy assumes independence and structurally cannot see it. The
gap between greedy and an interaction-aware search is the headroom this benchmark exists
to measure, now quantified rather than asserted. It is the empirical reason evolutionary
search, quality-diversity and RL belong in the paper.

### Timing, and why the surrogate is load-bearing

| Measure | Value |
|---|---|
| Build a whole city bundle, credential-free | 37.8 s |
| SOLWEIG per km2, warm (sky-view factor cached) | 162 s |
| SOLWEIG per km2, cold (geometry changed) | 283 s |
| One 1,000-evaluation search, one city | 45 to 78 h |

The corpus is 30 cities. Without a learned response model the benchmark is not runnable,
which makes the surrogate a contribution rather than an implementation detail. Useful
asymmetry: sky-view factor is cached, so albedo interventions (cool roofs, paving) are
1.7x cheaper to evaluate than geometry interventions (trees, shade).


## 2b. Phase 1 result (passed 2026-08-26)

**Exit criterion:** any listed city rebuilds from scratch, deterministically, with one
command, credential-free. **Nine cities built, zero failures**, plus a full
plan-and-evaluate loop on a second continent with no code changes.

### Study areas are chosen from data, not by hand

A city-centre coordinate usually lands in a commercial district that is empty at night.

| City | Population at seed | At selected AOI | Factor |
|---|---|---|---|
| Ahmedabad | 56,631 | 101,644 | 1.8x |
| Nairobi | 1,562 | **154,245** | **99x** |
| Rio de Janeiro | 540 | **53,134** | **98x** |

**This is a finding, not a convenience.** Naive centroid selection would have
systematically studied the wrong neighbourhoods, and in the Global South that means
missing exactly the informal settlements where heat risk concentrates.

### Nine cities, all Tier A

| City | Build | Buildings | Built | Canopy | Population | Design day |
|---|---|---|---|---|---|---|
| Ahmedabad | 33.8 s | 1,833 | 32% | 14% | 101,644 | 2024-05-23 |
| Nairobi | 71.7 s | 5,115 | 47% | 5% | 154,245 | 2024-02-18 |
| Rio de Janeiro | 34.5 s | 2,096 | 30% | 20% | 53,134 | 2023-11-18 |
| Sydney | 32.4 s | 742 | 40% | 7% | 27,125 | 2023-12-09 |
| Lagos | 31.9 s | 2,969 | 58% | 0% | 108,903 | 2023-02-16 |
| London | 57.5 s | 1,372 | 33% | 12% | 27,467 | 2022-07-19 |
| Phoenix | 44.7 s | 913 | 23% | 7% | 9,167 | 2025-08-07 |
| Jakarta | 43.0 s | 802 | 21% | 8% | 43,827 | 2024-09-07 |
| Khartoum | 30.4 s | 4,863 | 28% | 0% | 14,646 | 2023-05-26 |

Design-day selection is seasonally correct everywhere without special-casing: northern
cities pick their summer, southern cities pick theirs, equatorial Jakarta picks its dry
season. All 32 corpus cities validate against the real GlobalBuildingAtlas listing,
including equator-crossing and prime-meridian-crossing tiles.

### Zero canopy is real, confirmed by an independent sensor

| City | Meta/WRI CHM (1 m) | ESA WorldCover woody (10 m) | Verdict |
|---|---|---|---|
| Lagos | 0.03%, max 2.0 m | **0.00%** | genuinely treeless |
| Khartoum | 2.16%, max 12.8 m | 0.03% | genuinely treeless |
| Nairobi | 14.2%, max 23.0 m | 4.7% | consistent |
| Rio | 40.4%, max 30.0 m | 21.1% | consistent |

Lagos genuinely has almost no trees across 108,903 people at 58% built fraction. Never
let a single model's silence stand as evidence on its own.

### The first comparative result

Same code, same budget, different continent.

| | Ahmedabad | Lagos |
|---|---|---|
| Baseline outdoor Tmrt (pop-weighted) | 55.35 C | 50.96 C |
| Change with a 10M USD plan | -5.93 C | -5.37 C |
| People moved below 45 C | 8,370 | **42,088** |
| Tmrt drop where planted | 17.84 C | 11.91 C |
| Spillover to unplanted ground | 1.52 C | 1.30 C |
| **Excess reduced per 1,000 USD** | **31.77** | **43.72** |

**Lagos returns 38% more benefit per dollar than Ahmedabad**, despite cooling each
planted pixel *less*. Lagos starts from zero canopy so every tree lands on genuinely
unshaded ground, and its exposed population is more than twice as dense, so each degree
reaches more people. That points the opposite way to where adaptation money currently
goes: the treeless, dense, tropical cities that are 9% of the literature appear to have
the highest return on adaptation spend.

Spillover reproduces across both cities, so spatial interaction is a stable property
rather than an Ahmedabad artefact. Greedy still cannot see it.

## 3. Why this problem

- ~489,000 heat-attributable deaths per year, 2000 to 2019. Roughly 90% are over 65.
- The June 2026 European heatwave killed an estimated 10,000 to 20,000 people.
- Urban poor exposed to extreme heat could rise 700% by 2050, worst in West Africa and SE Asia.

> 60% of cities have no heat policy. Only 12% have a Heat Action Plan. 88% have no
> dedicated heat budget. Fewer than 5% have ever evaluated the impact of a heat
> intervention.
> (Red Cross Red Crescent Climate Centre, Urban Heat Governance, 2026)

> Tropical cities account for merely 9% of mitigation studies despite facing the most
> severe heat-health risks.
> (Renewable and Sustainable Energy Reviews, 2026 review)

## 4. The gap

| What exists | What it does | Why it isn't this |
|---|---|---|
| WRI Cool Cities Lab (Mar 2026) | Forward model, evaluates predefined scenarios | By WRI's own papers it does **not** address optimisation, budget, cost, equity or multi-objective tradeoffs |
| GUHVI (2025) | Global heat *vulnerability* index | Diagnosis, not decision. We consume it as input |
| CityLearn, Building2Building | Gymnasium envs for building energy | Indoor. Nothing outdoors, nothing spatial |
| `weather2alert` | Gymnasium env for heat *alert issuance* | Warning policy, not capital allocation |
| Single-city heat optimisers | DL surrogate plus differential evolution | One city, local data, one plan, no transfer, no shared protocol |

## 5. Architecture: one rule

> **Credentials at build time, never at use time.**

`cities-cif` needs Earth Engine, a CDS key, and an AWS profile whose credentials live in
WRI's internal secrets. Fine for a hosted platform, fatal for a reproducible benchmark.
Build time (us, once, network but no accounts): pull layers, run physics, design the
sampling, fit the surrogate. Use time (anyone, offline): download a frozen bundle and run.

### Where we are better, not just faster

WRI uses UT-GLOBUS for heights, RMSE 9.1 m against LiDAR by its own paper. Measured on the
same Ahmedabad area:

| Source | Buildings | With height | Query time |
|---|---|---|---|
| Overture 2026-08-19.0 | 14,213 | **1 (0.0%)** | 298 s |
| GlobalBuildingAtlas LoD1 | **27,352** | **27,352 (100%)** | **6.0 s** |

One building in 14,213 carrying a height is a finding, not a config choice. It is a
measurable North/South data asymmetry that caps what heat modelling can claim in exactly
the cities that need it most.

## 6. Verified data chain

All tested end to end in Phase 0. No account, key or quota anywhere.

| Layer | Source | Access |
|---|---|---|
| Buildings and heights | GlobalBuildingAtlas LoD1 | Source Cooperative, anonymous GeoParquet |
| Terrain | Copernicus DEM GLO-30 | Planetary Computer STAC |
| Canopy height | Meta and WRI 1 m CHM | AWS Open Data, anonymous S3 |
| Land cover | ESA WorldCover 10 m | Planetary Computer STAC |
| Population | GHS-POP R2023A 100 m | JRC, tiled, range requests |
| Meteorology | ERA5 via Open-Meteo | Public HTTP, no key |
| Validation thermal | Landsat 8/9, ECOSTRESS | Planetary Computer STAC |
| Physics | SOLWEIG-GPU 2.0.0 | PyPI |

Google Earth Engine is not required for anything. WorldPop was rejected because its server
refuses HTTP range requests, forcing a whole-country download.

## 7. Four tracks

| Track | Task | Which method should win |
|---|---|---|
| **A** Single period | Fixed budget, one shot | MILP and greedy. If RL loses, that is a finding |
| **B** Multi-period | 20 years, tree growth, discounting | RL: non-stationary, delayed reward |
| **C** Zero-shot transfer | Train data-rich, deploy unseen | Targets the 46% LA to Beijing degradation and the 9% equity gap |
| **D** Portfolio | A *set* of distinct plans, scored on QD coverage | MAP-Elites. Sharpest novelty |

## 8. Method ladder

Supervised ML (the surrogate) . Design of experiments (which physics runs to spend) .
Exact and heuristic OR (MILP, greedy) . Evolutionary strategies (CMA-ES, NSGA-II) .
Quality-diversity (MAP-Elites) . Deep RL (PPO, graph RL) . Robust decision making
(scenario discovery, regret ranking).

## 9. What we will not claim

- **SOLWEIG models outdoor thermal comfort, not indoor air temperature.** Most mortality,
  especially among the over-65s, is indoor-mediated. We do not claim deaths averted.
  *Phase 0 found this as a real bug:* Tmrt over a building footprint is not a temperature
  anyone experiences, yet the dasymetric step places everyone inside buildings, so the
  first scoring pass weighted the physics by exactly the mask where it does not apply.
  Fixed by redistributing residents onto outdoor pixels within walking reach.
- **Exposure-response functions do not exist for most target cities.** MCC covers 604
  locations in 39 countries, skewed to the Global North. We report where it is extrapolated.
- **Equity is proxied by population density, which is weak.** Phase 0 measured a negative
  equity gap: the densest areas are cooler at pedestrian level by day, probably because
  dense low-rise fabric self-shades its own streets. Real, but needs a deprivation surface.
- **A benchmark is not a deployment.**

## 10. Phases

| # | Phase | Weeks | Status |
|---|---|---|---|
| 0 | One-city vertical slice | 1 to 4 | **PASSED 2026-08-26** |
| 1 | Data pipeline generalised across cities | 4 to 8 | **PASSED 2026-08-26** |
| 2 | The surrogate, 100x faster at equal tolerance | 8 to 12 | next |
| 3 | Gymnasium env, Tracks A and B | 12 to 18 | |
| 4 | Tracks C and D | 18 to 24 | |
| 5 | Validation, ablations, paper | 24 to 30 | |

## 11. Umbra, the second artifact

Named for the fully shaded core of a shadow, which is what SOLWEIG computes.

En-ROADS works as a negotiation instrument because it answers in 60 ms. It is global,
system dynamics, and about mitigation, so there is no overlap. The two nest: En-ROADS
gives the planet's trajectory, Umbra gives where to plant trees on a block given that
trajectory. The surrogate is the only thing standing between us and that instrument.

## 12. Open issues

- No validation against ECOSTRESS or Landsat LST yet.
- Cost parameters are order-of-magnitude placeholders.
- Cool roofs and cool paving need UMEP surface classes absent from the stock table.
- solweig-gpu 2.0.0 has undeclared dependencies on GDAL bindings and numba, and hardcodes
  CUDA-or-CPU with no Apple Silicon path. Worth reporting upstream.
- Both WRI repos have no license file set. Needs resolving before we depend on them.

See `PHASE0.md` and `PHASE1.md` for the full evidence logs.
