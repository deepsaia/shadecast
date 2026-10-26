"""A wheel carries the built client, so an installed copy serves the dashboard without Node."""

import tomllib
from pathlib import Path

from shadecast.server.settings import STATIC_DIR

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
WORKFLOW = ROOT / ".github" / "workflows" / "frontend.yml"


def test_the_wheel_names_the_ignored_static_directory_as_an_artifact():
    wheel = tomllib.loads(PYPROJECT.read_text())["tool"]["hatch"]["build"]["targets"]["wheel"]
    static = STATIC_DIR.relative_to(ROOT).as_posix()
    assert wheel.get("artifacts") == [f"{static}/**"]


def test_the_client_workflow_builds_the_wheel_and_checks_the_client_is_inside():
    text = WORKFLOW.read_text()
    assert "uv build --wheel" in text
    assert "shadecast/server/static/index.html" in text
