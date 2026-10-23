"""Fetch and read the GHS Urban Centre Database, the corpus every city is drawn from.

GHS-UCDB R2024A (JRC, CC BY 4.0) describes 11,422 urban centres. Two of its theme files carry
every field the corpus needs: general characteristics (name, country, population, area, World
Bank income group) and climate (Koppen-Geiger class of the majority of the surface). They are
served anonymously from the same host as the GHS-POP tiles, so the one rule holds: network at
build time, no account anywhere.

Each archive is checked against a recorded SHA-256 before it is unpacked. A changed or truncated
download is refused by name rather than read into a corpus that would silently differ from the
one the benchmark was stratified on. The climate CSV is latin-1 encoded, which is recorded here
so that a reader never has to rediscover it.
"""

from __future__ import annotations

import hashlib
import logging
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

logger = logging.getLogger(__name__)

SOURCE = "ghs_ucdb"  # key in cited_sources.json
RELEASE = "R2024A"
VERSION = "V1_2"
BASE_URL = (
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
    f"GHS_UCDB_GLOBE_{RELEASE}/GHS_UCDB_THEME_GLOBE_{RELEASE}"
)
CACHE = Path.home() / ".cache" / "shadecast" / "ucdb"

GENERAL = "GENERAL_CHARACTERISTICS"
CLIMATE = "CLIMATE"
THEMES = (GENERAL, CLIMATE)

# SHA-256 of each archive as published on 2026-10-23. A mismatch is a refusal, not a warning.
CHECKSUMS: dict[str, str] = {
    GENERAL: "bc879d82320504f89df2041b7936221c8239cd808abe93980493aed062b4f3d6",
    CLIMATE: "966b96ef701a8b0053467179a1231ddc24830ac2693aadd7d1388f281795c0bb",
}
ENCODINGS: dict[str, str] = {GENERAL: "utf-8", CLIMATE: "latin-1"}

ID = "ID_UC_G0"
NAME = "GC_UCN_MAI_2025"  # main name
NAMES = "GC_UCN_LIS_2025"  # every name the centre is known by, separated by semicolons
COUNTRY = "GC_CNT_GAD_2025"
AREA = "GC_UCA_KM2_2025"  # km2, which is also the number of 1 km tiles
POPULATION = "GC_POP_TOT_2025"
INCOME_GROUP = "GC_DEV_WIG_2025"  # World Bank income group
KOPPEN_CODE = "CL_KOP_CUR_2025"  # Beck et al. code of the majority of the surface
GENERAL_COLUMNS = (ID, NAME, NAMES, COUNTRY, AREA, POPULATION, INCOME_GROUP)
CLIMATE_COLUMNS = (ID, KOPPEN_CODE)
COLUMNS: dict[str, tuple[str, ...]] = {GENERAL: GENERAL_COLUMNS, CLIMATE: CLIMATE_COLUMNS}
CENTROID_LAYER = "UC_centroids"
LON = "lon"
LAT = "lat"

DOWNLOAD_TIMEOUT_S = 600
CHUNK_BYTES = 1 << 20


def archive_name(theme: str) -> str:
    return f"GHS_UCDB_THEME_{theme}_GLOBE_{RELEASE}_{VERSION}.zip"


def archive_url(theme: str) -> str:
    version_dir = VERSION.replace("_", "-")
    return f"{BASE_URL}/GHS_UCDB_THEME_{theme}_GLOBE_{RELEASE}/{version_dir}/{archive_name(theme)}"


def csv_path(theme: str, cache_dir: Path) -> Path:
    return Path(cache_dir) / theme / f"GHS_UCDB_THEME_{theme}_GLOBE_{RELEASE}.csv"


def geopackage_path(theme: str, cache_dir: Path) -> Path:
    return Path(cache_dir) / theme / f"GHS_UCDB_THEME_{theme}_GLOBE_{RELEASE}.gpkg"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        chunk = handle.read(CHUNK_BYTES)
        while chunk:
            digest.update(chunk)
            chunk = handle.read(CHUNK_BYTES)
    return digest.hexdigest()


