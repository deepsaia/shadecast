# Phase 0: Ahmedabad vertical slice

Go/no-go evidence for CoolBench. Started 2026-08-26.

**Exit criterion:** Ahmedabad runs end to end, data through SOLWEIG through objectives
through a greedy baseline, reproducing plausible heat patterns.

**Status: PASSED.** Full loop closed on 2026-08-26. Data through SOLWEIG through
objectives through a greedy baseline, all from open data with no credentials.

---

## 1. The architecture decision

A benchmark that requires three accounts to run is not a benchmark. The rule:

> **Credentials at build time, never at use time.**

Build time (us, once, network required, no accounts): pull layers, run SOLWEIG,
design the intervention sampling, fit the surrogate.
Use time (anyone, offline, forever): download a frozen versioned bundle and run.

This is what separates a *benchmark* from a *pipeline*, and it is the reason we
build our own corpus rather than depending on WRI's live stack.

## 2. Why we are not consuming WRI's pipeline directly

WRI Cool Cities Lab (launched 2026-03-18) is validated and good science: SOLWEIG
plus UTCI at 1 m, MAE 0.39 degC against LiDAR-derived models. We adopt the method
and cite it. We do not adopt the pipeline, for three measured reasons.

**Credentials.** `cities-cif` requires Google Earth Engine access, a Copernicus CDS
API key, and an AWS profile named `cities-data-dev` whose credentials live in WRI's
internal secrets ("get in touch with Saif or Chris"). OpenUrban LULC is served only
as a Google Earth Engine asset.

**Input quality.** They use UT-GLOBUS for building heights, which reports **RMSE 9.1 m
against LiDAR** in its own paper. Three storeys of error in the input that drives
shadow geometry. This is why WRI cautions that their 1 m output has spatial
inaccuracies "well above 1 m" and advises against site-specific use.

**Speed.** Layers are pulled live per query rather than frozen.

## 3. Measured: the building-height source decision

Same Ahmedabad AOI, same query, no credentials either way.

| Source | Buildings | With height | Query time |
|---|---|---|---|
| Overture 2026-08-19.0 | 14,213 | **1 (0.0%)** | 298 s |
| GlobalBuildingAtlas LoD1 | **27,352** | **27,352 (100%)** | **6.0 s** |

GBA wins on every axis: 1.9x more buildings, complete heights against Overture's
effectively zero, and 50x faster because it is tiled by 5 degrees so one file covers
a city instead of a global scan. Native 3 m resolution, >97% global height
completeness, published in ESSD 2025.

**This is a finding, not just a config choice.** One building in 14,213 carrying a
height is a measurable Global North / South data asymmetry, and it directly caps
what heat modelling can claim in the cities that need it most. It belongs in the paper.

## 4. The verified credential-free stack

| Layer | Source | Access | Measured |
|---|---|---|---|
| Building footprints + heights | GlobalBuildingAtlas LoD1 | Source Cooperative, anonymous GeoParquet | 6,408 buildings, 100% heights |
| Terrain | Copernicus DEM GLO-30 | Planetary Computer STAC, anonymous SAS | 45.5 to 62.4 m asl |
| Canopy height | Meta/WRI 1 m CHM | AWS Open Data, anonymous S3 | 10.3% cover >2 m, max 39.7 m |
| Land cover | ESA WorldCover 10 m | Planetary Computer STAC | 97.4% built |
| Meteorology | ERA5 via Open-Meteo archive | Public HTTP, no key | 24 h UMEP forcing |
| Validation thermal | Landsat 8/9, ECOSTRESS | Planetary Computer STAC | 2,056 scenes over AOI |

**Google Earth Engine is not required for anything we use.** That matters given GEE
added monthly compute quotas to noncommercial tiers on 2026-04-27.

## 5. The Ahmedabad study area

1 km square at 1 m, centred on the old walled city (23.0225 N, 72.5850 E), EPSG:32643.
The first centre point sat on the Sabarmati and pulled 21% water, so it was moved east
into the dense fabric.

- 6,408 buildings, 100% with heights, max 18.1 m
- **48.0% built fraction**, 97.4% built land cover
- **10.3% canopy cover above 2 m**
- Design day **2024-05-23**: peak **46.4 degC** at 15:00, RH 11%, 940 W/m2 at noon

Dense, low-rise, nearly treeless, and genuinely dangerous. The right test case, and
the right validation case since Ahmedabad ran the first Heat Action Plan in South
Asia in 2013.

**Whole bundle builds in 37.8 seconds with no credentials.**

## 6. Defects found in solweig-gpu 2.0.0

Worth reporting upstream.

