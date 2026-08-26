"""Assemble a SOLWEIG-ready city bundle from credential-free open sources.

This is the build-time half of the architecture. It needs network access but no
account, key or quota anywhere: GlobalBuildingAtlas on Source Cooperative,
Copernicus DEM and ESA WorldCover via Planetary Computer's anonymous STAC,
Meta/WRI canopy on AWS Open Data, GHS-POP from the JRC, and Open-Meteo for ERA5.

Output is a frozen directory users consume offline. Nothing downstream of a
built bundle needs the network.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

from .aoi import AOI
from .aoi_selector import select
from .cities import City
from .data import buildings as B
from .data import canopy as C
from .data import landcover as LC
from .data import met as M
from .data import population as P
from .data import rasters as R
from .quality import assess

SCHEMA = 1


def _write(path: Path, arr: np.ndarray, aoi: AOI, dtype: str = "float32") -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=arr.shape[0],
        width=arr.shape[1],
        count=1,
        dtype=dtype,
        crs=aoi.crs,
        transform=aoi.transform,
        compress="deflate",
        tiled=True,
    ) as dst:
        dst.write(arr.astype(dtype), 1)


def build_city(
    city: City,
    out_dir: Path,
    *,
    side_m: int = 1000,
    res_m: float = 1.0,
    start: str = "2021-01-01",
    end: str = "2025-12-31",
    aoi: AOI | None = None,
) -> dict:
    """Produce Building_DSM.tif, DEM.tif, Trees.tif, landcover.tif, population.tif,
    met.txt and provenance.json for one city."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Study area is chosen from population density, not by hand. A city-centre
    # coordinate usually lands in a commercial district that is empty at night.
    if aoi is None:
        aoi = select(city, side_m=side_m, res_m=res_m)

    prov: dict = {
        "schema": SCHEMA,
        "city": {
            "key": city.key,
            "name": city.name,
            "country": city.country,
            "koppen": city.koppen,
            "income": city.income,
            "region": city.region,
            "in_wri_cool_cities_lab": city.in_wri,
        },
        "aoi": {
            "seed_lat": city.lat,
            "seed_lon": city.lon,
            "lat": aoi.lat,
            "lon": aoi.lon,
            "side_m": aoi.side_m,
            "res_m": aoi.res_m,
            "epsg": aoi.utm_epsg,
            "shape": list(aoi.shape),
            "selection": "densest populated window within 16 km of seed (GHS-POP)",
        },
    }

    # Ground elevation, metres above sea level.
    dem = R.terrain(aoi)
    _write(out_dir / "DEM.tif", dem, aoi)
    prov["dem"] = {
        "source": "Copernicus DEM GLO-30 (AWS Open Data, unsigned)",
        "min_m": round(float(dem.min()), 2),
        "max_m": round(float(dem.max()), 2),
    }

    # Buildings. SOLWEIG's "Building DSM" is ground PLUS building, in masl.
    gdf = B.fetch(aoi)
    bh = B.rasterize_heights(aoi, gdf)
    _write(out_dir / "Building_DSM.tif", dem + bh, aoi)
    prov["buildings"] = {
        "source": "GlobalBuildingAtlas LoD1 (Source Cooperative)",
        "tiles": B.tiles_for(aoi),
        "count": len(gdf),
        "height_completeness": round(float(gdf["height"].notna().mean()), 4),
        "built_fraction": round(float((bh > 0).mean()), 4),
        "max_height_m": round(float(bh.max()), 2),
        "median_height_m": round(float(gdf["height"].median()), 2),
        "origin_mix": {k: int(v) for k, v in gdf["source"].value_counts().items()},
    }

    # Vegetation canopy, height ABOVE GROUND (not asl). 0 where none.
    chm = C.canopy_height(aoi)
    _write(out_dir / "Trees.tif", chm, aoi)
    prov["canopy"] = {
        "source": "Meta/WRI 1m CHM (AWS Open Data)",
        "tiles": C.tiles_for(aoi),
        "cover_gt2m": round(float((chm > 2).mean()), 4),
        "max_m": round(float(chm.max()), 2),
    }

    # Land cover, for surface thermal properties, plus the UMEP-coded version
    # SOLWEIG actually consumes.
    wc = R.worldcover(aoi)
    _write(out_dir / "landcover.tif", wc, aoi, dtype="uint8")
    umep = LC.to_umep(wc, bh)
    # float32, not an integer type. The engine substitutes float albedos into a copy
    # of this grid, so an integer raster truncates every albedo to zero with no error.
    _write(out_dir / "landcover_umep.tif", umep, aoi, dtype="float32")
    prov["landcover"] = {
        "source": "ESA WorldCover 10m v200 2021 (AWS Open Data, unsigned)",
        "umep_mix": LC.summarise(umep),
    }

    # Population, dasymetrically redistributed into building volume.
    pop = P.dasymetric(aoi, bh)
    _write(out_dir / "population.tif", pop, aoi)
    prov["population"] = {
        "source": "GHS-POP R2023A 100m (JRC)",
        "tiles": [list(t) for t in P.tiles_for(aoi)],
        "total": round(float(pop.sum()), 1),
        "method": "dasymetric by building volume",
    }

    # Meteorological forcing for the hottest observed day in the window.
    _, date = M.build(aoi, out_dir / "met.txt", start, end)
    prov["met"] = {
        "source": "Open-Meteo ERA5 archive (no key)",
        "window": [start, end],
        "design_day": date,
    }

    prov["quality"] = assess(prov, bh, chm, wc, float(pop.sum()))

    (out_dir / "provenance.json").write_text(json.dumps(prov, indent=2))
    return prov
