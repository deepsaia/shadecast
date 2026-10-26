"""Service failures become responses naming what was missing; anything unexpected is a plain 500."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..service.missing_stage import MissingStage
from ..service.unknown_city import UnknownCity
from ..service.unknown_model import UnknownModel
from ..service.unknown_tile import UnknownTile
from .request_id import HEADER, current_request_id

logger = logging.getLogger(__name__)


def install(app: FastAPI) -> None:
    for unknown in (UnknownCity, UnknownTile, UnknownModel):
        app.add_exception_handler(unknown, _not_found)
    app.add_exception_handler(MissingStage, _missing_stage)
    app.add_exception_handler(Exception, _unexpected)


async def _not_found(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": str(exc), "kind": type(exc).__name__})


async def _missing_stage(_request: Request, exc: Exception) -> JSONResponse:
    stage = exc if isinstance(exc, MissingStage) else None
    content = {"error": str(exc), "kind": "MissingStage"}
    if stage is not None:
        content.update({"stage": stage.stage, "tile": stage.tile, "command": stage.command})
    return JSONResponse(status_code=404, content=content)


async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
    # This handler runs outside the request id middleware, so the id comes from the scope's
    # state. The detail goes to the log with it; the client learns only that the request failed.
    request_id = str(getattr(request.state, "request_id", current_request_id()))
    logger.exception("request %s failed: %s", request_id, exc)
    return JSONResponse(
        status_code=500,
        content={"error": "internal error", "request_id": request_id},
        headers={HEADER: request_id},
    )
