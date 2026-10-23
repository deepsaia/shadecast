"""Standalone pages ship with the walkthrough bundle, copied as they are from the package."""

from pathlib import Path

from typer.testing import CliRunner

from shadecast import dash_cli
from shadecast.cli import app

SOURCE = Path(dash_cli.__file__).parent / "dash"
runner = CliRunner()


def test_publish_pages_copies_every_page(tmp_path):
    written = dash_cli.publish_pages(tmp_path)
    assert [path.name for path in written] == list(dash_cli.PAGES)
    for path in written:
        assert path.read_text() == (SOURCE / path.name).read_text()


def test_model_pipeline_page_is_self_contained():
    page = (SOURCE / "model_pipeline.html").read_text()
    assert "<title>" in page
    assert chr(0x2014) not in page, "no em-dashes anywhere in this project"
    assert "<script src=" not in page
    assert '<link rel="stylesheet"' not in page


def test_the_walkthrough_links_the_other_pages_in_new_tabs():
    page = (SOURCE / "app.html").read_text()
    for target in ("result.html", "model_pipeline.html", "proposal.html"):
        assert f'href="{target}" target="_blank" rel="noopener"' in page


def test_pages_command_writes_the_shell_and_every_page_without_data(tmp_path):
    result = runner.invoke(app, ["dash", "pages", "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "index.html").exists() and (tmp_path / "app.js").exists()
    for name in dash_cli.PAGES:
        assert (tmp_path / name).exists()
    assert 'src="app.js?v=' in (tmp_path / "index.html").read_text()
