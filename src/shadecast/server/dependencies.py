"""How a route reaches the services and the settings the app was built with."""

from __future__ import annotations

from fastapi import Request

from .services import Services
from .settings import ServerSettings


def services(request: Request) -> Services:
    return request.app.state.services


def settings(request: Request) -> ServerSettings:
    return request.app.state.settings
