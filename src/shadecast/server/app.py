"""The FastAPI application: routes over the question services, the pages, and the built client.

Translation only. A route parses the path, calls one service method and returns its model; the
error handlers turn service failures into responses that name what was missing.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from . import errors, pages, spa
from .request_id import RequestIdMiddleware
from .routes import cities, health, tiles
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
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(RequestIdMiddleware)
    errors.install(app)
    for router in (health.router, cities.router, tiles.router):
        app.include_router(router, prefix=API)
    pages.mount(app)
    spa.mount(app, settings.static_dir)
    return app
