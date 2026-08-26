"""Data-quality tiering for a city bundle.

The corpus deliberately spans places with very different data density. Pretending
a Nairobi bundle is as well-constrained as a London one would be dishonest, and
would let a method look good simply by being evaluated where the inputs are best.
So every bundle carries a tier, results are stratified by it, and the reasons are
recorded rather than summarised away.
"""

from __future__ import annotations

import numpy as np

TIERS = {
    "A": "Complete inputs. Building heights near-complete, canopy present, clearly urban.",
    "B": "Usable with caveats. One input thin or the area only partly built up.",
    "C": "Weak. Treat results as indicative and report separately.",
}


def assess(
    prov: dict, building_h: np.ndarray, canopy: np.ndarray, landcover: np.ndarray, pop_total: float
) -> dict:
    reasons: list[str] = []
    notes: list[str] = []

    hc = float(prov.get("buildings", {}).get("height_completeness", 0.0))
    built = float((building_h > 0).mean())
    canopy_cover = float((canopy > 2).mean())
    water = float(np.mean(landcover == 80))

    if hc < 0.95:
        reasons.append(f"building height completeness {hc:.1%}")
    if built < 0.15:
        reasons.append(f"only {built:.1%} built, area may not be urban fabric")
    if water > 0.25:
        reasons.append(f"{water:.1%} water, thermal signal diluted")
    if canopy_cover < 0.01:
        # A canopy model reporting nothing is ambiguous: the trees may be absent,
        # or the model may have failed on this landscape. Cross-check against an
        # independent sensor. ESA WorldCover classes 10 and 20 are tree and shrub
        # cover at 10 m, derived separately from the 1 m canopy height model.
        wc_woody = float(np.mean((landcover == 10) | (landcover == 20)))
        if wc_woody < 0.02:
            # Both sources agree there is nothing there. That is a real property
            # of the city, not a data defect, and it means maximum shade headroom.
            notes.append(
                f"genuinely treeless: canopy {canopy_cover:.2%}, "
                f"independent land cover {wc_woody:.2%}"
            )
        else:
            reasons.append(
                f"canopy model reports {canopy_cover:.2%} but land cover "
                f"shows {wc_woody:.1%} woody: suspect a missing canopy tile"
            )
    if pop_total < 2000:
        reasons.append(f"only {pop_total:,.0f} people, exposure weighting is thin")

    tier = "A" if not reasons else ("B" if len(reasons) == 1 else "C")
    return {
        "tier": tier,
        "meaning": TIERS[tier],
        "reasons": reasons,
        "notes": notes,
        "metrics": {
            "height_completeness": round(hc, 4),
            "built_fraction": round(built, 4),
            "canopy_gt2m": round(canopy_cover, 4),
            "water_fraction": round(water, 4),
            "population": round(pop_total, 1),
        },
    }
