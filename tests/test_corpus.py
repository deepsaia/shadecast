"""The city corpus is data, read from corpus.json. No network, no engine."""

import json

import pytest

from shadecast.cities import CORPUS, CORPUS_PATH, City, load_corpus, summary

INCOME_GROUPS = {"L", "LM", "UM", "H"}
NEW_CITIES = ("savannah", "oaxaca", "recife", "bristol", "barcelona", "hamburg")


def test_corpus_is_read_from_the_json_file():
    assert CORPUS_PATH.name == "corpus.json"
    assert load_corpus(CORPUS_PATH) == CORPUS


def test_corpus_holds_the_expanded_city_set():
    assert len(CORPUS) == 38
    for key in NEW_CITIES:
        assert key in CORPUS, key


def test_every_entry_is_a_city_with_valid_strata():
    for key, city in CORPUS.items():
        assert isinstance(city, City)
        assert city.key == key
        assert -90 <= city.lat <= 90, key
        assert -180 <= city.lon <= 180, key
        assert city.income in INCOME_GROUPS, key
        assert city.koppen[0] in "ABCDE", key
        assert len(city.country) == 3, key


def test_keys_are_unique_in_the_file():
    entries = json.loads(CORPUS_PATH.read_text())
    keys = [entry["key"] for entry in entries]
    assert len(keys) == len(set(keys))


def test_unknown_field_names_the_file_and_the_key(tmp_path):
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps([{"key": "x", "name": "X", "colour": "red"}]))
    with pytest.raises(ValueError, match=r"corpus\.json.*x"):
        load_corpus(path)


def test_duplicate_key_is_rejected(tmp_path):
    entry = {
        "key": "x",
        "name": "X",
        "country": "XXX",
        "lat": 0.0,
        "lon": 0.0,
        "koppen": "Af",
        "income": "H",
        "region": "Nowhere",
    }
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps([entry, entry]))
    with pytest.raises(ValueError, match="duplicate"):
        load_corpus(path)


def test_summary_counts_the_expanded_corpus():
    stats = summary()
    assert stats["cities"] == 38
    assert stats["wri_overlap"] == 6
