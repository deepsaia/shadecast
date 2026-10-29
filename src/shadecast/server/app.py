"""The FastAPI application: routes over the question services, the pages, and the built client.

Translation only. A route parses the path, calls one service method and returns its model; the
error handlers turn service failures into responses that name what was missing.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from . import errors
from . import pages
from . import spa
from .request_id import RequestIdMiddleware
from .routes import channels
from .routes import cities
from .routes import fields
from .routes import health
from .routes import results
from .routes import runs
from .routes import tiles
from .services import Services
from .settings import ServerSettings

API = "/api/v1"


def create_app() -> FastAPI:
    """The uvicorn factory: settings from the environment, services over the real data."""
    settings = ServerSettings.from_environment()
    return build_app(settings, Services.open(settings))


def build_app(settings: ServerSettings, services: Services) -> FastAPI:
    """The app over given settings and services, which is how tests substitute both."""
    app = FastAPI(
        title="shadecast",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.services = services
    app.add_middleware(RequestIdMiddleware)
    # A browser lured to a rebound name must not reach a server bound to this machine.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts(settings))
    errors.install(app)
    routers = (
        health.router,
        cities.router,
        tiles.router,
        fields.router,
        channels.router,
        results.router,
        runs.router,
    )
    for router in routers:
        app.include_router(router, prefix=API)
    pages.mount(app)
    spa.mount(app, settings.static_dir)
    return app


def trusted_hosts(settings: ServerSettings) -> list[str]:
    """The names a request may address the server by: the bound host and the local names."""
    return sorted({settings.host, "localhost", "127.0.0.1", "testserver"})
