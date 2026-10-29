"""The selected cities resolve by key without the database, and to records only when asked."""

from support.fixtures import fixture_centres
from support.fixtures import fixture_corpus

from shadecast import cities
from shadecast.corpus.urban_centres import UrbanCentres
from shadecast.service.selection import Selection


def _no_database() -> UrbanCentres:
    raise AssertionError("the database was loaded for a key")


def test_the_selection_file_answers_keys_without_the_database():
    selection = Selection.read()
    assert selection.ucdb_id("ahmedabad") == 6143
    assert selection.ucdb_id("atlantis") is None
    keys = selection.keys()
    assert "ahmedabad" in keys


def test_a_resolved_selection_answers_records_without_the_database():
    selection = Selection.resolved(fixture_corpus())
    assert selection.ucdb_id("london") == 5816
    listed = selection.cities(_no_database)
    assert [city.key for city in listed.values()] == ["ahmedabad", "london"]


def test_a_read_selection_resolves_records_through_the_corpus(monkeypatch):
    seen: dict = {}

    def corpus(entries=None, centres=None):
        seen["entries"] = len(entries)
        seen["centres"] = centres
        return fixture_corpus()

    monkeypatch.setattr(cities, "corpus", corpus)
    listed = Selection.read().cities(fixture_centres)
    assert set(listed) == {"ahmedabad", "london"}
    assert seen["entries"] > 0 and seen["centres"] is not None
