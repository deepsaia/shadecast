"""Alive, and ready: the data root exists and the selection loads."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Annotated

from fastapi import APIRouter, Depends

from ..dependencies import services, settings
from ..health import Health
from ..services import Services
from ..settings import ServerSettings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health)
def health(
    found: Annotated[Services, Depends(services)],
    current: Annotated[ServerSettings, Depends(settings)],
) -> Health:
    return Health(
        version=_version(),
        ready=current.data_root.is_dir(),
        cities=len(found.catalog.keys()),
    )


def _version() -> str:
    try:
        return version("shadecast")
    except PackageNotFoundError:
        return "unknown"
