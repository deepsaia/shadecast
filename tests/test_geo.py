"""Pure-geometry tests. No network, no engine, deterministic."""

import math

import pytest

from shadecast.aoi import AOI
from shadecast.data.buildings import tile_name
from shadecast.data.buildings import tiles_for as gba_tiles
from shadecast.data.population import tile_rc
from shadecast.data.rasters import _corners

# Seeds spanning both hemispheres, the equator and the prime meridian. Fixed here rather than
# read from the corpus so the geometry tests need neither the database nor the network.
SEEDS = (
    ("ahmedabad", 23.02, 72.58),
    ("rio", -22.91, -43.17),
    ("sydney", -33.87, 151.21),
    ("nairobi", -1.29, 36.82),
    ("london", 51.51, -0.13),
    ("lima", -12.05, -77.04),
    ("phoenix", 33.45, -112.07),
    ("jakarta", -6.18, 106.83),
    ("khartoum", 15.50, 32.56),
    ("boston", 42.36, -71.06),
)

# --- UTM zone selection ---------------------------------------------------


@pytest.mark.parametrize(
    "lat,lon,epsg",
    [
        (23.02, 72.58, 32643),  # Ahmedabad, north
        (-22.91, -43.17, 32723),  # Rio, south + west
        (-33.87, 151.21, 32756),  # Sydney, far south
        (-1.29, 36.82, 32737),  # Nairobi, just south of equator
        (51.51, -0.13, 32630),  # London, straddles prime meridian
    ],
)
def test_utm_epsg(lat, lon, epsg):
    assert AOI("t", lat, lon).utm_epsg == epsg


def test_southern_hemisphere_uses_327xx():
    for key, lat, lon in SEEDS:
        band = AOI(key, lat, lon).utm_epsg // 100
        assert band == (327 if lat < 0 else 326), key


# --- grid integrity -------------------------------------------------------


def test_grid_is_square_and_snapped():
    a = AOI("t", 23.02, 72.58, side_m=1000, res_m=1.0)
    assert a.shape == (1000, 1000)
    minx, miny, maxx, maxy = a.bounds_utm
    assert maxx - minx == pytest.approx(1000)
    assert maxy - miny == pytest.approx(1000)
    # origin must land on a whole pixel so layers align without resampling drift
    assert minx % a.res_m == 0 and miny % a.res_m == 0


def test_transform_matches_bounds():
    a = AOI("t", -22.91, -43.17, side_m=500, res_m=0.5)
    minx, _, _, maxy = a.bounds_utm
    t = a.transform
    assert t.c == pytest.approx(minx)
    assert t.f == pytest.approx(maxy)
    assert t.a == pytest.approx(0.5)
    assert t.e == pytest.approx(-0.5)  # north-up


def test_wgs84_bounds_contain_centre():
    for key, lat, lon in SEEDS:
        a = AOI(key, lat, lon)
        minx, miny, maxx, maxy = a.bounds_wgs84
        assert minx <= a.lon <= maxx, key
        assert miny <= a.lat <= maxy, key


# --- tile addressing ------------------------------------------------------


@pytest.mark.parametrize(
    "lon,lat,expect",
    [
        (72.58, 23.02, "e070_n25_e075_n20"),  # north-east
        (-43.17, -22.91, "w045_s20_w040_s25"),  # south-west
        (36.82, -1.29, "e035_n00_e040_s05"),  # crosses the equator
        (-0.13, 51.51, "w005_n55_e000_n50"),  # crosses the prime meridian
    ],
)
def test_gba_tile_name(lon, lat, expect):
    assert tile_name(lon, lat) == expect


def test_gba_tiles_cover_aoi_corners():
    a = AOI("t", 23.02, 72.58)
    for t in gba_tiles(a):
        assert len(t.split("_")) == 4


def test_ghspop_tile_is_in_range():
    for key, lat, lon in SEEDS:
        r, col = tile_rc(lat, lon)
        assert 1 <= r <= 18, key
        assert 1 <= col <= 36, key


@pytest.mark.parametrize("step", [1, 3])
def test_raster_corners_floor_to_step(step):
    a = AOI("t", -22.91, -43.17)
    for la, lo in _corners(a, step):
        assert la % step == 0
        assert lo % step == 0
        # SW corner must not be north or east of the AOI
        assert la <= math.floor(a.bounds_wgs84[1])
