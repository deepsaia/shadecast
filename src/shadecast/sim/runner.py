"""Subprocess wall around the SOLWEIG physics engine.

solweig-gpu is GPL-3.0. shadecast is intended to stay permissively licensed so the
benchmark, its data and its baselines can be used without inheriting a copyleft
obligation. Importing a GPL library would defeat that.

The engine is therefore never imported. It is invoked as a subprocess through its
own console script, in its own environment, communicating only through files on
disk. This mirrors how KoMBench keeps a GPL CAD engine behind a process wall.

Set SHADECAST_SOLWEIG_BIN if the engine is not at the default path. The engine also
needs GDAL Python bindings and numba, neither of which solweig-gpu declares, which
is a second reason to isolate its environment.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

from .errors import EngineNotFound
from .result import RunResult

logger = logging.getLogger(__name__)

REQUIRED_INPUTS = ("Building_DSM.tif", "DEM.tif", "Trees.tif", "met.txt")

# The engine lives in its own uv environment beside the project one. Keeping it
# separate is what holds the GPL boundary: shadecast never imports it, and the two
# dependency sets never have to agree.
ENGINE_VENV = ".venv-engine"
ENGINE_SCRIPT = "thermal_comfort"


def candidate_paths() -> list[Path]:
    """Where the engine console script might be, most specific first."""
    override = os.environ.get("SHADECAST_SOLWEIG_BIN")
    found = [Path(override)] if override else []
    # Walk up from this module to the repo root, so the command works from anywhere.
    for parent in Path(__file__).resolve().parents:
        found.append(parent / ENGINE_VENV / "bin" / ENGINE_SCRIPT)
        if (parent / "pyproject.toml").exists():
            break
    found.append(Path.cwd() / ENGINE_VENV / "bin" / ENGINE_SCRIPT)
    return found


def engine_bin() -> str:
    """Locate the engine console script, preferring an explicit override."""
    for candidate in candidate_paths():
        if candidate.exists():
            return str(candidate)
    on_path = shutil.which(ENGINE_SCRIPT) or shutil.which("solweig_gpu")
    if on_path:
        return on_path
    raise EngineNotFound(
        "SOLWEIG engine not found. Create its environment with:\n"
        "  brew install gdal\n"
        f"  uv venv --python 3.12 {ENGINE_VENV}\n"
        f"  uv pip install --python {ENGINE_VENV} solweig-gpu numba "
        '"gdal==$(gdal-config --version)"\n'
        "solweig-gpu does not declare its GDAL or numba dependencies, which is why "
        "they are named explicitly. Set SHADECAST_SOLWEIG_BIN to override the path."
    )


def engine_version() -> str:
    """Report the engine version string, for provenance."""
    completed = subprocess.run(
        [engine_bin(), "--version"], capture_output=True, text=True, check=False
    )
    return (completed.stdout or completed.stderr).strip()


def build_command(
    base_path: Path,
    date: str,
    *,
    start: str | None,
    end: str | None,
    tile_size: int,
    save_svf: bool,
    save_shadow: bool,
    landcover: str | None = None,
) -> list[str]:
    """Assemble the engine invocation for one bundle."""
    command = [
        engine_bin(),
        "--base_path",
        str(base_path),
        "--date",
        date,
        "--building_dsm",
        "Building_DSM.tif",
        "--dem",
        "DEM.tif",
        "--trees",
        "Trees.tif",
        "--tile_size",
        str(tile_size),
        "--overlap",
        "20",
        "--use_own_met",
        "True",
        "--own_metfile",
        str(base_path / "met.txt"),
        # Roughness-length lookup wants a local ERA5 NetCDF we do not ship. It only
        # affects the wind-extinction term for UTCI and WBGT, not Tmrt.
        "--era5_z0_find",
        "False",
        "--use_uhi",
        "False",
        "--save_tmrt",
        "True",
        "--save_svf",
        str(save_svf),
        "--save_shadow",
        str(save_shadow),
    ]
    if landcover:
        # Only pass land cover when an intervention actually changes surface albedo.
        # Without it the engine uses a uniform 0.15, which is the setting every plan
        # before the intervention-type experiment ran under.
        command += ["--landcover", landcover]
    if start:
        command += ["--start", start]
    if end:
        command += ["--end", end]
    return command


def run(
    base_path: Path,
    date: str,
    *,
    start: str | None = None,
    end: str | None = None,
    tile_size: int = 1100,
    save_svf: bool = True,
    save_shadow: bool = True,
    landcover: str | None = None,
    timeout: int = 7200,
) -> RunResult:
    """Run SOLWEIG over a prepared bundle directory.

    The bundle must already contain the rasters and met file the engine expects.
    Outputs land in ``base_path/output_folder``.
    """
    base_path = Path(base_path)
    missing = [name for name in REQUIRED_INPUTS if not (base_path / name).exists()]
    if missing:
        raise FileNotFoundError(f"bundle {base_path} is missing {', '.join(missing)}")

    command = build_command(
        base_path,
        date,
        start=start,
        end=end,
        tile_size=tile_size,
        save_svf=save_svf,
        save_shadow=save_shadow,
        landcover=landcover,
    )
    logger.info("running engine over %s for %s", base_path, date)

    started = time.time()
    completed = subprocess.run(
        command, capture_output=True, text=True, timeout=timeout, check=False
    )
    elapsed = time.time() - started

    tmrt_path = next(base_path.glob("output_folder/*/TMRT_*.tif"), None)
    tail = "\n".join((completed.stderr or completed.stdout or "").splitlines()[-15:])

    if tmrt_path is None:
        raise RuntimeError(
            f"engine produced no Tmrt for {base_path} (rc={completed.returncode}) "
            f"after {elapsed:.0f}s:\n{tail}"
        )
    if completed.returncode != 0:
        # The engine writes Tmrt before the derived comfort indices and can fail on
        # the latter while Tmrt is complete and valid. Tmrt is all we consume, so
        # this is recoverable, but it is surfaced loudly rather than swallowed.
        logger.warning(
            "engine exited %d for %s but Tmrt was written; continuing. Tail:\n%s",
            completed.returncode,
            base_path,
            tail,
        )

    (base_path / "engine.json").write_text(
        json.dumps(
            {
                "engine": "solweig-gpu (GPL-3.0, invoked as a subprocess)",
                "version": engine_version(),
                "seconds": round(elapsed, 1),
                "date": date,
            },
            indent=2,
        )
    )
    logger.info("engine finished in %.1fs, wrote %s", elapsed, tmrt_path.name)
    return RunResult(base_path, elapsed, tmrt_path, completed.returncode)
