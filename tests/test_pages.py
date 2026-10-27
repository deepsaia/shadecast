"""The hand-written pages live in the package and GitHub Pages publishes them as they are."""

from shadecast.server import pages


def test_the_landing_and_pipeline_pages_are_self_contained():
    for name in ("index.html", "model_pipeline.html"):
        page = (pages.PAGES_DIR / name).read_text()
        assert "<title>" in page, name
        assert "<script src=" not in page, name
        assert '<link rel="stylesheet"' not in page, name


def test_no_page_carries_an_em_dash():
    for path in pages.PAGES_DIR.glob("*.html"):
        assert chr(0x2014) not in path.read_text(), (
            f"{path.name}: no em-dashes anywhere in this project"
        )


def test_the_landing_page_links_the_pages_and_the_repository():
    page = (pages.PAGES_DIR / "index.html").read_text()
    for target in pages.PAGES:
        assert f'href="{target}"' in page
    assert 'href="https://github.com/deepsaia/shadecast"' in page


def test_the_landing_page_tells_how_to_run_the_dashboard():
    page = (pages.PAGES_DIR / "index.html").read_text()
    assert "sdc serve" in page and "sdc dash" not in page


def test_the_pages_directory_publishes_without_jekyll():
    assert (pages.PAGES_DIR / ".nojekyll").exists()
