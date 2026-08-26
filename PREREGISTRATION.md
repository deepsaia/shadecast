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
