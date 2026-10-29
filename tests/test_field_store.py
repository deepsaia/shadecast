"""The field store reads a tile's arrays from the pipeline's files and names what is missing."""

import numpy as np
import pytest
from support import synthetic_tile

from shadecast.corpus.tile_paths import TilePaths
from shadecast.service.field_store import FieldStore
from shadecast.service.missing_stage import MissingStage


@pytest.fixture
def paths(tmp_path) -> TilePaths:
    tile = synthetic_tile.write_bundle(tmp_path)
    synthetic_tile.write_baseline(tile)
    synthetic_tile.write_designs(tile)
    return TilePaths.of_root(tile)


def test_heights_are_the_surface_above_the_terrain(paths):
    assert np.array_equal(FieldStore(paths).heights(), synthetic_tile.heights())


def test_population_and_baseline_fields_read_back(paths):
    store = FieldStore(paths)
    assert float(store.population().sum()) == 512.0
    assert np.all(store.baseline_daylight() == synthetic_tile.BASELINE_C)


def test_the_hourly_field_has_one_band_per_hour(paths):
    hours = FieldStore(paths).hourly_temperature()
    assert hours.shape == (24, synthetic_tile.SIZE, synthetic_tile.SIZE)
    assert float(hours[5].max()) == 35.0


def test_design_ids_come_from_the_manifest_and_responses_read_back(paths):
    store = FieldStore(paths)
    assert store.design_ids() == [*synthetic_tile.PLAN_IDS, synthetic_tile.PROBE_ID]
    placement, response = store.response("clustered_0101")
    assert placement.dtype == bool and int(placement.sum()) == 16
    assert float(response[placement].mean()) == 1.0


def test_meteorology_has_one_row_per_hour(paths):
    met = FieldStore(paths).meteorology()
    assert [row.hour for row in met] == list(range(24))
    assert met[12].solar == 800.0 and met[0].air_c == 30.0


def test_a_missing_bundle_names_the_stage_and_the_command(tmp_path):
    store = FieldStore(TilePaths(tmp_path, 6143, TilePaths.of_root(tmp_path / "6143" / "t43N_249_2547").tile))
    with pytest.raises(MissingStage, match="bundle") as caught:
        store.heights()
    assert "sdc build" in str(caught.value)


def test_a_missing_baseline_and_missing_physics_are_named(tmp_path):
    paths = TilePaths.of_root(synthetic_tile.write_bundle(tmp_path))
    store = FieldStore(paths)
    with pytest.raises(MissingStage, match="baseline"):
        store.baseline_daylight()
    with pytest.raises(MissingStage, match="physics"):
        store.design_ids()
    assert store.has_hourly() is False


def test_sources_are_the_files_a_report_depends_on(paths):
    sources = FieldStore(paths).sources()
    names = sorted(path.name for path in sources)
    assert names.count("response.npz") == 4
    assert "provenance.json" in names and "tmrt_daylight.npy" in names and "manifest.json" in names
