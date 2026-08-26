# Phase 1: generalise across cities

**Exit criterion:** any listed city rebuilds from scratch, deterministically, with one
command, credential-free.

**Status: PASSED.** 2026-08-26. Nine cities built, zero failures, plus a full
plan-and-evaluate loop on a second continent with no code changes.

---

## 1. The corpus

32 cities, stratified by Koppen zone and World Bank income group.

| Property | Value |
|---|---|
| Cities | 32 |
| Global South | 22 (69%) |
| Tropical (Koppen A) | 10 (31%) |
| Arid (Koppen B) | 10 (31%) |
| Southern hemisphere | 8 |
| Overlapping WRI Cool Cities Lab | 6 |
| Regions / Koppen classes | 8 / 9 |

The 31% tropical share is deliberate. A 2026 review found tropical cities to be only
9% of urban-heat mitigation studies despite carrying the worst risk, so the corpus
over-samples them by design. The 6 WRI-overlapping cities are the cross-validation
set: our independently built bundles should agree with their published UTCI, and any
disagreement is informative.

## 2. Study areas are chosen from data, not by hand

A city-centre coordinate is a bad study area. It usually lands in a commercial
district that is empty at night, and the first hand-picked Ahmedabad centre sat on the
Sabarmati and pulled 21% water. `aoi.select` instead scans GHS-POP within 16 km of the
seed and takes the densest window.

| City | Population at seed | At selected AOI | Factor | Moved |
|---|---|---|---|---|
| Ahmedabad | 56,631 | 101,644 | 1.8x | 3.1 km |
| Nairobi | 1,562 | **154,245** | **99x** | 6.8 km |
| Rio de Janeiro | 540 | **53,134** | **98x** | 3.4 km |

**This is a finding, not a convenience.** Naive centroid selection would have
systematically studied the wrong neighbourhoods, and in the Global South that means
missing exactly the informal settlements where heat risk concentrates. The selector
found Nairobi's Eastlands and a dense residential area in Rio.

## 3. Nine cities, zero failures

Every risky geographic path is covered: southern hemisphere, equator-crossing tiles,
prime-meridian-crossing tiles, and western hemisphere.

| City | Tier | Build | Buildings | Built | Canopy | Population | Design day |
|---|---|---|---|---|---|---|---|
| Ahmedabad | A | 33.8 s | 1,833 | 32% | 14% | 101,644 | 2024-05-23 |
| Nairobi | A | 71.7 s | 5,115 | 47% | 5% | 154,245 | 2024-02-18 |
| Rio de Janeiro | A | 34.5 s | 2,096 | 30% | 20% | 53,134 | 2023-11-18 |
| Sydney | A | 32.4 s | 742 | 40% | 7% | 27,125 | 2023-12-09 |
| Lagos | A | 31.9 s | 2,969 | 58% | 0% | 108,903 | 2023-02-16 |
| London | A | 57.5 s | 1,372 | 33% | 12% | 27,467 | 2022-07-19 |
| Phoenix | A | 44.7 s | 913 | 23% | 7% | 9,167 | 2025-08-07 |
| Jakarta | A | 43.0 s | 802 | 21% | 8% | 43,827 | 2024-09-07 |
| Khartoum | A | 30.4 s | 4,863 | 28% | 0% | 14,646 | 2023-05-26 |

**Design-day selection is seasonally correct everywhere without special-casing.**
Northern-hemisphere cities pick summer (London July, Phoenix August, Ahmedabad May
pre-monsoon), southern-hemisphere cities pick their own summer (Rio November, Sydney
December, Nairobi February), and equatorial Jakarta picks its dry season.

All 32 corpus cities were validated against the real GlobalBuildingAtlas bucket
listing: 32 of 32 map to tiles that exist, including equator-crossing (Nairobi
`e035_n00_e040_s05`) and prime-meridian-crossing (London `w005_n55_e000_n50`).

## 4. Zero canopy is real, and confirmed by an independent sensor

Lagos and Khartoum initially tiered B for having no detectable canopy. That is
ambiguous: the trees may be absent, or the canopy model may have failed. So the tier
now cross-checks against a separate sensor. ESA WorldCover's tree and shrub classes
are derived independently of the 1 m canopy height model.

| City | Meta/WRI CHM (1 m) | ESA WorldCover woody (10 m) | Verdict |
|---|---|---|---|
| Lagos | 0.03% nonzero, max 2.0 m | **0.00%** | genuinely treeless |
| Khartoum | 2.16%, max 12.8 m | 0.03% | genuinely treeless |
| Nairobi | 14.2%, max 23.0 m | 4.7% | consistent |
| Rio | 40.4%, max 30.0 m | 21.1% | consistent |

Both sources agree. Lagos genuinely has almost no trees across 108,903 people at 58%
built fraction. That is now recorded as a property of the city rather than penalised
as a data defect, and it means maximum shade headroom.

This is the independent-witness pattern: never let a single model's silence stand as
evidence on its own.

## 5. The first comparative result

Same code, same budget, different continent. 10 million USD of greedy tree planting.

| | Ahmedabad | Lagos |
|---|---|---|
| Baseline outdoor Tmrt (pop-weighted) | 55.35 C | 50.96 C |
| With plan | 49.42 C | 45.58 C |
| Change | -5.93 C | -5.37 C |
| People above 45 C, before | 41,002 | 93,235 |
| People moved below it | 8,370 | **42,088** |
| Tmrt drop where planted | 17.84 C | 11.91 C |
| Spillover to unplanted ground | 1.52 C | 1.30 C |
| **Excess reduced per 1,000 USD** | **31.77** | **43.72** |

**Lagos returns 38% more benefit per dollar than Ahmedabad**, despite cooling each
planted pixel *less* (11.91 C against 17.84 C). The decomposition matters: Lagos starts
from zero canopy, so every tree lands on genuinely unshaded ground, and its exposed
population is more than twice as dense, so each degree of cooling reaches more people.

That is the kind of result this benchmark exists to produce, and it points the opposite
way to where adaptation money currently goes. The treeless, dense, tropical cities that
are 9% of the literature appear to have the highest return on adaptation spend.

Spillover reproduces across both cities (1.52 C and 1.30 C), so spatial interaction is
a stable property rather than an Ahmedabad artefact. Greedy still cannot see it.

## 6. Robustness work this phase forced

- **Planetary Computer's SAS broker partially failed** mid-phase, returning 404 for
  `elevationeuwest/copernicus` and `esaworldcover/esaworldcover` while still serving
  Landsat. Terrain and land cover moved to unsigned AWS Open Data. Fewer moving parts,
  and genuinely no credentials rather than anonymous-but-brokered.
- **Multi-tile handling** added for buildings, canopy and population, since cities near
  a 5-degree boundary straddle two or four tiles.
- **GPL boundary enforced.** solweig-gpu is GPL-3.0. `sim/runner.py` now invokes it as
  a subprocess through its own console script in its own environment, so shadecast can
  stay permissive. Nothing in `src/` imports it.
- **27 tests** covering UTM zone selection, grid snapping, tile addressing across all
  four hemispheres, exposure weighting, and the intervention model. No network, no
  engine, sub-second.

## 7. Still open

- Validation against ECOSTRESS and Landsat LST.
- Cool roofs and cool paving need UMEP surface classes absent from the stock table.
- Cost parameters remain order-of-magnitude placeholders.
- Deprivation surface, to interpret the persistently negative equity gap.
- The remaining 23 corpus cities.
