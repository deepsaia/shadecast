"""Generate surrogate training data by running designed interventions through the physics.

One entry is a (placement, delta Tmrt) pair over the whole study area, produced by
one engine call. Sparse probe designs make each call yield many independent
single-intervention responses rather than one, which is what keeps the physics
budget affordable.

Everything is written to disk as it completes, so a long generation run can be
interrupted and resumed without losing work: designs already on disk are skipped, and a
lock left by a process that no longer runs is removed. The baseline runs alone first,
because every design needs it; the designs then run ``jobs`` at a time, each engine
process capped to its share of the cores.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import rasterio

from ..data.landcover import to_umep
from ..interventions import apply, feasibility_mask
from ..pipeline import BUNDLE_FILES, daylight_mean, read_band
from ..service.null_progress import NullProgress
from ..service.progress_listener import ProgressListener
from ..sim.result import RunResult
from ..sim.runner import run, stop_running_engines
from . import designs
from .generation_events import BASELINE, BASELINE_PHASE
from .generation_settings import GenerationSettings
from .tile_context import TileContext

logger = logging.getLogger(__name__)

GENERATION_LOCK = ".generating.lock"


def default_plan() -> list[dict]:
    """The standard generation plan for one city.

    Four probe lattices at different offsets give clean isolated responses across
    varied geometry. The dense families then supply the interaction signal, which
    is the part no single-tree kernel can predict.
    """
    plan: list[dict] = []
    for seed in range(4):
        plan.append({"family": "sparse_probe", "seed": seed, "params": {}})
    for coverage in (0.01, 0.02, 0.05, 0.10, 0.20, 0.30):
        plan.append(
            {
                "family": "clustered",
                "seed": 100 + int(coverage * 100),
                "params": {"coverage": coverage, "blob_m": 20.0},
            }
        )
    for coverage in (0.01, 0.05, 0.10, 0.20):
        plan.append(
            {
                "family": "random_uniform",
                "seed": 200 + int(coverage * 100),
                "params": {"coverage": coverage},
            }
        )
    for coverage in (0.02, 0.05, 0.10):
        plan.append(
            {
                "family": "corridor",
                "seed": 300 + int(coverage * 100),
                "params": {"coverage": coverage},
            }
        )
    return plan


def make_placement(family: str, feasible: np.ndarray, seed: int, params: dict) -> np.ndarray:
    """Build one placement from a design family."""
    rng = np.random.default_rng(seed)
    builder = getattr(designs, family, None)
    if builder is None:
        raise KeyError(f"unknown design family {family!r}, expected one of {designs.FAMILIES}")
    return builder(feasible, rng, **params)


def entry_id(family: str, seed: int) -> str:
    return f"{family}_{seed:04d}"


def generate(
    bundle: Path,
    out_dir: Path,
    settings: GenerationSettings | None = None,
    progress: ProgressListener | None = None,
) -> dict:
    """Run every design in the plan and store the resulting response fields.

    Holds an exclusive lock on the output directory. Two generators sharing one
    directory corrupt each other, because each deletes the engine scratch output
    after reading it and will happily delete the other's work in progress. That
    happened once and cost an hour of physics before it was noticed.
    """
    bundle, out_dir = Path(bundle), Path(out_dir)
    settings = settings if settings is not None else GenerationSettings()
    progress = progress if progress is not None else NullProgress()
    out_dir.mkdir(parents=True, exist_ok=True)

    lock = out_dir / GENERATION_LOCK
    acquire_lock(lock)
    try:
        return _generate(bundle, out_dir, settings, progress)
    finally:
        lock.unlink(missing_ok=True)


def acquire_lock(lock: Path) -> None:
    """Create the lock, or fail if a live process holds it. A dead holder's lock is removed."""
    for attempt in range(2):
        try:
            handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            if attempt == 0 and lock_is_stale(lock):
                logger.warning("removing stale lock %s: its process no longer runs", lock)
                lock.unlink(missing_ok=True)
                continue
            raise RuntimeError(
                f"another generator already holds {lock}. Generation is not safe to run "
                f"twice on one directory. Remove the lock only if none is running."
            ) from exc
        os.write(handle, str(os.getpid()).encode())
        os.close(handle)
        return


