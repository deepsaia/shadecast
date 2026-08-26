# Results against the pre-registration

Each hypothesis below was committed to this repository, with its predicted number and its
falsification condition, **before** the experiment that tests it was run. See
`PREREGISTRATION.md`. Outcomes are recorded here as they came out, including the ones that
missed.

Every cell is a real engine run. No surrogate output appears in any number here.

Live walkthrough: <https://deepsaia.github.io/shadecast/>

## Settled

| | Hypothesis | Outcome |
|---|---|---|
| **H1** | Reflective pavement warms pedestrians | **Prediction upheld, engine at fault.** See quarantine below |
| **H3** | Trees win on cooling per dollar | **Supported**, 9 of 9 comparisons |
| **H4** | The ranking is city invariant | **Supported**, trees led in all three cities |
| **H5** | De-paving cools by 0.5 to 3 C on treated ground | **Direction confirmed, magnitude missed**: cooled in all 6 cells, mean 4.43 C, above the band |
| **H6** | Cooling follows the surface heating coefficient | **Supported**, grass 4.43 C against permeable 1.57 C, in every city |
| **H8** | Corridor targeting selects a different, better plan | **Supported**, plans share 1.7 percent, 3.89 C more cooling on walked routes |

## What each one measured

**H3 and H4, the intervention factorial.** 18 cells: two geometry-based types, three
budgets, three cities. Trees beat shade structures by 2.74x to 3.70x, mean 3.18x, with the
ratio nearly flat across an 18x span of budget and across three continents.

An unplanned result fell out of splitting the efficiency metric into its parts. The same
money buys **almost the same physics everywhere and up to 20.7x the human benefit**:

| Budget | Cooling varies by | People helped varies by |
|---|---|---|
| 0.5M | 1.40x | 19.9x |
| 2.3M | 1.27x | 18.8x |
| 9.1M | 1.49x | 20.7x |

Cooling transfers between cities. Who is standing in the cooled space does not. That makes
targeting, not thermal prediction, the hard part of the problem.

**H8, corridor targeting.** Two plans per city at one budget, both simulated, each scored on
both objectives. The pre-registered bars were overlap under 70 percent and an advantage of
at least 0.3 C; measured overlap was **1.7 percent** and the advantage **3.89 C**.

| City | Hot-ground plan | Corridor plan |
|---|---|---|
| Ahmedabad | 0.73 C | 7.06 C |
| Lagos | 1.43 C | 5.44 C |
| Rio | 1.21 C | 2.54 C |

Stated caveat: corridor targeting winning on the corridor measure is partly definitional,
since that is what it optimises. The findings that are not definitional are how little the
two plans overlap, the size of the gap, and that in Ahmedabad the corridor plan wins on the
area measure as well.

**H5 and H6, the surface temperature channel.** Each city paid for an extra control run
holding land cover unchanged, because the stored baseline was produced without a land cover
raster and comparing against it would have confounded de-paving with switching land cover
on. Treated-ground cooling, measured against that matched control:

| City | Grass (coef. 0.21) | Permeable (coef. 0.37) |
|---|---|---|
| Ahmedabad | 2.50 C | 1.02 C |
| Lagos | 4.73 C | 1.44 C |
| Rio | 6.06 C | 2.26 C |

H5's band was wrong and is recorded as a miss rather than widened after the fact. Note also
that an intervention cooling treated ground by 4.43 C moves the population-weighted city
figure by under 0.4 C, because it cools only the ground it replaces while a tree shades well
beyond its own footprint.

## Quarantined

**The albedo arms, cool roofs and reflective pavement.** Raising ground albedo makes this
engine report 2.59 C of cooling. Arithmetic from the model's own constants gives roughly
0.83 C of warming, and field measurement over 58 km of treated street in Phoenix reports
that pedestrian mean radiant temperature rises significantly on the road with no significant
change on the sidewalk (Nature Communications 14, 1467, 2023). Two independent sources say
warming; the engine says cooling, sign inverted and magnitude about 3x.

H1 therefore predicted correctly and the engine is wrong. The arms stay out of every result
above until that resolves. Phoenix is the falsification target for any fix, and the
road-versus-sidewalk split is the sharper test because a coincidence is unlikely to
reproduce a spatial pattern.

## Not representable

**Retro-reflective materials**, which return solar radiation skyward instead of scattering it
onto the street, are the physically correct version of the albedo arm. They cannot be
modelled here at all: SOLWEIG assumes Lambertian reflection, and building albedo is a single
module-level scalar rather than a spatial field. Recorded as a limit of the benchmark rather
than carried as an untested arm.

## Retracted

An earlier spacing result reported a 2.1x advantage for one arrangement. It compared a solid
slab of canopy against a planting density nobody uses, because the planner treated one raster
pixel as one tree when a pixel is one square metre of crown. Retracted. Pre-registration was
introduced in response, and the crown-based planner replaced the pixel-based one for trees.
