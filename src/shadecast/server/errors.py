"""Service failures become responses: 404 names what was missing, 400 what was asked wrongly, 500 the rest."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse

from ..service.error_message import error_message
from ..service.missing_stage import MissingStage
from ..service.unknown_arrangement import UnknownArrangement
from ..service.unknown_channel import UnknownChannel
from ..service.unknown_city import UnknownCity
from ..service.unknown_model import UnknownModel
from ..service.unknown_tile import UnknownTile
from .request_id import HEADER
from .request_id import current_request_id

logger = logging.getLogger(__name__)


def install(app: FastAPI) -> None:
    for unknown in (UnknownCity, UnknownTile, UnknownModel, UnknownChannel):
        app.add_exception_handler(unknown, _not_found)
    for wrong in (ValueError, UnknownArrangement):
        app.add_exception_handler(wrong, _bad_request)
    app.add_exception_handler(MissingStage, _missing_stage)
    app.add_exception_handler(Exception, _unexpected)


async def _not_found(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": str(exc), "kind": type(exc).__name__})


async def _bad_request(_request: Request, exc: Exception) -> JSONResponse:
    """A lever or an option the request got wrong; the message says which, as the command line would."""
    return JSONResponse(status_code=400, content={"error": error_message(exc), "kind": type(exc).__name__})


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