def verify(archive: Path, theme: str) -> None:
    """Refuse an archive whose checksum is not the recorded one, naming the file."""
    expected = CHECKSUMS.get(theme)
    if expected is None:
        raise ValueError(f"no checksum recorded for theme {theme!r}")
    actual = sha256(archive)
    if actual != expected:
        raise ValueError(
            f"{Path(archive).name} does not match the recorded checksum "
            f"(expected {expected[:12]}..., got {actual[:12]}...); delete it and fetch again"
        )


def download(theme: str, cache_dir: Path) -> Path:
    """Stream one theme archive into the cache and verify it."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    archive = cache_dir / archive_name(theme)
    url = archive_url(theme)
    logger.info("fetching %s", url)
    with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT_S) as response:
        response.raise_for_status()
        with archive.open("wb") as handle:
            for chunk in response.iter_content(CHUNK_BYTES):
                handle.write(chunk)
    verify(archive, theme)
    logger.info("fetched %s, %.1f MB", archive.name, archive.stat().st_size / 1e6)
    return archive


def theme_dir(theme: str, cache_dir: Path = CACHE) -> Path:
    """Return the directory holding a theme's files, fetching and unpacking on first use."""
    cache_dir = Path(cache_dir)
    target = cache_dir / theme
    if csv_path(theme, cache_dir).exists():
        return target
    archive = cache_dir / archive_name(theme)
    if not archive.exists():
        archive = download(theme, cache_dir)
    verify(archive, theme)
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(target)
    logger.info("unpacked %s into %s", archive.name, target)
    return target


def read_theme(theme: str, cache_dir: Path = CACHE) -> pd.DataFrame:
    """Read one theme's table, keeping only the fields the corpus needs."""
    theme_dir(theme, cache_dir)
    path = csv_path(theme, cache_dir)
    encoding = ENCODINGS.get(theme, "utf-8")
    frame = pd.read_csv(path, encoding=encoding, low_memory=False)
    wanted = COLUMNS.get(theme, ())
    missing = [column for column in wanted if column not in frame.columns]
    if missing:
        raise ValueError(f"{path.name} lacks expected columns {missing}")
    return frame.loc[:, list(wanted)]


def join(general: pd.DataFrame, climate: pd.DataFrame) -> pd.DataFrame:
    """Pair the two themes on the urban centre id, refusing any centre one of them lacks."""
    general_ids = set(general[ID])
    climate_ids = set(climate[ID])
    missing = sorted(general_ids - climate_ids)
    if missing:
        raise ValueError(f"climate theme lacks urban centres {missing[:10]}")
    climate_only = [column for column in climate.columns if column not in general.columns]
    return general.merge(climate.loc[:, [ID, *climate_only]], on=ID, how="inner")


def centroids(cache_dir: Path = CACHE) -> pd.DataFrame:
    """Centroid of every urban centre in degrees, from the general theme package.

    The database stores centroids in World Mollweide metres. They are reprojected here so the
    rest of the code can treat a centroid like any other seed coordinate.
    """
    theme_dir(GENERAL, cache_dir)
    path = geopackage_path(GENERAL, cache_dir)
    points = gpd.read_file(path, layer=CENTROID_LAYER).to_crs("EPSG:4326")
    return pd.DataFrame({ID: points[ID], LON: points.geometry.x, LAT: points.geometry.y})


def polygons(cache_dir: Path = CACHE) -> gpd.GeoDataFrame:
    """Urban centre boundaries in World Mollweide, each an exact union of 1 km GHS cells."""
    theme_dir(GENERAL, cache_dir)
    path = geopackage_path(GENERAL, cache_dir)
    layers = gpd.list_layers(path)
    boundary_layer = next(name for name in layers["name"] if name != CENTROID_LAYER)
    frame = gpd.read_file(path, layer=boundary_layer)
    return frame.loc[:, [ID, "geometry"]]


def table(cache_dir: Path = CACHE) -> pd.DataFrame:
    """The corpus table: general and climate fields plus centroids, one row per centre."""
    joined = join(read_theme(GENERAL, cache_dir), read_theme(CLIMATE, cache_dir))
    return joined.merge(centroids(cache_dir), on=ID, how="left")
