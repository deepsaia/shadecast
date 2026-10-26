"""Read a JSON file that may be absent or half-written, answering nothing rather than failing."""

from __future__ import annotations

import json
from pathlib import Path


def read_json(path: Path) -> dict | list | None:
    """The file's payload, or None when it is absent or not yet valid JSON."""
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return None


def read_object(path: Path) -> dict:
    """The file's payload when it is a JSON object, else an empty one."""
    payload = read_json(path)
    return payload if isinstance(payload, dict) else {}
