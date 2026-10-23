"""One registry for every source the code reads or the documents cite.

The walkthrough, the README, the proposal and the module docstrings each used to carry their
own copy of the bibliography, and the copies drifted. ``cited_sources.json`` beside this module
is the only place a citation is typed. Data modules name their source by key, provenance
records the key and the citation line beside each layer, and the walkthrough renders its
references section from the same file. A source that is reached through another, such as the
Koppen maps through the urban centre database, says so with ``via``.
"""

from __future__ import annotations

import json
from pathlib import Path

REGISTRY_PATH = Path(__file__).with_name("cited_sources.json")
REQUIRED_FIELDS = ("key", "group", "title", "authors_or_publisher", "used_for")
ACCESS_KINDS = ("anonymous", "token broker", "account")


def _check_entry(entry: dict, group_keys: set[str], path: Path) -> None:
    key = entry.get("key", "?")
    for field in REQUIRED_FIELDS:
        if not entry.get(field):
            raise ValueError(f"{path.name}: source {key!r} lacks {field!r}")
    if entry.get("group") not in group_keys:
        raise ValueError(f"{path.name}: source {key!r} names unknown group {entry.get('group')!r}")
    access = entry.get("access")
    if access is not None and access not in ACCESS_KINDS:
        raise ValueError(
            f"{path.name}: source {key!r} has access {access!r}, not in {ACCESS_KINDS}"
        )


def registry(path: Path = REGISTRY_PATH) -> dict:
    """Read and validate the registry: ordered groups and uniquely keyed sources."""
    path = Path(path)
    payload: dict = json.loads(path.read_text())
    groups: list[dict] = payload.get("groups", [])
    entries: list[dict] = payload.get("sources", [])
    group_keys = {str(group.get("key")) for group in groups}
    if not groups or not entries:
        raise ValueError(f"{path.name}: registry needs both groups and sources")
    seen: set[str] = set()
    for entry in entries:
        _check_entry(entry, group_keys, path)
        key = str(entry.get("key"))
        if key in seen:
            raise ValueError(f"{path.name}: duplicate source key {key!r}")
        seen.add(key)
    for entry in entries:
        via = entry.get("via")
        if via is not None and via not in seen:
            raise ValueError(f"{path.name}: source {entry.get('key')!r} is via unknown {via!r}")
    return payload


def sources(path: Path = REGISTRY_PATH) -> dict[str, dict]:
    """Every source keyed by its registry key, in registry order."""
    return {str(entry.get("key")): entry for entry in registry(path).get("sources", [])}


def source(key: str, path: Path = REGISTRY_PATH) -> dict:
    entry = sources(path).get(key)
    if entry is None:
        raise KeyError(f"no cited source {key!r} in {Path(path).name}")
    return entry


def short(key: str, path: Path = REGISTRY_PATH) -> str:
    """The short name a provenance chip or a table cell shows."""
    entry = source(key, path)
    return str(entry.get("short") or entry.get("title"))


def citation(key: str, path: Path = REGISTRY_PATH) -> str:
    """One line: title, who and when, release, licence, and where to find it."""
    entry = source(key, path)
    who = str(entry.get("authors_or_publisher"))
    year = entry.get("year")
    parts = [f"{entry.get('title')}.", f"{who}, {year}." if year else f"{who}."]
    for field in ("release", "licence"):
        value = entry.get(field)
        if value:
            parts.append(f"{value}.")
    doi = entry.get("doi")
    locator = f"https://doi.org/{doi}" if doi else entry.get("url")
    if locator:
        parts.append(str(locator))
    return " ".join(parts)


def grouped(path: Path = REGISTRY_PATH) -> list[dict]:
    """Sources in their groups, in registry order, for rendering a references section."""
    payload = registry(path)
    entries: list[dict] = payload.get("sources", [])
    out: list[dict] = []
    for group in payload.get("groups", []):
        members = [entry for entry in entries if entry.get("group") == group.get("key")]
        if members:
            out.append({"key": group.get("key"), "title": group.get("title"), "sources": members})
    return out
