"""Whether the server is alive and whether it is ready to answer about data."""

from __future__ import annotations

from pydantic import BaseModel


class Health(BaseModel):
    version: str
    ready: bool
    cities: int