def lock_is_stale(lock: Path) -> bool:
    """True when the process whose id the lock records no longer exists."""
    try:
        pid = int(lock.read_text().strip() or 0)
    except (OSError, ValueError):
        return True
    if pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


def tile_label(bundle: Path, provenance: dict) -> str:
    """``city, tile t..., one of N tiles`` for a tile bundle, else the bundle's directory name.

    One generation run covers one tile: every design is an engine run over the same square
    kilometre. The label says how many tiles the urban centre has, so nobody mistakes the
    designs for tiles.
    """
    city = provenance.get("city", {}).get("key")
    tile = provenance.get("tile", {}).get("id")
    total = provenance.get("urban_centre", {}).get("tiles")
    if city and tile:
        count = f", one of {total:,} tiles" if total else ""
        return f"{city}, tile {tile}{count}"
    return bundle.name


def engine_threads(settings: GenerationSettings) -> int | None:
    """Threads per engine process: an even share of the cores when several run at once."""
    if settings.engine_threads is not None:
        return settings.engine_threads
    if settings.jobs == 1:
        return None
    return max(1, (os.cpu_count() or 1) // settings.jobs)


def _generate(
    bundle: Path, out_dir: Path, settings: GenerationSettings, progress: ProgressListener
) -> dict:
    """Body of :func:`generate`, run while the directory lock is held."""
    provenance = json.loads((bundle / "provenance.json").read_text())
    design_day = provenance["met"]["design_day"]
    plan = settings.plan if settings.plan is not None else default_plan()

    building_dsm, _ = read_band(bundle / "Building_DSM.tif")
    terrain, _ = read_band(bundle / "DEM.tif")
    canopy, profile = read_band(bundle / "Trees.tif")
    land_cover, _ = read_band(bundle / "landcover.tif")
    building_height = np.maximum(building_dsm - terrain, 0)
    umep_cover = to_umep(land_cover, building_height)
    feasible = feasibility_mask(umep_cover, building_height, settings.kind)
    profile.update(dtype="float32", count=1)

    names = [entry_id(spec["family"], spec["seed"]) for spec in plan]
    results: dict[str, dict] = {}
    pending: list[dict] = []
    for name, spec in zip(names, plan, strict=True):
        if (out_dir / name / "response.npz").exists():
            results[name] = json.loads((out_dir / name / "meta.json").read_text())
            logger.debug("%s already generated, skipping", name)
        else:
            pending.append(spec)
    progress.started(tile_label(bundle, provenance), total=len(plan), done=len(results))

    baseline_tmrt = ensure_baseline(bundle, out_dir, design_day, progress)
    context = TileContext(
        bundle=bundle,
        out_dir=out_dir,
        design_day=design_day,
        kind=settings.kind,
        canopy=canopy,
        umep_cover=umep_cover,
        feasible=feasible,
        profile=profile,
        baseline_tmrt=baseline_tmrt,
        engine_threads=engine_threads(settings),
    )
    failures = run_designs(context, pending, settings.jobs, progress, results)

    manifest = [results[name] for name in names if name in results]
    summary = {
        "city": bundle.name,
        "kind": settings.kind,
        "entries": len(manifest),
        "design_day": design_day,
        "manifest": manifest,
    }
    (out_dir / "manifest.json").write_text(json.dumps(summary, indent=2))
    if failures:
        raise RuntimeError(
            f"{len(failures)} of {len(pending)} designs failed: {', '.join(failures)}. "
            f"The rest are on disk; run again to retry the failed ones."
        )
    return summary


def ensure_baseline(
    bundle: Path, out_dir: Path, design_day: str, progress: ProgressListener
) -> np.ndarray:
    """The untouched tile's daylight mean Tmrt, run through the engine once and kept."""
    run_baseline_once(bundle, out_dir, design_day, progress)
    return np.load(out_dir / "baseline" / "tmrt_daylight.npy")


def run_baseline_once(
    bundle: Path, out_dir: Path, design_day: str, progress: ProgressListener
) -> RunResult | None:
    """The engine over the untouched tile, unless its daylight field is already on disk.

    Four arguments: the bundle, where the baseline lives, the day, and who to tell. Returns
    the engine run, or None when the field was kept and no engine ran.
    """
    baseline_dir = out_dir / "baseline"
    if (baseline_dir / "tmrt_daylight.npy").exists():
        progress.step_skipped(BASELINE, "kept from disk")
        return None
    baseline_dir.mkdir(parents=True, exist_ok=True)
    for name in BUNDLE_FILES:
        shutil.copy(bundle / name, baseline_dir / name)
    logger.debug("%s: baseline physics", bundle.name)
    progress.phase(BASELINE_PHASE)
    baseline_run = run(baseline_dir, design_day)
    np.save(baseline_dir / "tmrt_daylight.npy", daylight_mean(baseline_run.tmrt_path))
    progress.step_done(BASELINE, baseline_run.seconds, {})
    return baseline_run


def run_designs(
    context: TileContext,
    pending: list[dict],
    jobs: int,
    progress: ProgressListener,
    results: dict[str, dict],
) -> list[str]:
    """Run the pending designs ``jobs`` at a time. Returns the ids that failed."""
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(run_design, context, spec, progress): spec for spec in pending}
        try:
            collect_results(futures, progress, results, failures)
        except KeyboardInterrupt:
            # Stop the engines that are running and never start the queued designs. The
            # finished ones are on disk; a rerun of the same command continues from them.
            stopped = stop_running_engines()
            logger.warning(
                "interrupted: stopped %d running engine run(s), cancelled the rest", stopped
            )
            pool.shutdown(wait=False, cancel_futures=True)
            raise
    return failures


