"""The benchmark corpus is a selection of urban centre ids joined to the database. No network."""

import json
from pathlib import Path

import pandas as pd
import pytest

from shadecast import cities
from shadecast.cities import SELECTION_PATH, City, corpus, selection, summary
from shadecast.corpus.urban_centres import UrbanCentres

COLUMNS = (
    "ID_UC_G0",
    "GC_UCN_MAI_2025",
    "GC_UCN_LIS_2025",
    "GC_CNT_GAD_2025",
    "GC_UCA_KM2_2025",
    "GC_POP_TOT_2025",
    "GC_DEV_WIG_2025",
    "CL_KOP_CUR_2025",
    "lon",
    "lat",
)
ROWS = [
    (
        6143,
        "Ahmedabad",
        "Ahmedabad; Amdavad",
        "India",
        365,
        7898649.8,
        "Lower Middle",
        "6",
        72.5988,
        23.0192,
    ),
    (
        7799,
        "Rio de Janeiro",
        "Rio de Janeiro",
        "Brazil",
        1285,
        9853692.0,
        "Upper Middle",
        "3",
        -43.2,
        -22.9,
    ),
    (5816, "London", "London", "United Kingdom", 1649, 10408332.0, "High income", "15", -0.1, 51.5),
    (
        3570,
        "Dar es-Salaam",
        "Dar es-Salaam",
        "Tanzania",
        907,
        8918524.0,
        "Lower Middle",
        "-",
        39.2,
        -6.8,
    ),
]
SELECTED = [
    {
        "ucdb_id": 6143,
        "key": "ahmedabad",
        "region": "South Asia",
        "note": "First Heat Action Plan.",
    },
    {"ucdb_id": 7799, "key": "rio", "region": "LatAm", "in_wri": True},
    {"ucdb_id": 5816, "key": "london", "region": "Europe", "in_wri": True},
    {"ucdb_id": 3570, "key": "daressalaam", "region": "Africa"},
]


def _centres() -> UrbanCentres:
    return UrbanCentres(pd.DataFrame(ROWS, columns=COLUMNS))


def _write(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(entries))
    return path


def test_the_selection_file_holds_ids_and_our_own_fields_only():
    entries = json.loads(SELECTION_PATH.read_text())
    assert len(entries) == 38
    allowed = {"ucdb_id", "key", "region", "in_wri", "note"}
    for entry in entries:
        assert set(entry) <= allowed, entry.get("key")
        assert isinstance(entry.get("ucdb_id"), int), entry.get("key")
        assert entry.get("key") and entry.get("region"), entry.get("ucdb_id")
    assert len({e["ucdb_id"] for e in entries}) == 38
    assert len({e["key"] for e in entries}) == 38


def test_selection_rejects_a_typed_stratum_naming_the_file_and_key(tmp_path):
    path = _write(tmp_path, [{"ucdb_id": 1, "key": "x", "region": "Nowhere", "koppen": "Aw"}])
    with pytest.raises(ValueError, match=r"corpus\.json.*x.*koppen"):
        selection(path)


def test_selection_rejects_duplicate_keys_and_ids(tmp_path):
    entry = {"ucdb_id": 1, "key": "x", "region": "Nowhere"}
    with pytest.raises(ValueError, match="duplicate"):
        selection(_write(tmp_path, [entry, entry]))


def test_corpus_joins_the_selection_to_the_database():
    cities_by_key = corpus(SELECTED, _centres())
    assert list(cities_by_key) == ["ahmedabad", "rio", "london", "daressalaam"]
    city = cities_by_key["ahmedabad"]
    assert isinstance(city, City)
    assert city.ucdb_id == 6143
    assert city.name == "Ahmedabad"
    assert city.country == "India"
    assert city.koppen == "BSh"
    assert city.income == "LM"
    assert city.region == "South Asia"
    assert city.population == 7898650
    assert city.tiles == 365
    assert city.lat == pytest.approx(23.0192)
    assert city.note == "First Heat Action Plan."
    assert cities_by_key["rio"].in_wri and not city.in_wri
    assert city.global_south and not cities_by_key["london"].global_south


def test_corpus_keeps_a_missing_stratum_as_none():
    assert corpus(SELECTED, _centres())["daressalaam"].koppen is None


def test_corpus_refuses_an_id_the_database_lacks():
    with pytest.raises(KeyError, match=r"atlantis.*4242"):
        corpus([{"ucdb_id": 4242, "key": "atlantis", "region": "Sea"}], _centres())


def test_summary_counts_strata_from_database_fields():
    stats = summary(corpus(SELECTED, _centres()).values())
    assert stats["cities"] == 4
    assert stats["global_south"].startswith("3 ")
    assert stats["tropical_A"].startswith("1 ")
    assert stats["arid_B"].startswith("1 ")
    assert stats["southern_hemisphere"] == 2
    assert stats["wri_overlap"] == 2
    assert stats["regions"] == 4


def test_corpus_loads_the_database_when_no_centres_are_given(monkeypatch, tmp_path):
    monkeypatch.setattr(cities, "urban_centres", _centres)
    assert len(corpus(SELECTED)) == 4
