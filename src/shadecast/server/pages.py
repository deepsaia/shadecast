"""The hand-written pages, served from the package at /pages as GitHub Pages serves them."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

PAGES_DIR = Path(__file__).parent.parent / "pages"
PREFIX = "/pages"


def mount(app: FastAPI) -> None:
    app.mount(PREFIX, StaticFiles(directory=PAGES_DIR, html=True), name="pages")