def collect_results(
    futures: dict, progress: ProgressListener, results: dict[str, dict], failures: list[str]
) -> None:
    """Gather each design as it finishes, recording failures instead of stopping."""
    for future in as_completed(futures):
        spec = futures[future]
        name = entry_id(spec["family"], spec["seed"])
        try:
            meta = future.result()
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
            # One failed engine run must not throw away the others still running.
            logger.error("design %s failed: %s", name, error)
            progress.step_failed(name, str(error).splitlines()[0])
            failures.append(name)
            continue
        if meta is not None:
            results[name] = meta


def run_design(context: TileContext, spec: dict, progress: ProgressListener) -> dict | None:
    """One design through the engine: edit the canopy, run, keep the response, prune."""
    name = entry_id(spec["family"], spec["seed"])
    target = context.out_dir / name
    placement = make_placement(spec["family"], context.feasible, spec["seed"], spec["params"])
    if not placement.any():
        logger.warning("design %s produced an empty placement, skipping", name)
        progress.step_skipped(name, "empty placement")
        return None

    progress.step_started(name, {"target": target})
    target.mkdir(parents=True, exist_ok=True)
    for fname in BUNDLE_FILES:
        shutil.copy(context.bundle / fname, target / fname)
    new_canopy, _ = apply(context.kind, placement, context.canopy, context.umep_cover)
    with rasterio.open(target / "Trees.tif", "w", **context.profile) as destination:
        destination.write(new_canopy.astype("float32"), 1)

    started = time.time()
    engine_run = run(target, context.design_day, threads=context.engine_threads)
    response = context.baseline_tmrt - daylight_mean(engine_run.tmrt_path)

    np.savez_compressed(
        target / "response.npz", placement=placement, response=response.astype("float32")
    )
    meta = {
        "id": name,
        "family": spec["family"],
        "seed": spec["seed"],
        "params": spec["params"],
        "kind": context.kind,
        "city": context.bundle.name,
        "design_day": context.design_day,
        "placed_px": int(placement.sum()),
        "coverage": round(float(placement.mean()), 5),
        "mean_response_C": round(float(response[placement].mean()), 3),
        "engine_seconds": round(time.time() - started, 1),
        "engine_threads": context.engine_threads,
    }
    (target / "meta.json").write_text(json.dumps(meta, indent=2))
    logger.debug(
        "%s: %d px, mean %.2f C, %.0fs",
        name,
        meta["placed_px"],
        meta["mean_response_C"],
        meta["engine_seconds"],
    )
    # The engine writes a large multi-band stack per run; keep only what the
    # surrogate needs so a full generation does not fill the disk.
    shutil.rmtree(target / "output_folder", ignore_errors=True)
    shutil.rmtree(target / "processed_inputs", ignore_errors=True)
    progress.step_done(name, float(meta["engine_seconds"]), meta)
    return meta
