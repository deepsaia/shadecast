"""Which tile's baseline physics to run: a city, and one of its tiles or the densest built one."""

from __future__ import annotations

from pydantic import BaseModel


class BaselineRequest(BaseModel):
    target: str
    tile: str | None = None
