"""What a scenario is judged with but the physics never sees: the prices and the stress threshold."""

from __future__ import annotations

from dataclasses import dataclass

from ..interventions import CATALOGUE
from ..interventions import InterventionSpec
from ..objectives import TMRT_STRESS_C


@dataclass(frozen=True)
class Assumptions:
    spec: InterventionSpec  # the kind's prices
    threshold: float  # mean radiant temperature, degrees C, above which people count as exposed

    @classmethod
    def catalogue(cls, kind: str) -> Assumptions:
        """The placeholders: the catalogue's prices and the project's threshold."""
        return cls(spec=CATALOGUE[kind], threshold=TMRT_STRESS_C)
