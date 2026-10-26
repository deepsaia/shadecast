"""The city catalog answers what the selected cities are and what their tiles have reached."""

from pathlib import Path

import pytest
from support.fixtures import fixture_centres, fixture_corpus, fixture_tiles

from shadecast.corpus.urban_centres import UrbanCentres
from shadecast.service.city_catalog import CityCatalog
from shadecast.service.missing_stage import MissingStage
from shadecast.service.stage_counts import StageCounts
from shadecast.service.tile_index import TileIndex
from shadecast.service.unknown_city import UnknownCity
from shadecast.service.unknown_tile import UnknownTile

ROWS = fixture_tiles()
DENSEST = max(ROWS, key=lambda row: float(row.get("density_2020_per_km2", 0)))["id"]
SPARSEST = min(ROWS, key=lambda row: float(row.get("density_2020_per_km2", 0)))["id"]


@pytest.fixture
def root(tmp_path) -> Path:
    return tmp_path


@pytest.fixture
def catalog(root) -> CityCatalog:
    return CityCatalog(fixture_corpus(), fixture_centres, TileIndex(root, fixture_tiles))


def _prove(root: Path, tile_id: str, *stages: str, urban_centre: int = 6143) -> Path:
    """Write the files that prove the named stages for one tile, and nothing else."""
    tile = root / str(urban_centre) / tile_id
    proofs = {
        "bundle": tile / "bundle" / "provenance.json",
        "baseline": tile / "surrogate" / "baseline" / "tmrt_daylight.npy",
        "physics": tile / "surrogate" / "manifest.json",
        "model": tile / "models" / "unet-1" / "model.pt",
        "results": tile / "results.json",
    }
    tile.mkdir(parents=True, exist_ok=True)
    for stage in stages:
        proofs[stage].parent.mkdir(parents=True, exist_ok=True)
        proofs[stage].write_bytes(b"")
    return tile


def test_cities_are_the_selection_with_nothing_built(catalog):
    listed = catalog.cities()
    assert [city.key for city in listed] == ["ahmedabad", "london"]
    assert listed[0].name == "Ahmedabad" and listed[0].ucdb_id == 6143
    assert listed[0].stages == StageCounts(tiles=listed[0].stages.tiles)
    assert listed[0].stages.tiles > 0


def test_stage_counts_follow_the_files_that_prove_each_stage(root, catalog):
    _prove(root, "t43N_249_2547", "bundle", "baseline", "physics")
    _prove(root, "t43N_250_2547", "bundle")
    counts = catalog.stage_counts("ahmedabad")
    assert (counts.bundle, counts.baseline, counts.physics, counts.model, counts.results) == (
        2,
        1,
        1,
        0,
        0,
    )
    assert catalog.city("ahmedabad").stages == counts


def test_a_centre_is_found_by_key_id_slug_and_name(catalog):
    for text in ("ahmedabad", "6143", "Ahmedabad"):
        assert catalog.centre(text).id == 6143, text


def test_an_unknown_text_raises_unknown_city(catalog):
    with pytest.raises(UnknownCity, match="atlantis"):
        catalog.centre("atlantis")
    with pytest.raises(UnknownCity, match="atlantis"):
        catalog.city("atlantis")


def test_tiles_come_densest_first_with_their_stages(root, catalog):
    _prove(root, DENSEST, "bundle")
    tiles = catalog.tiles("ahmedabad")
    assert len(tiles) == len(ROWS)
    assert tiles[0].id == DENSEST and tiles[-1].id == SPARSEST
    assert tiles[0].stages.bundle is True and tiles[-1].stages.bundle is False


def test_a_tiles_file_from_an_older_build_is_read_for_what_it_has(root):
    index = TileIndex(root, lambda centre: [{"id": "t43N_249_2547", "x_km": 6897, "people": 1}])
    catalog = CityCatalog(fixture_corpus(), fixture_centres, index)
    tiles = catalog.tiles("ahmedabad")
    assert [tile.id for tile in tiles] == ["t43N_249_2547"]
    assert tiles[0].population_2020 == 0.0


