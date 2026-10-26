"""A derived payload is served while its sources are unchanged and rebuilt when one moves."""

import os

import pytest

from shadecast.service.derived_cache import DerivedCache


def _source(root, name: str, text: str = "x"):
    path = root / name
    path.write_text(text)
    return path


def test_a_written_payload_is_current_and_reads_back(tmp_path):
    source = _source(tmp_path, "a.json")
    cache = DerivedCache(tmp_path / "derived")
    cache.write("report", {"plans": 3}, [source])
    assert cache.current("report", [source]) is True
    assert cache.read("report") == {"plans": 3}


def test_a_touched_source_makes_the_payload_stale(tmp_path):
    source = _source(tmp_path, "a.json")
    cache = DerivedCache(tmp_path / "derived")
    cache.write("report", {"plans": 3}, [source])
    later = source.stat().st_mtime_ns + 1_000_000
    os.utime(source, ns=(later, later))
    assert cache.current("report", [source]) is False


def test_a_source_that_appears_later_makes_the_payload_stale(tmp_path):
    present = _source(tmp_path, "a.json")
    absent = tmp_path / "b.json"
    cache = DerivedCache(tmp_path / "derived")
    cache.write("report", {}, [present, absent])
    assert cache.current("report", [present, absent]) is True
    _source(tmp_path, "b.json")
    assert cache.current("report", [present, absent]) is False


def test_nothing_written_is_neither_current_nor_readable(tmp_path):
    cache = DerivedCache(tmp_path / "derived")
    assert cache.current("report", []) is False
    with pytest.raises(LookupError, match="report"):
        cache.read("report")
