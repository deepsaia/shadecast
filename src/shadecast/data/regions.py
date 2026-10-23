"""Continent, UN subregion and ISO3 code of a point, from Natural Earth countries.

The urban centre database names a country but no continent, and country names do not match
across datasets (México, United States of America). A spatial join of each centre's centroid
against the Natural Earth 1:50m admin-0 polygons sidesteps names entirely and yields the
continent, the UN subregion and the ISO3 code in one pass. Natural Earth is public domain and
served anonymously; the archive is checked against a recorded digest before it is read.
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from numpy.typing import ArrayLike

from . import checksum, ghs_grid
from .ghs_product import CACHE_ROOT, DOWNLOAD_TIMEOUT_S

logger = logging.getLogger(__name__)

SOURCE = "natural_earth_admin0"  # key in cited_sources.json
URL = "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip"
ARCHIVE_NAME = "ne_50m_admin_0_countries.zip"
CHECKSUM = "5fed433373581fa648920435f937d95f2d3c0200e067409c6478dcdf1b853139"
FIELDS = {"CONTINENT": "continent", "SUBREGION": "subregion", "ADM0_A3": "iso3"}
REGION_COLUMNS = ("continent", "subregion", "iso3")
WGS84 = "EPSG:4326"


def fetch(cache_root: Path = CACHE_ROOT) -> Path:
    """The cached archive, downloaded and verified on first use."""
    target = Path(cache_root) / "naturalearth" / ARCHIVE_NAME
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    logger.info("fetching %s", URL)
    response = requests.get(URL, timeout=DOWNLOAD_TIMEOUT_S)
    response.raise_for_status()
    target.write_bytes(response.content)
    checksum.verify(target, CHECKSUM)
    return target


def countries(cache_root: Path = CACHE_ROOT) -> gpd.GeoDataFrame:
    """Country polygons with continent, subregion and ISO3, in degrees."""
    frame = gpd.read_file(fetch(cache_root)).rename(columns=FIELDS)
    return frame.loc[:, [*REGION_COLUMNS, "geometry"]].to_crs(WGS84)


def _nearest(points: gpd.GeoDataFrame, polygons: gpd.GeoDataFrame) -> pd.DataFrame:
    """Nearest country for points no polygon contains, measured in metres."""
    joined = gpd.sjoin_nearest(
        points.to_crs(ghs_grid.CRS), polygons.to_crs(ghs_grid.CRS), how="left"
    )
    return joined.loc[~joined.index.duplicated(keep="first"), list(REGION_COLUMNS)]


def regions_of(lons: ArrayLike, lats: ArrayLike, polygons: gpd.GeoDataFrame) -> pd.DataFrame:
    """Continent, subregion and ISO3 for each point; a point outside every polygon takes the
    nearest one, which is what a coastal centroid on a coarse coastline needs.

    Three arguments because the points come as two coordinate columns and the polygons are
    passed in so tests can substitute a fixture.
    """
    points = gpd.GeoDataFrame(geometry=gpd.points_from_xy(lons, lats), crs=WGS84)
    within = gpd.sjoin(points, polygons, how="left", predicate="within")
    within = within.loc[~within.index.duplicated(keep="first")]
    missing = within["iso3"].isna()
    if bool(missing.any()):
        nearest = _nearest(points.loc[missing], polygons)
        within.loc[missing, list(REGION_COLUMNS)] = nearest.to_numpy()
    return pd.DataFrame(within.loc[:, list(REGION_COLUMNS)]).reset_index(drop=True)


def with_regions(table: pd.DataFrame, cache_root: Path = CACHE_ROOT) -> pd.DataFrame:
    """A copy of a corpus table with continent, subregion and iso3 columns from its lon and lat."""
    found = regions_of(table["lon"].to_numpy(), table["lat"].to_numpy(), countries(cache_root))
    return pd.concat([table.reset_index(drop=True), found], axis=1)
