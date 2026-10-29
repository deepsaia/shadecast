"""The selected cities, and one city's tile statistics."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends

from ...service.city_summary import CitySummary
from ...service.tile_statistics import TileStatistics
from ..dependencies import services
from ..services import Services

router = APIRouter(tags=["cities"])


@router.get("/cities", response_model=list[CitySummary])
def cities(found: Annotated[Services, Depends(services)]) -> list[CitySummary]:
    return found.catalog.cities()


@router.get("/cities/{city}", response_model=TileStatistics)
def city(city: str, found: Annotated[Services, Depends(services)]) -> TileStatistics:
    return found.catalog.statistics(city)
