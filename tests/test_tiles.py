"""Tiles are UTM kilometre squares; an urban centre is the squares inside it. No network."""

import numpy as np
import pytest
from shapely.geometry import box
from shapely.ops import transform as transform_geometry

from shadecast.corpus.tile import Tile
from shadecast.corpus.tile_rasters import TileRasters
from shadecast.corpus.tiling import attributes
from shadecast.corpus.tiling import select_densest
from shadecast.corpus.tiling import select_ids
from shadecast.corpus.tiling import select_random
from shadecast.corpus.tiling import select_stratified
from shadecast.corpus.tiling import tiles_of
from shadecast.corpus.tiling import zone_of
from shadecast.corpus.utm_zone import UtmZone
from shadecast.data import ghs_grid
from shadecast.data.raster_window import RasterWindow

ZONE = UtmZone(43, False)  # Ahmedabad
TILE = Tile(ZONE, 249, 2546)
# A block of 3 by 2 kilometre squares, e 249..252 km and n 2546..2548 km, as an urban centre
# boundary would be delivered: in the GHS Mollweide grid.
BLOCK_UTM = box(249_000, 2_546_000, 252_000, 2_548_000)
BLOCK = transform_geometry(ZONE.transformer_to(ghs_grid.CRS).transform, BLOCK_UTM)


def _constant_window(value: float) -> RasterWindow:
    minx, miny, maxx, maxy = BLOCK.bounds
    bounds = (
        np.floor(minx / 100) * 100 - 500,
        np.floor(miny / 100) * 100 - 500,
        np.ceil(maxx / 100) * 100 + 500,
        np.ceil(maxy / 100) * 100 + 500,
    )
    window = RasterWindow.zeros(bounds)
    window.values[:] = value
    return window


def _rasters() -> TileRasters:
    return TileRasters(
        population_2020=_constant_window(10.0),  # ten people in every 100 m cell
        built_surface=_constant_window(2_500.0),  # a quarter of every cell is built
        building_height=_constant_window(8.0),
    )


def test_tile_id_names_zone_and_kilometre_corner():
    assert TILE.id == "t43N_249_2546"
    assert Tile(UtmZone(23, True), 686, 7462).id == "t23S_686_7462"


def test_tile_id_round_trips():
    assert Tile.from_id("t43N_249_2546") == TILE
    assert Tile.from_id("t23S_686_7462") == Tile(UtmZone(23, True), 686, 7462)


def test_tile_id_that_is_not_a_square_is_refused():
    with pytest.raises(ValueError, match="t6908"):
        Tile.from_id("t6908_2816")


def test_tile_bounds_are_the_kilometre_square_in_metres():
    assert TILE.bounds == (249_000, 2_546_000, 250_000, 2_547_000)
    assert TILE.polygon.area == 1_000_000


def test_tile_containing_a_point_in_the_zone():
    assert Tile.containing(ZONE, 249_750.0, 2_546_150.0) == TILE


def test_tile_at_a_wgs84_point_is_the_square_holding_it():
    assert Tile.at_wgs84(23.013954, 72.558362) == Tile(ZONE, 249, 2547)


def test_tile_centre_round_trips_through_degrees():
    lat, lon = TILE.centre_wgs84
    assert ZONE.from_wgs84(lon, lat) == pytest.approx(TILE.centre_utm, abs=0.01)


def test_tile_footprint_in_mollweide_keeps_its_area():
    assert TILE.polygon_in(ghs_grid.CRS).area == pytest.approx(1_000_000, rel=0.01)


def test_zone_of_a_boundary_is_the_zone_of_its_centroid():
    assert zone_of(BLOCK) == ZONE


def test_tiles_of_a_boundary_are_the_squares_whose_centres_lie_inside():
    tiles = tiles_of(BLOCK)
    assert len(tiles) == 6
    assert {(t.e_km, t.n_km) for t in tiles} == {(e, n) for e in (249, 250, 251) for n in (2546, 2547)}
    assert all(t.zone == ZONE for t in tiles)


def test_tiles_are_listed_north_to_south_then_west_to_east():
    assert [(t.e_km, t.n_km) for t in tiles_of(BLOCK)][:3] == [
        (249, 2547),
        (250, 2547),
        (251, 2547),
    ]


def test_attributes_sum_the_cells_inside_the_footprint():
    first = attributes([TILE], _rasters())[0]
    assert first["id"] == "t43N_249_2546"
    assert first["population_2020"] == pytest.approx(1000.0, rel=0.1)
    assert first["density_2020_per_km2"] == first["population_2020"]
    assert first["built_fraction"] == pytest.approx(0.25, rel=0.1)
    assert first["mean_height_m"] == pytest.approx(8.0)


def test_attributes_carry_both_bounds_and_the_centre():
    first = attributes([TILE], _rasters())[0]
    assert first["bounds_utm"] == [249_000, 2_546_000, 250_000, 2_547_000]
    assert first["zone"] == "43N"
    assert len(first["bounds_wgs84"]) == 4
    assert len(first["centre"]) == 2


ROWS = [
    {"id": "a", "population_2020": 9000.0, "density_2020_per_km2": 9000.0, "built_fraction": 0.9},
    {"id": "b", "population_2020": 7000.0, "density_2020_per_km2": 7000.0, "built_fraction": 0.8},
    {"id": "c", "population_2020": 5000.0, "density_2020_per_km2": 5000.0, "built_fraction": 0.5},
    {"id": "d", "population_2020": 3000.0, "density_2020_per_km2": 3000.0, "built_fraction": 0.4},
    {"id": "e", "population_2020": 1000.0, "density_2020_per_km2": 1000.0, "built_fraction": 0.1},
    {"id": "f", "population_2020": 500.0, "density_2020_per_km2": 500.0, "built_fraction": 0.05},
]


def test_select_densest_takes_the_top_k_by_density():
    assert [r["id"] for r in select_densest(ROWS, 2)] == ["a", "b"]


def test_select_stratified_takes_the_densest_tile_of_each_built_fraction_tercile():
    assert [r["id"] for r in select_stratified(ROWS, 3)] == ["a", "c", "e"]


def test_select_stratified_returns_to_the_highest_tercile_for_a_fourth():
    assert [r["id"] for r in select_stratified(ROWS, 4)] == ["a", "c", "e", "b"]


def test_select_ids_keeps_the_asked_order():
    assert [r["id"] for r in select_ids(ROWS, ["c", "a"])] == ["c", "a"]


def test_select_ids_refuses_an_unknown_id_by_name():
    with pytest.raises(KeyError, match="zz"):
        select_ids(ROWS, ["a", "zz"])


def test_select_random_is_reproducible_for_a_seed():
    first = [r["id"] for r in select_random(ROWS, 3, 1)]
    assert first == [r["id"] for r in select_random(ROWS, 3, 1)]
    assert len(first) == 3


def test_select_random_draws_only_populated_tiles():
    assert all(r["population_2020"] > 0 for r in select_random(ROWS, 6, 2))
