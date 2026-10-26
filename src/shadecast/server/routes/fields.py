"""A tile's raster fields as arrays: the hours, the heights, each plan's cooling and placement."""

from __future__ import annotations

from typing import Annotated, Literal

import numpy as np
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from ...service.field_store import FieldStore
from ...service.resample import downsample, downsample_stack
from ...service.tile_reporter import report_of
from ..dependencies import services
from ..npy_response import npy_response
from ..services import Services

router = APIRouter(tags=["fields"])

Field = Literal["hours", "context", "cooling", "placement"]


@router.get("/cities/{city}/tiles/{tile}/fields/{field}", response_class=Response)
def field(
    city: str,
    tile: str,
    field: Field,
    *,
    found: Annotated[Services, Depends(services)],
    design: Annotated[
        str | None, Query(description="One design; else every plan, stacked.")
    ] = None,
    size: Annotated[int | None, Query(ge=8, le=4096, description="Long side in pixels.")] = None,
) -> Response:
    """The field in NPY format, hours or plans first when stacked, shrunk to ``size`` when asked."""
    paths = found.catalog.tile_paths(city, tile)
    store = FieldStore(paths)
    array = _array(store, field, design)
    if size is not None:
        # Area averaging promotes to float64 and turns a mask into a planted fraction; float32 is
        # all the client draws from, and half the bytes.
        shrunk = downsample_stack(array, size) if array.ndim == 3 else downsample(array, size)
        array = np.asarray(shrunk, dtype=np.float32)
    return npy_response(array)


def _array(store: FieldStore, field: str, design: str | None) -> np.ndarray:
    if field == "hours":
        return store.hourly_temperature()
    if field == "context":
        return store.heights()
    designs = [design] if design else [plan.id for plan in report_of(store.paths).plans]
    index = 0 if field == "placement" else 1
    layers = [store.response(design_id)[index] for design_id in designs]
    if design:
        return layers[0]
    return np.stack(layers) if layers else np.zeros((0, 0, 0), dtype="float32")
