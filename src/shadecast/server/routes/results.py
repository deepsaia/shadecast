"""The measured results, the findings and the cited sources."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from ... import sources
from ...service.findings import Findings
from ...service.results import Results
from ..dependencies import services
from ..services import Services

router = APIRouter(tags=["results"])


@router.get("/results", response_model=Results)
def results(found: Annotated[Services, Depends(services)]) -> Results:
    return found.results.collect()


@router.get("/findings", response_model=Findings)
def findings(found: Annotated[Services, Depends(services)]) -> Findings:
    return found.findings.collect()


@router.get("/references", response_model=list[dict])
def references() -> list[dict]:
    return sources.grouped()
