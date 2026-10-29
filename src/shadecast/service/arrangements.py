"""The arrangements a person can choose, and the design family the physics ran for each.

A scenario names an arrangement; a simulated design names its family. The two vocabularies meet
here, so plan scoring and scenario evaluation agree on which designs are plans and what to call them.
"""

from __future__ import annotations

from .unknown_arrangement import UnknownArrangement

# arrangement -> design family in surrogate/designs.py
FAMILY_OF: dict[str, str] = {"clustered": "clustered", "scattered": "random_uniform", "corridor": "corridor"}
ARRANGEMENTS = tuple(FAMILY_OF)


def family_of(arrangement: str) -> str:
    """The design generator that draws this arrangement."""
    found = FAMILY_OF.get(arrangement)
    if found is None:
        raise UnknownArrangement(arrangement)
    return found


def arrangement_of(design_id: str) -> str:
    """The arrangement a simulated design belongs to; empty for a probe, which is not a plan."""
    family = design_id.rsplit("_", 1)[0]  # a design id is its family and a four digit seed
    for arrangement, known in FAMILY_OF.items():
        if known == family:
            return arrangement
    return ""
