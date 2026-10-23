"""Refuse a downloaded file whose bytes are not the ones the code was written against."""

from __future__ import annotations

import hashlib
from pathlib import Path

CHUNK_BYTES = 1 << 20


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        chunk = handle.read(CHUNK_BYTES)
        while chunk:
            digest.update(chunk)
            chunk = handle.read(CHUNK_BYTES)
    return digest.hexdigest()


def verify(path: Path, expected: str) -> None:
    """Raise, naming the file, when its digest is not the recorded one."""
    actual = sha256(path)
    if actual != expected:
        raise ValueError(
            f"{Path(path).name} does not match its recorded checksum "
            f"(expected {expected[:12]}..., got {actual[:12]}...); delete it and fetch again"
        )
