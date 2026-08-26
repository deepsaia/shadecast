# Pre-registration: which intervention type buys the most outdoor cooling?

Written **before** the experiment is run. Committed before any result is seen, so the
analysis cannot drift toward whatever came out.

This exists because the previous round did not do this. A spacing result was reported
at 2.1x, then retracted when the units turned out to compare a solid slab of canopy
against a planting density nobody uses. The failure was not the experiment, it was
running one without stating in advance what it would mean.

## The question

A city has a fixed budget. It can buy street trees, cool roofs, reflective pavement,
or shade structures. Which delivers the most reduction in pedestrian heat exposure per
dollar, and is the ranking the same in every city?

All 39 plans simulated so far are trees. Cool roofs cost 12 USD/m2 against trees at
40 USD/m2, a 3.3x difference that has never been tested.

## What is already known

Read first this time, rather than rediscovered at the cost of physics runs.

- Raising pavement reflectance lowers **surface** temperature by 10 to 13 C but raises
  **mean radiant temperature** by 5 to 7 C at midday, because the reflected shortwave
  lands on the pedestrian. Field measurement in Pacoima found Tmrt 4.5 to 5.8 C higher
  over cool pavement than untreated asphalt at midday.
- High-albedo surfaces can therefore increase heat stress at pedestrian level even
  while cooling the city as a whole.
- Street tree spacing around 6 m is the practical standard. Our own measured optimum
  of 8 m agrees with practice, which is why the spacing result was a null.

## Hypotheses and predictions

Each carries a number, so each can fail.

**H1. Reflective pavement will make pedestrians hotter, not cooler.**
Predicted daylight-mean Tmrt change at treated pixels: **negative** (warming), somewhere
between 1 and 7 C. Falsified if the model shows net cooling at treated pixels.

*This is the validation test.* Reproducing a counterintuitive published field result is
much stronger evidence that the pipeline is sound than any correlation against Landsat,
which cannot resolve pedestrian-level radiation at 100 m anyway.

**H2. Cool roofs will barely move pedestrian Tmrt.**
Predicted population-weighted outdoor change: **under 0.5 C** at equal budget to trees.
Roofs sit above the pedestrian, so most reflected shortwave leaves skyward.
Falsified if cool roofs deliver over 1 C.

**H3. Trees will dominate on cost-effectiveness despite costing 3.3x more per m2.**
Predicted ranking, best to worst: **trees, shade structures, cool roofs, reflective
pavement**, with pavement possibly negative. Falsified if any non-tree option beats
trees on cooling per 1,000 USD.

**H4. The ranking will hold in every city, unlike the objective conflict.**
Falsified if the best intervention type differs between Ahmedabad, Lagos and Rio.

## Design

Full factorial: 4 intervention types x 3 budgets (0.5M, 2.3M, 9.1M USD) x 3 cities,
36 cells. Placement is greedy-targeted within each type's own feasibility mask, at the
spacing already shown to be near-optimal for trees.

Every cell is a real engine run. No surrogate in the reported numbers; the surrogate is
used only to sanity-check before committing physics time.

## Analysis, fixed in advance

Primary outcome: population-weighted outdoor daylight-mean Tmrt change per 1,000 USD.
Secondary: people moved below 45 C, and change at treated pixels only (for H1).

Ranking by primary outcome within each city. H4 holds if the top type is the same in all
three. Effects under 0.1 C are reported as null rather than as small effects, because
that is below the surrogate error and near the noise of a single design.

## What would make me abandon this line

If all four types land within 20 percent of each other on the primary outcome, then
intervention type does not matter either, and the decision space that remains is budget
and district-scale placement. That result gets reported as a null, not reframed.

## Known limitation, stated up front

Reflective pavement and cool roofs act through albedo, which SOLWEIG reads from its
surface-class table. The stock table has no high-albedo classes, so shadecast supplies
its own. Any error in those albedo values propagates directly into H1 and H2, and the
values used are recorded alongside the result.

---

# Round two: the surface temperature channel and the network objective

Written **before** either experiment is run, and appended rather than edited, so the
first round stands exactly as it was filed.

## What round one changed

**H1 is no longer just a hypothesis about pavement. It is a test of the engine.**

The engine reported reflective pavement *cooling* pedestrians by 2.59 C. Arithmetic from
SOLWEIG's own constants gives roughly 0.83 C of warming, and field measurement over 58 km
of treated street in Phoenix reports that pedestrian mean radiant temperature rises
significantly on the road, with no significant change on the sidewalk
(Nature Communications 14, 1467, 2023). Two independent sources say warming; this engine
says cooling, with the sign inverted and the magnitude about 3x.

