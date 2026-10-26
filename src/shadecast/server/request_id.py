"""Every response carries a request id, and every log line written while it runs carries it too."""

from __future__ import annotations

import logging
from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

HEADER = "X-Request-Id"
_current: ContextVar[str] = ContextVar("request_id", default="-")


def current_request_id() -> str:
    return _current.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Reads the client's id or mints one, keeps it for the request, and echoes it back."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(HEADER) or uuid4().hex[:12]
        # The scope's state outlives this middleware, so the outermost error handler can read it.
        request.state.request_id = request_id
        token = _current.set(request_id)
        try:
            response = await call_next(request)
        finally:
            _current.reset(token)
        response.headers[HEADER] = request_id
        return response


class RequestIdFilter(logging.Filter):
    """Stamps the current request id on every record, as ``request_id``."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id()
        return True