1. **No MPS path.** Device selection is hardcoded `torch.device('cuda' if
   torch.cuda.is_available() else 'cpu')`, so Apple Silicon silently runs on CPU
   despite a working MPS backend. Only 2 float64 uses exist and both are numpy, so
   MPS is not actually blocked, just unreachable.
2. **Undeclared dependency on GDAL Python bindings.** `preprocessor.py` imports
   `osgeo` but `gdal` is absent from `requires_dist`, so a clean install fails at run
   time rather than install time.
3. **`ERA_5_z0_find` defaults to True** even with `use_own_met=True`, producing a
   failed lookup on every run. Caught internally, so cosmetic, but it only affects
   the wind-extinction term for UTCI/WBGT, not Tmrt.

## 7. Measured: SOLWEIG runtime on CPU

1 km2 at 1 m (1000x1000 px), Apple M5 Max, CPU only, 18 workers. Note solweig-gpu
computes the whole 24 h diurnal cycle regardless of the requested window.

| Stage | Time | Recomputed when |
|---|---|---|
| Wall height and aspect | 28.9 s | building geometry changes |
| Sky view factor | 130.8 s | any geometry changes (trees, shade) |
| SOLWEIG radiation, 24 h | 115 to 122 s | every run |
| **Total, warm (SVF cached)** | **162 s** | albedo-only edits: cool roofs, cool paving |
| **Total, cold (SVF invalid)** | **283 s** | geometry edits: trees, shade |

**The caching asymmetry matters for the action space.** Albedo interventions are
1.7x cheaper to evaluate than geometry interventions. A search method that knows
this can spend its budget better.

**This is the surrogate justification, quantified.** At ~5 minutes per evaluation,
a CMA-ES run of 1,000 evaluations costs 45 to 78 hours for one city. The corpus is
30 cities. Without a learned surrogate the benchmark is not runnable, which makes
the surrogate a load-bearing contribution rather than an optimisation.

## 8. Result: the loop closes

Baseline: 1 km2 of Ahmedabad's old walled city, design day 2024-05-23.

Tmrt behaves exactly as physics demands. At night it collapses to air temperature
with almost no spatial spread. By 15:00 the median is 73.0 degC with a **30 degC gap
between deep shade (43.9) and full sun (79.7)**. That gap is the entire premise of
the project, now measured from open data.

**A methodological bug caught here and fixed.** SOLWEIG is a pedestrian-level model,
so its Tmrt over a building footprint is not a temperature anyone experiences. But
the dasymetric step places 100% of residents inside buildings, so the first scoring
pass weighted Tmrt by exactly the mask where the physics does not apply. Fixed by
redistributing residents onto outdoor pixels within walking reach (`exposure.py`).
This is the outdoor-exposure channel; indoor heat remains out of scope and unclaimed.

### Greedy tree-planting, 10M USD

| | Baseline | With plan | Change |
|---|---|---|---|
| Pop-weighted outdoor Tmrt, daylight mean | 55.35 degC | 49.42 degC | **-5.93 degC** |
| People above 45 degC | 41,002 | 32,631 | **-8,370** |
| Canopy above 2 m | 10.3% | 21.7% | +11.4 pp |

Greedy targets correctly: it plants where baseline Tmrt averages 64.8 degC against an
outdoor mean of 55.8 degC.

- Tmrt drop where planted: **17.84 degC mean, 27.19 degC max**
- **Spillover to unplanted outdoor pixels: 1.52 degC**

### The finding that shapes the benchmark

That 1.52 degC spillover is spatial interaction. A tree shades its neighbours, so the
marginal value of any placement depends on every other placement. **Greedy assumes
independence and therefore cannot see it.** The gap between greedy and an
interaction-aware search is the headroom this benchmark exists to measure, and it is
now quantified rather than asserted.

## 9. Still open

- Validation of simulated Tmrt against Landsat and ECOSTRESS LST.
- Deprivation surface. Population density is currently a weak equity proxy, and the
  measured equity gap is negative (dense low-rise fabric self-shades its own streets,
  so the densest areas are cooler at pedestrian level by day). Probably physically
  real, and policy-relevant, but it needs a proper deprivation layer to interpret.
- Cool-roof and cool-paving interventions need UMEP surface classes that do not exist
  in the stock table; CoolBench must ship an extended class file.
- Cost parameters are order-of-magnitude placeholders pending a real review.

## 10. Environment note

solweig-gpu needs GDAL Python bindings and numba, neither declared. Homebrew was
still resolving GDAL's dependency tree after 25 minutes with nothing installed, so
the simulation side runs in a conda-forge micromamba environment (`coolsim`) with
prebuilt binaries, while the data pipeline stays in uv. Two environments, one
boundary, documented in the build script.
