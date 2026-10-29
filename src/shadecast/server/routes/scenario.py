"""A scenario on one tile: its outcomes as JSON, and the cooling and placement behind them as one array."""

from __future__ import annotations

from typing import Annotated

import numpy as np
from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi.responses import Response

from ...service.resample import downsample_stack
from ...service.scenario import Scenario
from ...service.scenario_outcome import ScenarioOutcome
from ..dependencies import services
from ..npy_response import npy_response
from ..services import Services

router = APIRouter(tags=["scenario"])


def levers(
    city: str,
    tile: str,
    *,
    kind: Annotated[str, Query(description="Intervention kind; tree is the one with a surrogate.")] = "tree",
    arrangement: Annotated[str, Query(description="clustered, scattered or corridor.")] = "clustered",
    coverage: Annotated[float | None, Query(description="Share of the feasible ground planted, 0 to 1.")] = None,
    budget_usd: Annotated[
        float | None, Query(description="Budget in USD; sets the coverage through the cost table.")
    ] = None,
) -> Scenario:
    """The scenario a request asks for: one parameter per lever, since FastAPI reads them from the signature."""
    return Scenario(
        target=city, tile=tile, kind=kind, arrangement=arrangement, coverage=coverage, budget_usd=budget_usd
    )


@router.get("/cities/{city}/tiles/{tile}/scenario", response_model=ScenarioOutcome)
def scenario(
    asked: Annotated[Scenario, Depends(levers)],
    found: Annotated[Services, Depends(services)],
) -> ScenarioOutcome:
    """The outcomes of the levers on this tile against doing nothing, from the tile's surrogate."""
    return found.scenarios.evaluate(asked).outcome


@router.get("/cities/{city}/tiles/{tile}/scenario/field", response_class=Response)
def scenario_field(
    asked: Annotated[Scenario, Depends(levers)],
    found: Annotated[Services, Depends(services)],
    size: Annotated[int | None, Query(ge=8, le=4096, description="Long side in pixels.")] = None,
) -> Response:
    """The cooling field and the placement, stacked in that order, in NPY format, shrunk when asked."""
    answer = found.scenarios.evaluate(asked)
    stacked = np.stack([answer.cooling.astype("float32"), answer.placement.astype("float32")])
    if size is not None:
        stacked = np.asarray(downsample_stack(stacked, size), dtype=np.float32)
    return npy_response(stacked)
