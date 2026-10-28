"""What is simulating or training now is read from the locks and checkpoints runs leave."""

import json
import os

from support.fixtures import fixture_centres, fixture_corpus, fixture_tiles

from shadecast.service.city_catalog import CityCatalog
from shadecast.service.model_catalog import ModelCatalog
from shadecast.service.run_status import RunStatus
from shadecast.service.selection import Selection
from shadecast.service.tile_index import TileIndex
from shadecast.surrogate.dataset import SIMULATION_LOCK
from shadecast.surrogate.training_state import CHECKPOINT_NAME, STARTED_NAME

TILE = "t43N_249_2547"


def _status(root) -> RunStatus:
    catalog = CityCatalog(
        Selection.resolved(fixture_corpus()),
        fixture_centres,
        TileIndex(root, fixture_tiles),
        ModelCatalog(root / "models"),
    )
    return RunStatus(catalog, root / "models")


def _unfinished(root, name: str, record: dict | None = None):
    """A checkpoint without a manifest; a record is the cities and tiles its start wrote."""
    model = root / "models" / name
    model.mkdir(parents=True)
    (model / CHECKPOINT_NAME).write_bytes(b"c")
    if record is not None:
        started = {"started": "2026-10-23T12:17:39+00:00", **record}
        (model / STARTED_NAME).write_text(json.dumps(started))
    return model


def _physics(root, designs: int):
    physics = root / "6143" / TILE / "physics"
    physics.mkdir(parents=True)
    for index in range(designs):
        (physics / f"clustered_{index:04d}").mkdir()
        (physics / f"clustered_{index:04d}" / "response.npz").write_bytes(b"")
    return physics


def test_a_live_lock_is_a_simulation_run_with_its_progress(tmp_path):
    physics = _physics(tmp_path, 3)
    (physics / SIMULATION_LOCK).write_text(str(os.getpid()))
    [run] = _status(tmp_path).runs()
    assert run.kind == "simulation" and run.city == "ahmedabad" and run.tile == TILE
    assert run.alive is True and run.designs_done == 3 and run.designs_planned == 17
    assert run.started


def test_a_stale_or_unreadable_lock_is_reported_as_not_alive(tmp_path):
    physics = _physics(tmp_path, 1)
    (physics / SIMULATION_LOCK).write_text("")
    [run] = _status(tmp_path).runs()
    assert run.alive is False


def test_a_checkpoint_without_a_manifest_is_a_training_run_named_by_its_start_record(tmp_path):
    one = _unfinished(
        tmp_path,
        "response-unet-ahmedabad-20261023T121739",
        {"cities": ["ahmedabad"], "tiles": [f"6143/{TILE}"]},
    )
    pooled = _unfinished(
        tmp_path,
        "response-unet-ahmedabad+lagos-20261024T090000",
        {"cities": ["ahmedabad", "lagos"], "tiles": [f"6143/{TILE}", "1289/t31N_537_714"]},
    )
    bare = _unfinished(tmp_path, "response-unet-x-20261024T100000")
    finished = _unfinished(tmp_path, "response-unet-ahmedabad-20261023T100000")
    (finished / "manifest.json").write_text("{}")
    runs = {run.model: run for run in _status(tmp_path).runs()}
    assert set(runs) == {one.name, pooled.name, bare.name}
    assert all(run.kind == "training" and run.alive is None for run in runs.values())
    assert runs[one.name].city == "ahmedabad" and runs[one.name].tile == TILE
    assert runs[one.name].started == "2026-10-23T12:17:39+00:00"
    assert runs[pooled.name].city == "ahmedabad, lagos" and runs[pooled.name].tile is None
    assert runs[bare.name].city == "unrecorded" and runs[bare.name].started


def test_nothing_running_is_an_empty_list(tmp_path):
    assert _status(tmp_path).runs() == []
