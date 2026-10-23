"""Generation runs designs side by side, resumes from disk, and survives one failed run."""

import json
import os
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from shadecast.sim.result import RunResult
from shadecast.sim.runner import thread_environment
from shadecast.surrogate import dataset
from shadecast.surrogate.assessment import designs_for_tile
from shadecast.surrogate.generation_progress import GenerationProgress, clock, sparkline
from shadecast.surrogate.generation_settings import GenerationSettings
from shadecast.surrogate.patches import tile_key

SIDE = 24
PLAN = [
    {"family": "random_uniform", "seed": 1, "params": {"coverage": 0.2}},
    {"family": "clustered", "seed": 2, "params": {"coverage": 0.2, "blob_m": 2.0}},
    {"family": "sparse_probe", "seed": 3, "params": {"spacing_m": 6.0}},
]


def _write(path: Path, bands: np.ndarray, dtype: str = "float32") -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=SIDE,
        height=SIDE,
        count=bands.shape[0],
        dtype=dtype,
        crs="EPSG:32643",
        transform=from_origin(249000, 2548000, 1, 1),
    ) as raster:
        raster.write(bands.astype(dtype))


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    zeros = np.zeros((1, SIDE, SIDE), dtype="float32")
    _write(bundle / "Building_DSM.tif", zeros)
    _write(bundle / "DEM.tif", zeros)
    _write(bundle / "Trees.tif", zeros)
    _write(bundle / "landcover.tif", np.full((1, SIDE, SIDE), 30), dtype="uint8")  # grassland
    (bundle / "met.txt").write_text("header\n")
    (bundle / "provenance.json").write_text(
        json.dumps(
            {
                "city": {"key": "testville"},
                "tile": {"id": "t43N_249_2547"},
                "met": {"design_day": "2024-05-23"},
            }
        )
    )
    return bundle


class FakeEngine:
    """Writes a 24-band Tmrt stack: 50 C everywhere, 5 C cooler under new canopy."""

    def __init__(self, fail: str | None = None) -> None:
        self.calls: list[Path] = []
        self.threads: list[int | None] = []
        self.fail = fail

    def __call__(self, base_path: Path, date: str, threads: int | None = None) -> RunResult:
        self.calls.append(Path(base_path))
        self.threads.append(threads)
        if self.fail and Path(base_path).name == self.fail:
            raise RuntimeError("engine crashed on purpose")
        with rasterio.open(Path(base_path) / "Trees.tif") as raster:
            canopy = raster.read(1)
        tmrt = np.full((24, SIDE, SIDE), 50.0, dtype="float32") - 5.0 * (canopy > 0)
        out = Path(base_path) / "output_folder" / "0_0"
        out.mkdir(parents=True)
        _write(out / "TMRT_0_0.tif", tmrt)
        return RunResult(Path(base_path), 0.01, out / "TMRT_0_0.tif", 0)


