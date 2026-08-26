"""Serve the dashboard bundle over plain HTTP.

Deliberately the standard library and nothing else. The dashboard is static files,
so a web framework would add a dependency, a build step and a security surface for
no benefit. This also means the built bundle can be zipped, archived or served by
any web server, which matters for reproducing a paper years later.
"""

from __future__ import annotations

import logging
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

logger = logging.getLogger(__name__)


class QuietHandler(SimpleHTTPRequestHandler):
    """Static handler that does not narrate every asset fetch to the console."""

    def log_message(self, format: str, *args: object) -> None:
        logger.debug("%s %s", self.address_string(), format % args)

    def end_headers(self) -> None:
        # The bundle is rebuilt in place, so a cached index would show stale results.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve(directory: Path, port: int = 8765, open_browser: bool = True) -> None:
    """Serve `directory` until interrupted."""
    handler = partial(QuietHandler, directory=str(directory))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        url = f"http://127.0.0.1:{port}/"
        logger.info("serving %s at %s", directory, url)
        if open_browser:
            threading.Timer(0.5, webbrowser.open, args=(url,)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("stopped")
