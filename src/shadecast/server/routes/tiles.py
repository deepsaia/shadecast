"""A city's tiles, one tile's location, and a tile's report."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends

from ...service.tile_location import TileLocation
from ...service.tile_report import TileReport
from ...service.tile_summary import TileSummary
from ..dependencies import services
from ..services import Services

router = APIRouter(tags=["tiles"])


@router.get("/cities/{city}/tiles", response_model=list[TileSummary])
def tiles(city: str, found: Annotated[Services, Depends(services)]) -> list[TileSummary]:
    return found.catalog.tiles(city)


@router.get("/cities/{city}/report", response_model=TileReport)
def city_report(city: str, found: Annotated[Services, Depends(services)]) -> TileReport:
    """The report of the city's tile that has come furthest."""
    return found.reporter.report_furthest(city)


@router.get("/cities/{city}/tiles/{tile}", response_model=TileLocation)
def tile(city: str, tile: str, found: Annotated[Services, Depends(services)]) -> TileLocation:
    return found.catalog.tile(city, tile)


@router.get("/cities/{city}/tiles/{tile}/report", response_model=TileReport)
def tile_report(city: str, tile: str, found: Annotated[Services, Depends(services)]) -> TileReport:
    return found.reporter.report(city, tile)
