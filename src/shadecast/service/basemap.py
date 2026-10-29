"""The street map under the simulator's tile grid: where the browser fetches it and whom to credit."""

from __future__ import annotations

from pydantic import BaseModel


class Basemap(BaseModel):
    source: str  # the key in the cited sources registry
    style_url: str
    attribution: str
