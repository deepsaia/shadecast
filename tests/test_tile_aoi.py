"""A tile is built on exactly its own square kilometre."""

from shadecast.corpus.tile import Tile
from shadecast.corpus.tile_aoi import aoi_for_tile
from shadecast.corpus.utm_zone import UtmZone


def test_the_aoi_bounds_are_the_tile_bounds_to_the_metre():
    tile = Tile(UtmZone(43, False), 249, 2546)
    aoi = aoi_for_tile(tile)
    assert aoi.bounds_utm == (249_000.0, 2_546_000.0, 250_000.0, 2_547_000.0)
    assert aoi.shape == (1000, 1000)
    assert aoi.name == tile.id


def test_the_aoi_uses_the_tile_zone_even_near_a_zone_boundary():
    # Easting 165 km in zone 43 is west of the zone's own longitude span, where a centre-based
    # zone choice would pick zone 42; the tile's zone must win so one city keeps one grid.
    tile = Tile(UtmZone(43, False), 165, 2546)
    aoi = aoi_for_tile(tile)
    assert aoi.utm_epsg == 32643
    assert aoi.bounds_utm == (165_000.0, 2_546_000.0, 166_000.0, 2_547_000.0)


def test_a_southern_tile_lands_on_its_square_too():
    tile = Tile(UtmZone(23, True), 686, 7462)
    assert aoi_for_tile(tile).bounds_utm == (686_000.0, 7_462_000.0, 687_000.0, 7_463_000.0)
