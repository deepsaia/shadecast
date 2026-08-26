"""Structured logging configuration for the command line and library.

Output goes to stderr so that machine-readable results written to stdout stay
clean and pipeable, which matters for a benchmark whose results get aggregated.
"""

from __future__ import annotations

import logging
import sys

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
DATE_FORMAT = "%H:%M:%S"


def configure(verbose: bool = False) -> None:
    """Install a single stderr handler at the requested level."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(FORMAT, datefmt=DATE_FORMAT))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    # These libraries are chatty at INFO and drown the signal.
    for noisy in ("rasterio", "urllib3", "botocore", "fiona", "matplotlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
