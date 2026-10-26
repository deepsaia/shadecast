"""One physical channel a surrogate is trained for."""

from __future__ import annotations

from pydantic import BaseModel


class ChannelSummary(BaseModel):
    key: str  # how commands and routes name it
    label: str  # how the dashboard and the pages name it
    kind: str  # the engine's intervention kind
