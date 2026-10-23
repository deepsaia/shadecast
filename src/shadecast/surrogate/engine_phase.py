"""Which phase an engine run is in, read from the files it has written so far.

The engine prints nothing per pixel or per hour and writes its output stack once at the end,
so time within a run cannot be observed. Its phases can: it prepares the input rasters, then
computes the sky view factor into one folder, then runs the radiation for every hour in
memory, then writes the output rasters. Each step leaves files, so the phase is exact.
"""

from __future__ import annotations

from pathlib import Path

PHASES = ("inputs", "sky view", "radiation", "outputs")


def design_phase(target: Path) -> int:
    """Index into PHASES for a design directory the engine is working in."""
    target = Path(target)
    outputs = target / "output_folder"
    if outputs.is_dir() and any(outputs.rglob("*.tif")):
        return 3
    svf = target / "processed_inputs" / "SVF"
    if svf.is_dir() and any(svf.iterdir()):
        return 2
    if (target / "processed_inputs").is_dir():
        return 1
    return 0


def phase_bar(phase: int) -> str:
    """The four phases as a row, the current and finished ones lit: inputs ▰ sky view ▰ ..."""
    parts = []
    for index, name in enumerate(PHASES):
        mark = "▰" if index <= phase else "▱"
        parts.append(f"{mark} {name}")
    return "  ".join(parts)
