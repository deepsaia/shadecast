"""Standalone pages ship with the walkthrough bundle, copied as they are from the package."""

from pathlib import Path

from shadecast import dash_cli

SOURCE = Path(dash_cli.__file__).parent / "dash"


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
