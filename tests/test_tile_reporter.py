"""A tile reports what it has: facts always, the baseline when run, the plans when generated."""

import os

import pytest
from support import synthetic_tile
from support.fixtures import fixture_centres, fixture_corpus, fixture_tiles

from shadecast.corpus.tile_paths import TilePaths
from shadecast.service.city_catalog import CityCatalog
from shadecast.service.missing_stage import MissingStage
from shadecast.service.model_catalog import ModelCatalog
from shadecast.service.selection import Selection
from shadecast.service.tile_index import TileIndex
from shadecast.service.tile_reporter import TileReporter, report_of


@pytest.fixture
def catalog(tmp_path) -> CityCatalog:
    return CityCatalog(
        Selection.resolved(fixture_corpus()),
        fixture_centres,
        TileIndex(tmp_path, fixture_tiles),
        ModelCatalog(tmp_path / "models"),
    )


def test_a_bundle_only_tile_reports_its_facts_and_nothing_it_lacks(tmp_path, catalog):
    tile = synthetic_tile.write_bundle(tmp_path)
    report = report_of(TilePaths.of_root(tile))
    assert report.city == "ahmedabad" and report.tile == synthetic_tile.TILE_ID
    assert report.facts.tier == "A" and report.facts.urban_centre.koppen == "BSh"
    assert report.facts.sources.get("terrain") == "Copernicus DEM"
    assert report.stages.bundle is True and report.stages.baseline is False
    assert (
        report.baseline is None
        and report.hourly == []
        and report.plans == []
        and report.physics is None
    )


def test_a_tile_with_a_baseline_reports_its_score_meteorology_and_hours(tmp_path, catalog):
    tile = synthetic_tile.write_bundle(tmp_path)
    synthetic_tile.write_baseline(tile)
    report = report_of(TilePaths.of_root(tile))
    assert report.baseline.exposure == synthetic_tile.BASELINE_C
    assert len(report.met) == 24 and len(report.hourly) == 24
    assert report.hourly[5].median == 35.0 and report.hourly[5].max == 35.0
    assert report.plans == [] and report.physics is None


def test_a_tile_with_designs_reports_plans_and_physics(tmp_path, catalog):
    tile = synthetic_tile.write_bundle(tmp_path)
    synthetic_tile.write_baseline(tile)
    synthetic_tile.write_designs(tile)
    report = report_of(TilePaths.of_root(tile))
    assert [plan.arrangement for plan in report.plans] == ["clustered", "corridor", "scattered"]
    assert report.physics.designs == 4


def test_a_baseline_whose_hourly_raster_is_gone_still_reports(tmp_path, catalog):
    tile = synthetic_tile.write_bundle(tmp_path)
    baseline = synthetic_tile.write_baseline(tile)
    (baseline / "output_folder" / "0_0" / "TMRT_0_0.tif").unlink()
    report = report_of(TilePaths.of_root(tile))
    assert report.baseline is not None and report.hourly == []


def test_the_second_report_is_read_from_the_cache_until_a_source_changes(tmp_path, catalog):
    tile = synthetic_tile.write_bundle(tmp_path)
    synthetic_tile.write_baseline(tile)
    synthetic_tile.write_designs(tile)
    paths = TilePaths.of_root(tile)
    first = report_of(paths)
    cached = paths.root / "derived" / "report.json"
    assert cached.exists()
    cached.write_text(cached.read_text().replace('"designs":4', '"designs":99'))
    assert report_of(paths).physics.designs == 99
    archive = paths.surrogate / "clustered_0101" / "response.npz"
    later = archive.stat().st_mtime_ns + 1_000_000
    os.utime(archive, ns=(later, later))
    assert report_of(paths).physics.designs == first.physics.designs == 4


def test_a_named_tile_and_the_furthest_tile_resolve_through_the_catalog(tmp_path, catalog):
    built = synthetic_tile.write_bundle(tmp_path)
    synthetic_tile.write_baseline(built)
    other = tmp_path / "6143" / "t43N_250_2547" / "bundle"
    other.mkdir(parents=True)
    (other / "provenance.json").write_text("{}")
    reporter = TileReporter(catalog)
    assert reporter.report("ahmedabad", synthetic_tile.TILE_ID).baseline is not None
    assert reporter.report_furthest("ahmedabad").tile == synthetic_tile.TILE_ID


def test_a_city_with_nothing_built_names_the_build_command(catalog):
    with pytest.raises(MissingStage, match="sdc build ahmedabad"):
        TileReporter(catalog).report_furthest("ahmedabad")
