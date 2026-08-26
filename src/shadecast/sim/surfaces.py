"""Surface class table for the physics engine, extended with high-albedo classes.

SOLWEIG reads per-class albedo, emissivity and a ground-temperature response from a
fixed text table shipped inside the engine package. That table has no high-albedo
entries, so cool roofs and reflective pavement cannot be represented at all without
supplying our own.

**A latent engine bug makes this dangerous, so it is guarded here.** The lookup in
`Tgmaps_v1` substitutes float albedos into `np.copy(lc_grid)`. If the land cover
raster is an integer type, every albedo truncates to zero, meaning perfectly
absorbing surfaces, and no error is raised. Verified directly: uint8 and int32 both
produce an all-zero albedo grid while float32 is correct. Land cover must therefore
be written as float32, and `write_table` refuses to install a table without saying so.

Albedo values below are the ones the reflective-surface literature reports for
commercially applied products, and they propagate directly into any result about
cool roofs or reflective pavement, so they are recorded with every run.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TABLE_FILENAME = "landcoverclasses_2016a.txt"

# name, code, albedo, emissivity, Ts_deg, Tstart, TmaxLST
STOCK_CLASSES = (
    ("Cobble_stone_2014a", 0, 0.20, 0.95, 0.37, -3.41, 15.0),
    ("Dark_asphalt", 1, 0.18, 0.95, 0.58, -9.78, 15.0),
    ("Roofs(buildings)", 2, 0.18, 0.95, 0.58, -9.78, 15.0),
    ("Grass_unmanaged", 5, 0.16, 0.94, 0.21, -3.38, 14.0),
    ("bare_soil", 6, 0.25, 0.94, 0.33, -3.01, 14.0),
    ("Water", 7, 0.05, 0.98, 0.00, 0.00, 12.0),
    ("Walls", 99, 0.20, 0.90, 0.58, -3.41, 15.0),
)

# Codes 3 and 4 are free in the stock table. Note that solweig.py hardcodes
# `lc_grid == 3` as water in two places for the nocturnal water temperature, so
# code 3 is NOT safe to reuse. Cool surfaces therefore take 4 and 8.
COOL_ROOF_CODE = 4
COOL_PAVING_CODE = 8

EXTENDED_CLASSES = (
    *STOCK_CLASSES,
    # A white or high-albedo coated roof.
    ("Cool_roof", COOL_ROOF_CODE, 0.65, 0.90, 0.58, -9.78, 15.0),
    # Light-coloured reflective paving.
    ("Cool_paving", COOL_PAVING_CODE, 0.40, 0.94, 0.37, -3.41, 15.0),
)

HEADER = "Name              Code Alb  Emis Ts_deg Tstart TmaxLST"


def render_table(classes=EXTENDED_CLASSES) -> str:
    lines = [HEADER]
    for name, code, albedo, emissivity, ts_deg, tstart, tmax in classes:
        lines.append(
            f"{name:<18s} {code:<4d} {albedo:.2f} {emissivity:.2f} "
            f"{ts_deg:.2f}   {tstart:.2f}  {tmax:.1f}"
        )
    return "\n".join(lines) + "\n"


def engine_package_dir(engine_bin: str) -> Path:
    """Locate the engine package directory from its console script path."""
    root = Path(engine_bin).resolve().parent.parent
    matches = list(root.glob("lib/python*/site-packages/solweig_gpu"))
    if not matches:
        raise FileNotFoundError(f"could not find solweig_gpu package under {root}")
    return matches[0]


def install(engine_bin: str, classes=EXTENDED_CLASSES) -> Path:
    """Write the extended class table into the engine environment.

    Keeps a one-time backup of the original so the stock behaviour is recoverable.
    """
    package = engine_package_dir(engine_bin)
    target = package / TABLE_FILENAME
    backup = package / (TABLE_FILENAME + ".stock")
    if target.exists() and not backup.exists():
        backup.write_text(target.read_text())
        logger.info("kept the engine's original class table at %s", backup)
    target.write_text(render_table(classes))
    logger.info("installed %d surface classes into %s", len(classes), target)
    return target


def is_installed(engine_bin: str) -> bool:
    package = engine_package_dir(engine_bin)
    table = package / TABLE_FILENAME
    return table.exists() and "Cool_roof" in table.read_text()
