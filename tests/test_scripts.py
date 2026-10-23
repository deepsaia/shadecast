"""The short alias runs the same command line as the full name."""

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_sdc_is_an_alias_of_shadecast():
    scripts = tomllib.loads(PYPROJECT.read_text())["project"]["scripts"]
    assert scripts["sdc"] == scripts["shadecast"] == "shadecast.cli:entry"
