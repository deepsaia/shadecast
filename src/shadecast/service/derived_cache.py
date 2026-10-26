"""Named JSON payloads derived from a tile's files, stamped with the files they came from."""

from __future__ import annotations

import json
from pathlib import Path


class DerivedCache:
    """Keeps a derived payload beside its tile and knows whether its sources have moved since.

    The stamp is the modification time of every source, present or not: a source that appears
    later changes the stamp as surely as one that is rewritten. The cache file is never a source.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = Path(directory)

    def current(self, name: str, sources: list[Path]) -> bool:
        path = self._path(name)
        if not path.exists():
            return False
        return json.loads(path.read_text()).get("sources") == _stamp(sources)

    def read(self, name: str) -> dict:
        path = self._path(name)
        if not path.exists():
            raise LookupError(f"no derived {name!r} under {self._directory}")
        return json.loads(path.read_text()).get("payload", {})

    def write(self, name: str, payload: dict, sources: list[Path]) -> Path:
        path = self._path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"sources": _stamp(sources), "payload": payload}
        path.write_text(json.dumps(record, separators=(",", ":")))
        return path

    def _path(self, name: str) -> Path:
        return self._directory / f"{name}.json"


def _stamp(sources: list[Path]) -> dict[str, int]:
    return {str(path): path.stat().st_mtime_ns for path in sources if path.exists()}