The reading is therefore that **H1 predicted correctly and the engine is wrong**, not that
H1 failed. The albedo arms stay quarantined until that is resolved. Phoenix becomes the
falsification target for any fix: a corrected engine must warm the road and leave the
sidewalk roughly unchanged. That road-versus-sidewalk split is a sharper test than the
overall sign, because it is a spatial pattern a coincidence is unlikely to reproduce.

## Arms grouped by channel

Naming arms by what they are called hid the thing that matters, which is the physical
channel each acts through, because the channel decides how far the number can be trusted.

| Channel | Arms | Status |
|---|---|---|
| Geometry, shading | trees, shade structures | validated |
| Surface temperature, longwave | de-paving, permeable paving | new, this round |
| Shortwave albedo | cool roofs, reflective paving | quarantined |
| Directional reflectance | retro-reflective materials | not representable |

Retro-reflective materials are the physically correct version of the albedo arm, returning
solar radiation skyward instead of scattering it onto the street, with reported canyon
surface reductions up to 20 C (Nature Cities, 2024). They cannot be represented here at
all: SOLWEIG assumes Lambertian reflection, and building albedo is a single module-level
scalar in this engine rather than a spatial field. This is recorded as a stated limit of
the benchmark, not carried as an untested arm.

## Hypotheses, round two

**H5. De-paving cools, and does so without the albedo pathology.**
Converting sealed surface to unmanaged grass moves the surface temperature coefficient
from 0.58 to 0.21 while changing albedo only from 0.18 to 0.16. Predicted daylight-mean
change at treated pixels: **cooling, 0.5 to 3 C**. Falsified if de-paving warms
pedestrians. Because the residual albedo change is adverse, any cooling measured is a
lower bound, which makes a warming result hard to explain away.

**H6. The surface temperature channel is monotone in its own parameter.**
Predicted ordering of cooling at treated pixels: **grass (0.21) > cobble (0.37) > 0**.
Falsified if permeable paving out-cools grass. This is an internal consistency check on
the engine that needs no external data, and it is exactly the kind of dimensional check
whose absence produced the retracted spacing result.

**H7. Trees still win on cost-effectiveness, because shading beats emitting.**
Trees intercept the direct beam, which is the largest term in the pedestrian budget;
de-paving only reduces upwelling longwave. Predicted ranking on cooling per 1,000 USD:
**trees, de-paving, shade structures, permeable paving**. Falsified if de-paving beats
trees.

**H8. Route targeting and area targeting select materially different plans.**
This is the load-bearing hypothesis for the network objective. At equal budget, the plan
minimising population-weighted area exposure and the plan minimising trip-weighted route
exposure will **overlap by less than 70 percent** of placed units, and the route-targeted
plan will beat the area-targeted plan on experienced Tmrt by **at least 0.3 C**.
Falsified if overlap exceeds 90 percent, in which case the network objective adds nothing
and should be reported as redundant rather than kept for novelty.

**H9. The advantage of route targeting depends on how irregular the street network is.**
Shaded routing gives no benefit on a perfectly regular grid with uniform building heights,
because every alternative is equivalent (Scientific Reports, 2025). Predicted: the gain
from route targeting **correlates positively with network circuity** across Ahmedabad,
Lagos and Rio. Falsified if the gain is flat across cities, or runs the other way.

## Analysis, fixed in advance

For H5 to H7, the outcome and the reporting rule are unchanged from round one, so the two
rounds stay comparable.

For H8, plan overlap is the fraction of placed units common to both plans at equal budget
and equal intervention type. Experienced Tmrt is trip-weighted mean Tmrt along
perceived-cost-optimal routes, with detour aversion fixed at beta = 1.0 before any run.
Trip endpoints are drawn in proportion to nearby population with a fixed seed, and the
same endpoints score both plans.

The beta = 0 case is retained as a null control. At beta = 0 no walker detours, so the
route objective must report exactly zero avoided heat. If it ever reports otherwise, the
objective is measuring its own tie-breaking rather than shade, and the result is void.

## What would make me abandon the network objective

If H8 is falsified, the route objective is redundant with the area objective and gets
reported as a null. It would be easy to keep it anyway on the grounds that it is novel,
and that is precisely the temptation this file exists to remove.
