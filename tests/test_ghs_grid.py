"""The GHS Mollweide grid: 1,000 km tiles of 100 m cells, origin at (-18,041,000, 9,000,000)."""

import pytest

from shadecast.data import ghs_grid
from shadecast.data.population import tile_rc as population_tile_rc


def test_tile_scheme_origin_is_a_whole_kilometre():
    assert ghs_grid.X0 == -18_041_000.0
    assert ghs_grid.Y0 == 9_000_000.0
    assert ghs_grid.TILE_M == 1_000_000.0
    assert ghs_grid.CELL_M == 100.0


@pytest.mark.parametrize(
    "x,y,row,col",
    [
        (2_959_005.0, -5.0, 10, 22),  # just inside the tile whose raster origin is (2959000, 0)
        (-4_040_995.0, -1_000_005.0, 11, 15),  # raster origin (-4041000, -1000000)
        (6_912_192.0, 2_816_722.0, 7, 25),  # Ahmedabad's centroid
    ],
)
def test_tile_row_and_column_match_the_raster_origins(x, y, row, col):
    assert ghs_grid.tile_rc(x, y) == (row, col)


def test_a_point_just_south_of_a_row_boundary_stays_in_the_row_below():
    # 19 km south of the boundary between rows 9 and 10. The old origin of 9,020,048 m put
    # this point in row 10, whose raster does not cover it.
    assert ghs_grid.tile_rc(0.0, 19_000.0) == (9, 19)


def test_tile_name_matches_the_published_file_names():
    assert ghs_grid.tile_name(6, 26) == "R6_C26"


def test_wgs84_round_trip():
    x, y = ghs_grid.to_mollweide(72.5988, 23.0192)
    assert x == pytest.approx(6_912_192, abs=50)
    assert y == pytest.approx(2_816_722, abs=50)
    lon, lat = ghs_grid.to_wgs84(x, y)
    assert (lon, lat) == pytest.approx((72.5988, 23.0192), abs=1e-4)


def test_population_reader_uses_the_shared_grid():
    assert population_tile_rc(23.0192, 72.5988) == ghs_grid.tile_rc(
        *ghs_grid.to_mollweide(72.5988, 23.0192)
    )