def test_tiles_on_disk_are_the_directories_present_in_id_order(root, catalog):
    _prove(root, "t43N_250_2547", "bundle")
    _prove(root, "t43N_249_2547")
    _prove(root, "t43N_999_9999", "bundle")
    listed = catalog.tiles_on_disk("6143")
    assert [tile.tile for tile in listed] == ["t43N_249_2547", "t43N_250_2547", "t43N_999_9999"]
    assert [tile.stages.bundle for tile in listed] == [False, True, True]
    assert "t43N_999_9999" not in [tile.id for tile in catalog.tiles("6143")]


def test_a_tile_location_has_every_path_and_its_stages(root, catalog):
    _prove(root, "t43N_249_2546", "bundle", "results")
    location = catalog.tile("ahmedabad", "t43N_249_2546")
    assert location.urban_centre == 6143 and location.tile == "t43N_249_2546"
    assert location.bundle == str(root / "6143" / "t43N_249_2546" / "bundle")
    assert location.results == str(root / "6143" / "t43N_249_2546" / "results.json")
    assert location.stages.bundle is True and location.stages.results is True
    assert location.stages.baseline is False


def _no_database() -> UrbanCentres:
    raise AssertionError("the database was loaded for a key or an id")


def test_keys_and_ids_never_load_the_database(root):
    catalog = CityCatalog(fixture_corpus(), _no_database, TileIndex(root, fixture_tiles))
    _prove(root, "t43N_249_2547", "bundle")
    assert [city.key for city in catalog.cities()] == ["ahmedabad", "london"]
    assert catalog.city("ahmedabad").stages.bundle == 1
    assert catalog.stage_counts("6143").bundle == 1
    assert catalog.tile("ahmedabad", "t43N_249_2547").stages.bundle is True
    assert [tile.tile for tile in catalog.tiles_on_disk("6143")] == ["t43N_249_2547"]


def test_a_malformed_tile_id_raises_unknown_tile(catalog):
    with pytest.raises(UnknownTile, match="6908"):
        catalog.tile("ahmedabad", "6908")


def test_statistics_carry_the_counts_the_quantiles_and_the_stages(root, catalog):
    _prove(root, DENSEST, "bundle", "baseline")
    statistics = catalog.statistics("ahmedabad")
    assert statistics.urban_centre == 6143 and statistics.name == "Ahmedabad"
    assert statistics.tiles == len(ROWS)
    assert statistics.populated_tiles == sum(
        float(row.get("population_2020", 0)) > 0 for row in ROWS
    )
    assert "built_fraction" in statistics.quantiles
    assert statistics.stages.bundle == 1 and statistics.stages.baseline == 1
    assert statistics.stages.tiles == catalog.centre("ahmedabad").tiles


def test_refresh_describes_the_tiles_again(root):
    calls: list[int] = []

    def describe(centre: object) -> list[dict]:
        calls.append(1)
        return fixture_tiles(centre)

    catalog = CityCatalog(fixture_corpus(), fixture_centres, TileIndex(root, describe))
    catalog.tiles("ahmedabad")
    catalog.tiles("ahmedabad")
    catalog.refresh("ahmedabad")
    assert len(calls) == 2


def test_tile_paths_are_the_record_a_report_reads(root, catalog):
    paths = catalog.tile_paths("ahmedabad", "t43N_249_2547")
    assert paths.root == root / "6143" / "t43N_249_2547"


def test_the_furthest_tile_prefers_physics_over_baseline_over_bundle(root, catalog):
    _prove(root, DENSEST, "bundle")
    _prove(root, "t43N_250_2546", "bundle", "baseline")
    _prove(root, SPARSEST, "bundle", "baseline", "physics")
    assert catalog.furthest_tile("ahmedabad").id == SPARSEST
    (root / "6143" / SPARSEST / "surrogate" / "manifest.json").unlink()
    assert catalog.furthest_tile("ahmedabad").id == "t43N_250_2546"


def test_a_city_with_nothing_built_has_no_furthest_tile(catalog):
    with pytest.raises(MissingStage, match="sdc build ahmedabad"):
        catalog.furthest_tile("ahmedabad")
