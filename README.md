# shadecast

Open, credential-free pipeline that turns any city into an urban heat **decision**
problem, plus baselines and a benchmark.

WRI's Cool Cities Lab solved the *forward* model: given an intervention, how much
cooler? shadecast solves the *inverse* problem: **given a budget, what should you
build?**

- **shadecast** is this repo and library.
- **CoolBench** is the benchmark artifact it publishes.
- **Umbra** is the interactive instrument built on the same surrogate.

## The one rule

> Credentials at build time, never at use time.

Build time needs network but no account, key or quota anywhere. Use time is a frozen
bundle, offline, forever. A benchmark that requires three accounts is not a benchmark.

## Quick start

```bash
uv sync
shadecast list                    # the 32 city corpus and its stratification
shadecast build ahmedabad         # assemble one bundle, about 35 seconds
shadecast plan data/cities/ahmedabad --kind tree --budget 10000000
```

The physics engine is optional and lives in its own environment. See
[CLAUDE.md](CLAUDE.md) for why, and for the licensing boundary.

## What it does

For any city it assembles a 1 metre simulation bundle from open global sources:
building footprints and heights, terrain, tree canopy, land cover, population and
meteorology. It then plans an adaptation portfolio (trees, cool roofs, reflective
paving, shade structures) against a budget and scores the result on population
weighted heat exposure, equity and cost.

Study areas are chosen from population density rather than by hand. Seeding on a
city centre coordinate found 1,562 residents in Nairobi; scanning for the densest
window found 154,245.

## Status

- **Phase 0 passed.** Ahmedabad end to end. See [PHASE0.md](PHASE0.md).
- **Phase 1 passed.** Nine cities, zero failures, first cross-city comparison. See
  [PHASE1.md](PHASE1.md).
- Next: the learned surrogate, which is what makes search affordable.

Full proposal in [PROPOSAL.md](PROPOSAL.md).

## Data sources

All open, all unsigned, no API keys.

| Layer | Source |
|---|---|
| Buildings and heights | GlobalBuildingAtlas LoD1 (Source Cooperative) |
| Terrain | Copernicus DEM GLO-30 (AWS Open Data) |
| Canopy height | Meta and WRI 1 m CHM (AWS Open Data) |
| Land cover | ESA WorldCover 10 m (AWS Open Data) |
| Population | GHS-POP R2023A 100 m (JRC) |
| Meteorology | ERA5 via Open-Meteo |
| Physics | SOLWEIG via solweig-gpu, run as a subprocess |

## Licence

Apache 2.0. The GPL physics engine stays behind a process wall; see [LICENSE](LICENSE).
