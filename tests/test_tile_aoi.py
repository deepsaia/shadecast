"""A tile is built on the UTM square that covers its Mollweide cell, and scored inside the cell."""

import numpy as np
import pytest
from shapely.geometry import Point

from shadecast.corpus.tile import Tile
from shadecast.corpus.tile_aoi import aoi_for_tile, cell_mask, footprint_utm

TILE = Tile(6908, 2816)  # Ahmedabad's densest district


def test_the_footprint_is_the_cell_projected_to_utm_and_keeps_its_area():
    aoi = aoi_for_tile(TILE)
    footprint = footprint_utm(TILE, aoi.crs)
    assert footprint.area == pytest.approx(1_000_000, rel=0.01)


def test_the_aoi_is_a_whole_metre_square_that_covers_the_footprint():
    aoi = aoi_for_tile(TILE)
    footprint = footprint_utm(TILE, aoi.crs)
    minx, miny, maxx, maxy = aoi.bounds_utm
    fx0, fy0, fx1, fy1 = footprint.bounds
    assert aoi.side_m == int(aoi.side_m)
    assert 1000 <= aoi.side_m <= 1400
    assert minx <= fx0 and miny <= fy0 and maxx >= fx1 and maxy >= fy1
    assert aoi.name == TILE.id


def test_the_aoi_centre_is_the_cell_centre():
    aoi = aoi_for_tile(TILE)
    lat, lon = TILE.centre_wgs84
    assert (aoi.lat, aoi.lon) == pytest.approx((lat, lon), abs=1e-4)


def test_the_cell_mask_marks_the_pixels_inside_the_cell():
    aoi = aoi_for_tile(TILE)
    mask = cell_mask(TILE, aoi)
    assert mask.shape == aoi.shape
    assert mask.dtype == np.uint8
    inside = int(mask.sum()) * aoi.res_m * aoi.res_m
    assert inside == pytest.approx(1_000_000, rel=0.01)
    footprint = footprint_utm(TILE, aoi.crs)
    minx, _, _, maxy = aoi.bounds_utm
    centre = footprint.centroid
    row = int((maxy - centre.y) / aoi.res_m)
    col = int((centre.x - minx) / aoi.res_m)
    assert mask[row, col] == 1
    assert footprint.contains(Point(centre.x, centre.y))
    assert mask[0, 0] == 0
