"""The basemap the client draws under its map, read from the cited sources so the URL is typed once."""

from __future__ import annotations

from fastapi import APIRouter

from ... import sources
from ...service.basemap import Basemap

router = APIRouter(tags=["basemap"])

SOURCE = "openfreemap"


@router.get("/basemap", response_model=Basemap)
def basemap() -> Basemap:
    """Where the browser fetches the street map at view time, and the credit it owes."""
    cited = sources.source(SOURCE)
    return Basemap(
        source=SOURCE,
        style_url=str(cited.get("endpoint")),
        attribution=str(cited.get("authors_or_publisher")),
    )
