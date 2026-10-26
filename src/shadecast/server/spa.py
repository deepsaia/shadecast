"""Serve the built client: its assets, the index for every page route, a plain answer when unbuilt.

Registered last, after every API route, so an unknown ``/api/`` path is a 404 and never the index.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

API = "api/"
NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>shadecast</title>
<body style="font-family: system-ui; max-width: 40rem; margin: 4rem auto; line-height: 1.5">
<h1>The client is not built</h1>
<p>The API is up at <a href="/api/docs">/api/docs</a>. To serve the dashboard, build the client
once:</p>
<pre>make frontend</pre>
<p>then start the server again.</p></body>"""


def mount(app: FastAPI, static_dir: Path) -> None:
    assets = Path(static_dir) / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    app.add_api_route(
        "/{path:path}", SpaFallback(Path(static_dir)), methods=["GET"], include_in_schema=False
    )


class SpaFallback:
    """Answers every path no route claimed: a root file, the index, or the unbuilt page."""

    def __init__(self, static_dir: Path) -> None:
        self._static_dir = static_dir

    async def __call__(self, path: str) -> Response:
        if path.startswith(API):
            return JSONResponse(status_code=404, content={"error": f"no route /{path}"})
        index = self._static_dir / "index.html"
        if not index.exists():
            return HTMLResponse(NOT_BUILT, status_code=503)
        root_file = self._root_file(path)
        if root_file is not None:
            return FileResponse(root_file)
        return HTMLResponse(index.read_text(), headers={"Cache-Control": "no-store"})

    def _root_file(self, path: str) -> Path | None:
        """A file at the client's root, such as a favicon; never anything outside it."""
        if not path or path == "index.html":
            return None
        root = self._static_dir.resolve()
        candidate = (root / path).resolve()
        if candidate.parent != root or not candidate.is_file():
            return None
        return candidate
