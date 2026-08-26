"""Building footprints and heights from GlobalBuildingAtlas (GBA) LoD1.

Chosen over Overture and UT-GLOBUS deliberately. Measured on the Ahmedabad AOI:
Overture 2026-08-19.0 carried a height for 1 of 14,213 buildings (0.0%), while
GBA carried heights for 27,352 of 27,352 (100%). UT-GLOBUS, which the WRI Cool
Cities Lab pipeline uses, reports RMSE 9.1 m against LiDAR in its own paper.
GBA is 3 m native resolution with >97% global height completeness (ESSD 2025).

Hosted as anonymous GeoParquet on Source Cooperative, tiled 5 degrees, so a
single city needs one file rather than a global scan.
"""

from __future__ import annotations

import logging
import math
from operator import itemgetter

import duckdb
import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio.enums import MergeAlg
from rasterio.features import rasterize
from shapely import from_wkb

from ..aoi import AOI

logger = logging.getLogger(__name__)

BASE = "https://data.source.coop/tge-labs/globalbuildingatlas-lod1"


def _east_west(degrees: int) -> str:
    """Format a longitude edge the way GBA names its tiles."""
    hemisphere = "e" if degrees >= 0 else "w"
    return f"{hemisphere}{abs(degrees):03d}"


def _north_south(degrees: int) -> str:
    """Format a latitude edge the way GBA names its tiles."""
    hemisphere = "n" if degrees >= 0 else "s"
    return f"{hemisphere}{abs(degrees):02d}"


def tile_name(lon: float, lat: float) -> str:
    """GBA tiles are 5x5 degrees, named by their west/north/east/south edges."""
    lon0 = int(math.floor(lon / 5) * 5)
    lat0 = int(math.floor(lat / 5) * 5)
    return (
        f"{_east_west(lon0)}_{_north_south(lat0 + 5)}_{_east_west(lon0 + 5)}_{_north_south(lat0)}"
    )


def tiles_for(aoi: AOI) -> list[str]:
    """Every GBA tile intersecting the AOI. A city near a 5-degree boundary
    straddles two or four tiles, which is common enough to handle properly."""
    minx, miny, maxx, maxy = aoi.bounds_wgs84
    lons = sorted({int(math.floor(v / 5) * 5) for v in (minx, maxx)})
    lats = sorted({int(math.floor(v / 5) * 5) for v in (miny, maxy)})
    return [tile_name(lo + 0.1, la + 0.1) for lo in lons for la in lats]


def fetch(aoi: AOI) -> gpd.GeoDataFrame:
    """Return building polygons with heights, reprojected to the AOI's UTM CRS."""
    minx, miny, maxx, maxy = aoi.bounds_wgs84
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")

    frames = []
    for tile in tiles_for(aoi):
        try:
            frames.append(
                con.execute(
                    f"""
                SELECT height, var, source, geometry
                FROM read_parquet('{BASE}/{tile}.parquet')
                WHERE bbox.xmin BETWEEN {minx} AND {maxx}
                  AND bbox.ymin BETWEEN {miny} AND {maxy}
                """
                ).fetchdf()
            )
        except duckdb.IOException as exc:
            # Ocean-only tiles are simply absent from the bucket, which is a
            # normal condition for coastal cities, not a failure.
            logger.debug("GBA tile %s unavailable: %s", tile, exc)
            continue

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if df.empty:
        raise RuntimeError(f"No GBA buildings in {aoi.name} AOI")

    gdf = gpd.GeoDataFrame(
        df.drop(columns=["geometry"]),
        geometry=from_wkb([bytes(g) for g in df["geometry"].values]),
        crs="EPSG:4326",
    )
    return gdf.to_crs(aoi.crs)


def rasterize_heights(aoi: AOI, gdf: gpd.GeoDataFrame) -> np.ndarray:
    """Burn building heights (metres above ground) onto the AOI grid.

    Taller buildings win on overlap, so a courtyard block does not erase a tower.
    """
    shapes = sorted(
        (
            (geom, float(height))
            for geom, height in zip(gdf.geometry, gdf["height"], strict=True)
            if height and height > 0
        ),
        key=itemgetter(1),
    )
    if not shapes:
        raise RuntimeError("No positive building heights to rasterize")

    return rasterize(
        shapes,
        out_shape=aoi.shape,
        transform=aoi.transform,
        fill=0.0,
        merge_alg=MergeAlg.replace,
        dtype="float32",
    )
