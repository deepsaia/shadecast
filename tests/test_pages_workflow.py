"""GitHub Pages publishes the package's pages directory, and refuses to publish it incomplete."""

from pathlib import Path

from shadecast.server import pages

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "pages.yml"


def test_the_workflow_uploads_the_pages_directory():
    assert "path: src/shadecast/pages" in WORKFLOW.read_text()


def test_the_workflow_checks_every_file_it_publishes():
    text = WORKFLOW.read_text()
    for name in ("index.html", ".nojekyll", *pages.PAGES):
        assert f"src/shadecast/pages/{name}" in text, name
