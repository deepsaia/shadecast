"""Simulation is addressed by city and tile: the densest built tile, named tiles, or all of them."""

import json
from pathlib import Path

import pytest
from support.fixtures import fixture_centres
from support.fixtures import fixture_corpus
from support.fixtures import fixture_tiles

from shadecast.service import simulation_service
from shadecast.service.city_catalog import CityCatalog
from shadecast.service.missing_stage import MissingStage
from shadecast.service.model_catalog import ModelCatalog
from shadecast.service.null_progress import NullProgress
from shadecast.service.selection import Selection
from shadecast.service.simulation_request import SimulationRequest
from shadecast.service.simulation_service import SimulationService
from shadecast.service.tile_index import TileIndex

DENSE, SPARSE = "t43N_250_2547", "t43N_249_2547"


@pytest.fixture
def service(tmp_path) -> SimulationService:
    catalog = CityCatalog(
        Selection.resolved(fixture_corpus()),
        fixture_centres,
        TileIndex(tmp_path, fixture_tiles),
        ModelCatalog(tmp_path / "models"),
    )
    return SimulationService(catalog)


def _built(root: Path, tile_id: str) -> Path:
    bundle = root / "6143" / tile_id / "bundle"
    bundle.mkdir(parents=True)
    (bundle / "provenance.json").write_text(json.dumps({"tile": {"id": tile_id}}))
    return bundle


def _rank(root: Path) -> None:
    (root / "6143" / "tiles.json").write_text(
        json.dumps(
            {
                "tiles": [
                    {"id": SPARSE, "population_2020": 100, "density_2020_per_km2": 100},
                    {"id": DENSE, "population_2020": 900, "density_2020_per_km2": 900},
                ]
            }
        )
    )


def test_without_tiles_the_densest_built_tile_is_chosen(tmp_path, service):
    _built(tmp_path, SPARSE)
    _built(tmp_path, DENSE)
    _rank(tmp_path)
    [paths] = service.tiles_for(SimulationRequest(target="ahmedabad"))
    assert paths.tile.id == DENSE


def test_named_tiles_and_all_tiles_are_honored(tmp_path, service):
    _built(tmp_path, SPARSE)
    _built(tmp_path, DENSE)
    _rank(tmp_path)
    named = service.tiles_for(SimulationRequest(target="ahmedabad", tiles=SPARSE))
    assert [paths.tile.id for paths in named] == [SPARSE]
    every = service.tiles_for(SimulationRequest(target="ahmedabad", tiles="all"))
    assert [paths.tile.id for paths in every] == [DENSE, SPARSE]
    assert len(service.tiles_for(SimulationRequest(target="ahmedabad", tiles=""))) == 2


def test_a_city_without_a_bundle_and_an_unbuilt_tile_name_the_build_command(tmp_path, service):
    with pytest.raises(MissingStage, match="sdc build ahmedabad"):
        service.tiles_for(SimulationRequest(target="ahmedabad"))
    _built(tmp_path, DENSE)
    with pytest.raises(MissingStage, match=f"sdc build ahmedabad --tiles {SPARSE}"):
        service.tiles_for(SimulationRequest(target="ahmedabad", tiles=SPARSE))


def test_an_output_directory_applies_to_one_tile_only(tmp_path, service):
    _built(tmp_path, SPARSE)
    _built(tmp_path, DENSE)
    with pytest.raises(ValueError, match="one tile"):
        service.tiles_for(SimulationRequest(target="ahmedabad", tiles="all", out=tmp_path / "o"))


def test_simulate_runs_the_simulation_beside_the_bundle_or_where_asked(tmp_path, service, monkeypatch):
    bundle = _built(tmp_path, DENSE)
    seen: list[tuple] = []

    def fake_simulate(bundle_dir, destination, settings, progress):
        seen.append((Path(bundle_dir), Path(destination), settings.jobs, settings.kind))
        progress.started("x", total=1, done=0)
        return {"entries": 1, "manifest": []}

    monkeypatch.setattr(simulation_service, "simulate", fake_simulate)
    [paths] = service.tiles_for(SimulationRequest(target="ahmedabad", jobs=3))
    outcome = service.simulate(paths, SimulationRequest(target="ahmedabad", jobs=3), NullProgress())
    assert seen == [(bundle, bundle.parent / "physics", 3, "tree")]
    assert outcome.tile == DENSE and outcome.entries == 1
    assert outcome.destination == str(bundle.parent / "physics")
    service.simulate(paths, SimulationRequest(target="ahmedabad", out=tmp_path / "o"), NullProgress())
    assert seen[-1][1] == tmp_path / "o"
