"""What is generating or training now is read from the locks and checkpoints runs leave."""

import os

from support.fixtures import fixture_centres, fixture_corpus, fixture_tiles

from shadecast.service.city_catalog import CityCatalog
from shadecast.service.run_status import RunStatus
from shadecast.service.tile_index import TileIndex
from shadecast.surrogate.dataset import GENERATION_LOCK
from shadecast.surrogate.training_state import CHECKPOINT_NAME

TILE = "t43N_249_2547"


def _status(root) -> RunStatus:
    catalog = CityCatalog(fixture_corpus(), fixture_centres, TileIndex(root, fixture_tiles))
    return RunStatus(catalog, root / "models")


def _surrogate(root, designs: int):
    surrogate = root / "6143" / TILE / "surrogate"
    surrogate.mkdir(parents=True)
    for index in range(designs):
        (surrogate / f"clustered_{index:04d}").mkdir()
        (surrogate / f"clustered_{index:04d}" / "response.npz").write_bytes(b"")
    return surrogate


def test_a_live_lock_is_a_generation_run_with_its_progress(tmp_path):
    surrogate = _surrogate(tmp_path, 3)
    (surrogate / GENERATION_LOCK).write_text(str(os.getpid()))
    [run] = _status(tmp_path).runs()
    assert run.kind == "generation" and run.city == "ahmedabad" and run.tile == TILE
    assert run.alive is True and run.designs_done == 3 and run.designs_planned == 17
    assert run.started


def test_a_stale_or_unreadable_lock_is_reported_as_not_alive(tmp_path):
    surrogate = _surrogate(tmp_path, 1)
    (surrogate / GENERATION_LOCK).write_text("")
    [run] = _status(tmp_path).runs()
    assert run.alive is False


def test_a_checkpoint_without_a_manifest_is_a_training_run(tmp_path):
    model = tmp_path / "6143" / TILE / "models" / "response-unet-ahmedabad-20261023T121739"
    model.mkdir(parents=True)
    (model / CHECKPOINT_NAME).write_bytes(b"c")
    finished = tmp_path / "6143" / TILE / "models" / "response-unet-ahmedabad-20261023T100000"
    finished.mkdir()
    (finished / CHECKPOINT_NAME).write_bytes(b"c")
    (finished / "manifest.json").write_text("{}")
    pooled = tmp_path / "models" / "response-unet-ahmedabad-2tiles-20261024T090000"
    pooled.mkdir(parents=True)
    (pooled / CHECKPOINT_NAME).write_bytes(b"c")
    runs = _status(tmp_path).runs()
    assert [(run.kind, run.model) for run in runs] == [
        ("training", "response-unet-ahmedabad-20261023T121739"),
        ("training", "response-unet-ahmedabad-2tiles-20261024T090000"),
    ]
    assert runs[0].tile == TILE and runs[1].tile is None and runs[0].alive is None


def test_nothing_running_is_an_empty_list(tmp_path):
    assert _status(tmp_path).runs() == []
