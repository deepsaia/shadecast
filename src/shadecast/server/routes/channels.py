"""The surrogate channels, and the models trained for a city on one of them."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query

from ...service.channel_summary import ChannelSummary
from ...service.channels import CHANNELS
from ...service.channels import channel as channel_of
from ...service.model_summary import ModelSummary
from ..dependencies import services
from ..services import Services

router = APIRouter(tags=["channels"])

City = Annotated[str, Query(description="A city key, an id, a slug or a name.")]


@router.get("/channels", response_model=list[ChannelSummary])
def channels() -> list[ChannelSummary]:
    return CHANNELS


@router.get("/channels/{channel}/models", response_model=list[ModelSummary])
def models(
    channel: str, found: Annotated[Services, Depends(services)], city: City | None = None
) -> list[ModelSummary]:
    """The channel's models for one city, or every model under the root when none is named."""
    channel_of(channel)
    if city is not None:
        return found.models.models(found.catalog.urban_centre_id(city))
    return found.models.all_models()


@router.get("/channels/{channel}/models/{model}", response_model=ModelSummary)
def model(channel: str, model: str, city: City, found: Annotated[Services, Depends(services)]) -> ModelSummary:
    channel_of(channel)
    return found.models.named(found.catalog.urban_centre_id(city), model)
