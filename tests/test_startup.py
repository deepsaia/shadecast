"""The command line answers --help before any heavy library loads; those take seconds, help takes none.

Both checks start a fresh interpreter, since the test process has already imported everything. The
list of libraries is the real guard; the timing bound is loose so continuous integration passes it.
"""

import subprocess
import sys
import time

HEAVY = (
    "torch",
    "numpy",
    "pandas",
    "geopandas",
    "rasterio",
    "osmnx",
    "matplotlib",
    "scipy",
    "duckdb",
    "networkx",
    "shapely",
    "pyproj",
    "fastapi",
    "uvicorn",
    "skimage",
    "PIL",
    "requests",
)
LOADED = "import sys; import shadecast.cli; print(' '.join(sorted({name.split('.')[0] for name in sys.modules})))"
HELP = "import sys; from shadecast.cli import entry; sys.argv = ['sdc', '--help']; raise SystemExit(entry())"
GENEROUS_SECONDS = 1.0


def _python(code: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)


def test_importing_the_command_line_loads_no_heavy_library():
    loaded = set(_python(LOADED).stdout.split())
    assert "typer" in loaded
    assert not loaded & set(HEAVY), sorted(loaded & set(HEAVY))


def test_help_answers_within_a_second():
    _python(HELP)  # the first run may compile bytecode; the second is what a user sees
    started = time.perf_counter()
    completed = _python(HELP)
    elapsed = time.perf_counter() - started
    assert elapsed < GENEROUS_SECONDS, f"--help took {elapsed:.2f} s"
    for group in ("build", "simulate", "surrogate", "serve"):
        assert group in completed.stdout
