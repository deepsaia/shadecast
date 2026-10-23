"""Tiles are 1 km GHS grid cells; an urban centre is an exact set of them. No network."""

import numpy as np
import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from shadecast.corpus.tile import Tile
from shadecast.corpus.tiling import (
    aggregate,
    attributes,
    select_densest,
    select_ids,
    select_random,
    select_stratified,
    tiles_of,
)

# Three cells in a row at y = 2807 km and two more on the row above, an L shape of five.
CELLS = [(6897, 2807), (6898, 2807), (6899, 2807), (6897, 2808), (6898, 2808)]
POLYGON = unary_union([box(x * 1000, y * 1000, x * 1000 + 1000, y * 1000 + 1000) for x, y in CELLS])


def test_tile_id_is_the_lower_left_corner_in_kilometres():
    tile = Tile(6897, 2807)
    assert tile.id == "t6897_2807"
    assert Tile.from_id("t6897_2807") == tile
    assert Tile(-7346, 3873).id == "t-7346_3873"
    assert Tile.from_id("t-7346_3873") == Tile(-7346, 3873)


def test_tile_id_that_is_not_a_cell_is_refused():
    with pytest.raises(ValueError, match="t6897"):
        Tile.from_id("t6897")


def test_tile_bounds_are_the_metre_cell():
    assert Tile(6897, 2807).bounds == (6_897_000, 2_807_000, 6_898_000, 2_808_000)
    assert Tile(6897, 2807).polygon.area == 1_000_000


def test_tile_containing_a_mollweide_point_and_a_wgs84_point():
    assert Tile.containing(6_912_192.3, 2_816_722.1) == Tile(6912, 2816)
    assert Tile.at_wgs84(23.0192, 72.5988) == Tile(6912, 2816)
    lat, lon = Tile(6912, 2816).centre_wgs84
    assert (lat, lon) == pytest.approx((23.0, 72.6), abs=0.1)


def test_tiles_of_an_urban_centre_polygon_are_exactly_its_cells():
    tiles = tiles_of(POLYGON)
    assert len(tiles) == 5
    assert {(t.x_km, t.y_km) for t in tiles} == set(CELLS)
    # North to south, west to east, so a listing reads like a map.
    assert [(t.x_km, t.y_km) for t in tiles][:2] == [(6897, 2808), (6898, 2808)]


def test_aggregate_sums_or_averages_the_hundred_cells_inside_each_tile():
    # A 100 m field covering x 6897..6900 km and y 2807..2809 km: 30 columns by 20 rows.
    origin = (6_897_000.0, 2_809_000.0)
    field = np.zeros((20, 30), dtype="float32")
    field[10:20, 0:10] = 2.0  # the tile at (6897, 2807): every cell holds 2
    field[0:10, 10:20] = 5.0  # the tile at (6898, 2808): every cell holds 5
    tiles = [Tile(6897, 2807), Tile(6898, 2808), Tile(6899, 2807)]
    assert aggregate(field, origin, tiles, how="sum").tolist() == [200.0, 500.0, 0.0]
    assert aggregate(field, origin, tiles, how="mean").tolist() == [2.0, 5.0, 0.0]


def test_attributes_report_population_density_built_fraction_and_height():
    origin = (6_897_000.0, 2_809_000.0)
    population = np.zeros((20, 30), dtype="float32")
    population[10:20, 0:10] = 12.5  # 1,250 people in the first tile
    built = np.zeros((20, 30), dtype="float32")
    built[10:20, 0:10] = 2_500.0  # a quarter of every 100 m cell is built: fraction 0.25
    height = np.zeros((20, 30), dtype="float32")
    height[10:20, 0:10] = 8.0
    rows = attributes([Tile(6897, 2807), Tile(6899, 2807)], population, built, height, origin)
    first = rows[0]
    assert first["id"] == "t6897_2807"
    assert first["population_2020"] == pytest.approx(1250.0)
    assert first["density_2020_per_km2"] == pytest.approx(1250.0)
    assert first["built_fraction"] == pytest.approx(0.25)
    assert first["mean_height_m"] == pytest.approx(8.0)
    assert first["bounds_mollweide"] == [6_897_000, 2_807_000, 6_898_000, 2_808_000]
    assert len(first["bounds_wgs84"]) == 4
    assert rows[1]["population_2020"] == 0.0 and rows[1]["mean_height_m"] == 0.0


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
    chosen = [r["id"] for r in select_stratified(ROWS, 3)]
    assert chosen == ["a", "c", "e"]
    # Four asks for a second from the highest tercile before any tercile gets a third.
    assert [r["id"] for r in select_stratified(ROWS, 4)] == ["a", "c", "e", "b"]


def test_select_ids_keeps_the_asked_order_and_refuses_unknowns():
    assert [r["id"] for r in select_ids(ROWS, ["c", "a"])] == ["c", "a"]
    with pytest.raises(KeyError, match="zz"):
        select_ids(ROWS, ["a", "zz"])


def test_select_random_is_reproducible_and_populated():
    first = [r["id"] for r in select_random(ROWS, 3, seed=1)]
    assert first == [r["id"] for r in select_random(ROWS, 3, seed=1)]
    assert len(first) == 3
    assert all(r["population_2020"] > 0 for r in select_random(ROWS, 6, seed=2))
