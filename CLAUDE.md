# shadecast

Open, credential-free pipeline that turns any city into an urban-heat **decision**
problem, plus baselines and a benchmark.

- **shadecast**: this repo and library.
- **CoolBench**: the benchmark artifact it publishes (the paper).
- **Umbra**: the interactive instrument built on the same surrogate.

WRI's Cool Cities Lab solved the *forward* model (given an intervention, how much
cooler). This solves the *inverse* problem (given a budget, what should you build).

## The one rule

> **Credentials at build time, never at use time.**

Build time needs network but no account, key or quota. Use time is a frozen
bundle, offline, forever. A benchmark that requires three accounts is not a
benchmark.

## Licensing boundary

`solweig-gpu` is **GPL-3.0**. shadecast never imports it. `sim/runner.py` invokes
it as a **subprocess** through its own console script in its own environment, so
the GPL stays behind the process wall and shadecast can stay permissive. Do not
`import solweig_gpu` anywhere in `src/`.

## Two environments, both uv

| Env | Holds | Why |
|---|---|---|
| `.venv` | shadecast and the data stack | the library, permissively licensed |
| `.venv-engine` | solweig-gpu, GDAL bindings, numba | the GPL engine, isolated |

Both are uv. Keeping them separate is what holds the GPL boundary: shadecast never
imports the engine, and the two dependency sets never have to agree.

```bash
brew install gdal
uv venv --python 3.12 .venv-engine
uv pip install --python .venv-engine solweig-gpu numba "gdal==$(gdal-config --version)"
```

`solweig-gpu` has **undeclared dependencies** on GDAL Python bindings and numba,
which is why they are named explicitly above. The runner finds `.venv-engine`
automatically by walking up to the repo root; `SHADECAST_SOLWEIG_BIN` overrides it.

**Never modify a venv while a background job is running from it.** Adding a package
mid-run rebuilds the environment underneath the live process and kills it.

## Gotchas learned the hard way

- **Overture heights are effectively absent in the Global South.** Ahmedabad: 1 of
  14,213 buildings carried a height. GlobalBuildingAtlas gave 27,352 of 27,352, and
  50x faster because it is tiled by 5 degrees rather than needing a global scan.
- **Do not pick study areas by hand.** A city-centre coordinate lands in a
  commercial district that is empty at night. `aoi.select` scans GHS-POP for the
  densest window: Nairobi gained 99x population, Rio 98x.
- **SOLWEIG is pedestrian-level.** Its Tmrt over a building footprint is not a
  temperature anyone experiences. The dasymetric step puts everyone *inside*
  buildings, so scoring must go through `exposure.outdoor_weights` first. Skipping
  that silently scores the one mask where the physics does not apply.
- **Planetary Computer's SAS broker can partially fail.** On 2026-08-26 it 404ed for
  elevation and WorldCover while still serving Landsat. Terrain and land cover now
  come unsigned from AWS Open Data.
- **WorldPop refuses HTTP range requests**, so windowed reads are impossible and you
  must pull a whole country. GHS-POP is tiled and serves ranges.
- **Sky-view factor is cached by the engine.** Albedo edits (cool roofs, paving)
  reuse it and cost ~162 s; geometry edits (trees, shade) invalidate it and cost
  ~283 s. The action space should exploit that asymmetry.
- **macOS spawns rather than forks**, so anything invoking the engine needs a
  `__main__` guard.
- **`ruff` respects `.gitignore`.** An unanchored `data/` pattern meant to exclude
  built bundles also matched `src/shadecast/data/`, so ruff silently skipped six
  modules while reporting all checks passed. Anchor ignore patterns to the root.
- **A tree's cooling lands in its shadow, not on its own pixel.** Measured: 0.06 C
  at the tree, 0.88 C mean and 14.3 C peak at 1 to 2 m away.
- **Adding a tree does not only cool.** About 0.04 percent of outdoor pixels warm,
  by up to 10 C, all within 10 m of the new tree. That is longwave from warm canopy
  replacing cold sky. Do not constrain the surrogate output to be non-negative.

## Layout

```
src/shadecast/
  aoi.py           study-area grid, data-driven AOI selection
  cities.py        the 32-city stratified corpus
  build.py         assemble one bundle from open sources
  quality.py       data-quality tiering (A/B/C), never averaged away
  interventions.py action space: trees, cool roofs, paving, shade
  objectives.py    exposure, excess, people at risk, equity gap, cost
  exposure.py      residents to outdoor pixels (see gotcha above)
  data/            buildings, canopy, rasters, population, met, landcover
  sim/runner.py    subprocess wall around the GPL engine
  baselines/       greedy, and the search methods it has to beat
```

## Commands

```
shadecast list                     corpus and its stratification
shadecast build <city>             one bundle, credential-free
shadecast build --all              the whole corpus
shadecast run <bundle> <date>      physics, via the subprocess wall
pytest tests/ -q                   pure logic, no network, no engine
```

## Conventions

- Every claim in the docs should be a **measured** number, not an estimate. If it
  was not run, say so.
- Data-quality tiers are reported per city and results are **stratified by tier**,
  never pooled. A method must not look good only because it was evaluated where the
  inputs are best.
- No em-dashes in anything written for this project.

## Coding Guidelines and Best Practices

### General Principles
- Write clear, maintainable, and modular code.
- Prefer explicitness over cleverness.
- Keep functions and modules small and focused.
- Do not ever write nested functions or classes.
- Avoid duplication; reuse existing utilities where possible.
- Prioritize readability and maintainability over premature optimization.
- Use ruff and pyrefly.

### Code Style
- Follow PEP8 for formatting, naming conventions, and import conventions.
- Organize imports into standard library, third-party, and local modules.
- Use explicit type hints for all functions and methods.
- Avoid untyped interfaces unless absolutely necessary.

### Module Design
- Each module should have a single clear responsibility. And therefore have only a
  single class per module.
- Avoid excessively large modules or functions.
- Group related functionality logically within packages.
- Do not place anything logic inside `__init__.py`.
- Avoid global variables unless absolutely necessary.
- Favor simple, well-understood design patterns when appropriate.

### Error Handling and Logging
- Handle exceptions explicitly and consistently.
- Do not silently swallow exceptions.
- Provide meaningful error messages and logging.
- Use a structured logging approach instead of print statements.
- Ensure logs provide sufficient context for debugging and monitoring.

### Commits and PRs
- One commit per single task or single file. Keep each commit tightly scoped; never
  bundle unrelated changes.
- Single-line, simple commit messages. No body paragraphs unless truly needed.
- No co-authored trailer. Ever.
- No tool-attribution footer in commit messages or PR bodies.
- Absolutely no em-dashes anywhere in commit messages, PR text, code comments, or docs.
