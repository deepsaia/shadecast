# shadecast

### [deepsaia.github.io/shadecast](https://deepsaia.github.io/shadecast/): the proposal and the surrogate pipeline

The interactive dashboard runs locally, from your own physics output, with `make frontend` once and
then `uv run sdc serve`: step by step through the whole pipeline, every number from a real physics
run, maps drawn in your browser from raw model output so that hovering any pixel reads its actual
temperature.

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
sdc cities                        # the selected cities, their strata and what each has; sdc is short for shadecast
sdc build savannah                # assemble the densest tile's bundle, about a minute
sdc run savannah                  # the baseline physics for that tile, kept beside its bundle
sdc tile show savannah            # where its tiles live and which stages have run; reads disk only
sdc tile report savannah          # the tile's baseline, its physics run and every scored plan
sdc surrogate treeshade generate savannah --jobs 4   # physics for the 17 tree designs, 4 at a time
sdc surrogate treeshade train savannah      # fit the tree shade surrogate on that tile
sdc surrogate treeshade assess savannah     # judge the newest model against the engine
sdc results                       # the measured results across every tile with physics
sdc runs                          # what is generating or training right now, and whether it is alive
sdc serve                         # the API and the dashboard for whatever data is on disk
```

Every command takes the city name and means its densest tile unless told otherwise. One
generation run is one tile: the 17 designs are 17 engine runs over the same square kilometre.
To study more of a city, choose tiles explicitly and the same options carry through:

```bash
sdc tile list savannah                          # every tile of the centre, densest first
sdc build savannah --tiles t17N_488_3550,t17N_489_3550   # named tiles
sdc build savannah --stratified 3               # three tiles spread over built-fraction terciles
sdc build savannah --tiles all                  # every tile; about a minute each to build
sdc surrogate treeshade generate savannah --tiles all --jobs 4   # physics for every built tile
sdc surrogate treeshade train savannah --tiles all      # one model over every tile with physics
```

A tile's directory is `data/tiles/<urban centre id>/<tile id>/`, and `sdc tile show <city>`
prints it, so nobody needs to know the id.

## The dashboard

`sdc serve` serves the API and the dashboard for whatever data is on disk. The dashboard is a React client
built once into the server's static directory; the server never builds it and never regenerates data.

```bash
fnm use                           # Node from .node-version
make frontend                     # install the client's packages and build it into the server
sdc serve                         # http://127.0.0.1:8765/ with the API at /api/docs
```

An installed copy needs no Node. `make wheel` builds the client and then a wheel that carries it, so
`sdc serve` from a `pip install dist/shadecast-*.whl` serves the dashboard too.

Developing the client: `sdc serve --reload` in one terminal and `pnpm --dir frontend dev` in another; Vite
proxies `/api` and `/pages` to the server. `make types` regenerates the client's API types from the server's
schema, which is the one contract between them; CI fails when the committed types drift.

The physics engine is optional and lives in its own uv environment, which is what
keeps its GPL licence off this project:

```bash
brew install gdal
uv venv --python 3.12 .venv-engine
uv pip install --python .venv-engine solweig-gpu numba "gdal==$(gdal-config --version)"
```

See the [engineering notes](https://github.com/deepsaia/shadecast/issues/61) for why, and for the licensing boundary.

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

- **Phase 0 passed.** Ahmedabad end to end: data, physics, objectives, a greedy
  baseline, and a measured 1.52 C spillover that greedy cannot see.
- **Phase 1 passed.** Nine cities, zero failures, and the first cross city result:
  Lagos returns 38% more cooling benefit per dollar than Ahmedabad.
- **Phase 2 in progress.** The learned surrogate, which is what makes search
  affordable at all. How it is built, trained and judged is documented, with every
  number taken from a model manifest or a recorded run, in
  [the tree shade surrogate pipeline page](https://deepsaia.github.io/shadecast/model_pipeline.html).

Full proposal in [PROPOSAL.md](PROPOSAL.md).

## Data sources

All open, all unsigned, no API keys. Every dataset, model and paper this work rests on is cited
once, in `src/shadecast/cited_sources.json`, and the walkthrough's references section is
rendered from that file. Each built bundle records the source key and citation of every layer
in its `provenance.json`.

## Licence

Apache 2.0. The GPL physics engine stays behind a process wall; see [LICENSE](LICENSE).