def test_designs_run_side_by_side_and_the_manifest_keeps_plan_order(bundle, tmp_path, monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(dataset, "run", engine)
    out = tmp_path / "surrogate"
    summary = dataset.generate(bundle, out, GenerationSettings(plan=PLAN, jobs=2))
    assert summary["entries"] == 3
    assert [m["id"] for m in summary["manifest"]] == [
        "random_uniform_0001",
        "clustered_0002",
        "sparse_probe_0003",
    ]
    assert len(engine.calls) == 4  # baseline plus three designs
    assert engine.threads[0] is None  # the baseline runs alone with every core
    assert all(t is not None for t in engine.threads[1:])  # designs get their share
    response = np.load(out / "clustered_0002" / "response.npz")
    assert response["response"][response["placement"]].mean() == pytest.approx(5.0)
    assert summary["manifest"][1]["mean_response_C"] == pytest.approx(5.0)
    assert not (out / "clustered_0002" / "output_folder").exists()
    assert not (out / ".generating.lock").exists()


def test_a_second_run_resumes_without_touching_the_engine(bundle, tmp_path, monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(dataset, "run", engine)
    out = tmp_path / "surrogate"
    dataset.generate(bundle, out, GenerationSettings(plan=PLAN))
    calls = len(engine.calls)
    progress = GenerationProgress.quiet()
    summary = dataset.generate(bundle, out, GenerationSettings(plan=PLAN), progress)
    assert len(engine.calls) == calls
    assert summary["entries"] == 3
    assert progress.done_at_start == 3
    assert progress.baseline_kept


def test_a_stale_lock_is_removed_and_a_live_one_is_respected(bundle, tmp_path, monkeypatch):
    monkeypatch.setattr(dataset, "run", FakeEngine())
    out = tmp_path / "surrogate"
    out.mkdir()
    (out / ".generating.lock").write_text("999999999")
    dataset.generate(bundle, out, GenerationSettings(plan=PLAN[:1]))
    (out / ".generating.lock").write_text(str(os.getpid()))
    with pytest.raises(RuntimeError, match="already holds"):
        dataset.generate(bundle, out, GenerationSettings(plan=PLAN))


def test_one_failed_design_does_not_stop_the_others(bundle, tmp_path, monkeypatch):
    monkeypatch.setattr(dataset, "run", FakeEngine(fail="clustered_0002"))
    out = tmp_path / "surrogate"
    progress = GenerationProgress.quiet()
    with pytest.raises(RuntimeError, match="clustered_0002"):
        dataset.generate(bundle, out, GenerationSettings(plan=PLAN, jobs=3), progress)
    assert (out / "random_uniform_0001" / "response.npz").exists()
    assert (out / "sparse_probe_0003" / "response.npz").exists()
    assert not (out / "clustered_0002" / "response.npz").exists()
    assert progress.failed and "clustered_0002" in progress.failed[0]
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["entries"] == 2


def test_engine_threads_share_the_cores():
    assert dataset.engine_threads(GenerationSettings(jobs=1)) is None
    share = dataset.engine_threads(GenerationSettings(jobs=3))
    assert share == max(1, (os.cpu_count() or 1) // 3)
    assert dataset.engine_threads(GenerationSettings(jobs=3, engine_threads=4)) == 4
    with pytest.raises(ValueError, match="jobs"):
        GenerationSettings(jobs=0)


def test_thread_environment_caps_every_pool():
    env = thread_environment(6)
    assert env["OMP_NUM_THREADS"] == "6" and env["NUMBA_NUM_THREADS"] == "6"
    assert "OMP_NUM_THREADS" not in {
        k: v for k, v in thread_environment(None).items() if k not in os.environ
    }


def test_quiet_progress_counts_and_renders_nothing():
    progress = GenerationProgress.quiet()
    with progress:
        progress.start("testville t43N_249_2547", total=3, done=1)
        progress.design_started("a")
        progress.design_done(
            {
                "id": "a",
                "engine_seconds": 10.0,
                "mean_response_C": 4.0,
                "family": "clustered",
                "coverage": 0.1,
                "placed_px": 5,
            }
        )
        progress.design_skipped("b", "empty placement")
    assert progress.completed() == 3
    assert progress.mean_seconds() == 10.0
    assert progress.phase == "done"
    assert progress.live is None


def test_sparkline_and_clock():
    assert sparkline([1.0, 2.0, 3.0]) == "▁▄█"
    assert sparkline([2.0, 2.0]) == "▄▄"
    assert sparkline([]) == ""
    assert clock(65) == "1m 05s"
    assert clock(3725) == "1h 02m"


def test_an_interrupt_cancels_the_designs_not_yet_started(bundle, tmp_path, monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(dataset, "run", engine)

    def interrupt(futures, progress, results, failures):
        raise KeyboardInterrupt

    monkeypatch.setattr(dataset, "collect_results", interrupt)
    stopped = {"n": 0}
    monkeypatch.setattr(dataset, "stop_running_engines", lambda: stopped.__setitem__("n", 1) or 0)
    with pytest.raises(KeyboardInterrupt):
        dataset.generate(bundle, tmp_path / "surrogate", GenerationSettings(plan=PLAN, jobs=1))
    # The baseline ran, and at most the one design that had already started.
    assert len(engine.calls) <= 2
    assert stopped["n"] == 1
    assert not (tmp_path / "surrogate" / ".generating.lock").exists()


def test_tile_label_says_one_tile_of_the_centre():
    provenance = {
        "city": {"key": "savannah"},
        "tile": {"id": "t17N_488_3550"},
        "urban_centre": {"tiles": 64},
    }
    assert (
        dataset.tile_label(Path("x"), provenance) == "savannah, tile t17N_488_3550, one of 64 tiles"
    )
    assert dataset.tile_label(Path("plain"), {}) == "plain"


def test_tile_key_names_city_and_tile_or_the_directory(bundle, tmp_path):
    assert tile_key(bundle) == "testville:t43N_249_2547"
    plain = tmp_path / "plain"
    plain.mkdir()
    assert tile_key(plain) == "plain"


def test_designs_for_tile_keeps_this_tiles_held_out_designs():
    held = ["clustered_0105", "savannah:t1/corridor_0302", "savannah:t2/corridor_0305"]
    assert designs_for_tile(held, "savannah:t1") == ["clustered_0105", "corridor_0302"]
    assert designs_for_tile(held, "other") == ["clustered_0105"]
