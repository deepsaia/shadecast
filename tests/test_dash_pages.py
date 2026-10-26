"""The hand-written pages live in the package and ship with the walkthrough bundle unchanged."""

from pathlib import Path

from typer.testing import CliRunner

from shadecast import dash_cli
from shadecast.cli import app

DASH = Path(dash_cli.__file__).parent / "dash"
PAGES = Path(dash_cli.__file__).parent / "pages"
runner = CliRunner()


def test_publish_pages_copies_the_result_files_and_every_page(tmp_path):
    written = dash_cli.publish_pages(tmp_path)
    assert [path.name for path in written] == [*dash_cli.RESULT_FILES, *dash_cli.PAGES]
    for name in dash_cli.RESULT_FILES:
        assert (tmp_path / name).read_text() == (DASH / name).read_text()
    for name in dash_cli.PAGES:
        assert (tmp_path / name).read_text() == (PAGES / name).read_text()


def test_the_landing_and_pipeline_pages_are_self_contained():
    for name in ("index.html", "model_pipeline.html"):
        page = (PAGES / name).read_text()
        assert "<title>" in page, name
        assert "<script src=" not in page, name
        assert '<link rel="stylesheet"' not in page, name


def test_no_page_carries_an_em_dash():
    for path in PAGES.glob("*.html"):
        assert chr(0x2014) not in path.read_text(), (
            f"{path.name}: no em-dashes anywhere in this project"
        )


def test_the_landing_page_links_the_pages_and_the_repository():
    page = (PAGES / "index.html").read_text()
    for target in dash_cli.PAGES:
        assert f'href="{target}"' in page
    assert 'href="https://github.com/deepsaia/shadecast"' in page


def test_the_pages_directory_publishes_without_jekyll():
    assert (PAGES / ".nojekyll").exists()


def test_the_walkthrough_links_the_other_pages_in_new_tabs():
    page = (DASH / "app.html").read_text()
    for target in ("result.html", "model_pipeline.html", "proposal.html"):
        assert f'href="{target}" target="_blank" rel="noopener"' in page


def test_pages_command_writes_the_shell_and_every_page_without_data(tmp_path):
    result = runner.invoke(app, ["dash", "pages", "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "index.html").exists() and (tmp_path / "app.js").exists()
    for name in (*dash_cli.RESULT_FILES, *dash_cli.PAGES):
        assert (tmp_path / name).exists()
    assert 'src="app.js?v=' in (tmp_path / "index.html").read_text()
