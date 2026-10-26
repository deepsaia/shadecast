"""What a tile is, from its provenance: the city, the design day, the inputs and their sources."""

from __future__ import annotations

from pydantic import BaseModel

from .urban_centre_facts import UrbanCentreFacts


class TileFacts(BaseModel):
    key: str
    name: str
    design_day: str | None
    tier: str
    buildings: int | None
    built_fraction: float | None
    canopy: float | None
    population_2020: float | None
    lat: float | None
    lon: float | None
    urban_centre: UrbanCentreFacts | None
    sources: dict[str, str]


def facts_from(provenance: dict, fallback_key: str) -> TileFacts:
    """The facts a provenance file carries; a bundle built before the database has no centre."""
    city = provenance.get("city", {})
    centre = provenance.get("urban_centre")
    return TileFacts(
        key=str(city.get("key", fallback_key)),
        name=str(city.get("name", fallback_key.title())),
        design_day=provenance.get("met", {}).get("design_day"),
        tier=str(provenance.get("quality", {}).get("tier", "?")),
        buildings=provenance.get("buildings", {}).get("count"),
        built_fraction=provenance.get("buildings", {}).get("built_fraction"),
        canopy=provenance.get("canopy", {}).get("cover_gt2m"),
        population_2020=provenance.get("population", {}).get("total"),
        lat=provenance.get("aoi", {}).get("lat"),
        lon=provenance.get("aoi", {}).get("lon"),
        urban_centre=UrbanCentreFacts.model_validate(centre) if isinstance(centre, dict) else None,
        sources={
            "buildings": str(provenance.get("buildings", {}).get("source", "")),
            "terrain": str(provenance.get("dem", {}).get("source", "")),
            "canopy": str(provenance.get("canopy", {}).get("source", "")),
            "landcover": str(provenance.get("landcover", {}).get("source", "")),
            "meteorology": str(provenance.get("met", {}).get("source", "")),
        },
    )
