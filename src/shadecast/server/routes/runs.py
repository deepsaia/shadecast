"""What is simulating or training right now."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends

from ...service.run_summary import RunSummary
from ..dependencies import services
from ..services import Services

router = APIRouter(tags=["runs"])


@router.get("/runs", response_model=list[RunSummary])
def runs(found: Annotated[Services, Depends(services)]) -> list[RunSummary]:
    return found.runs.runs()
