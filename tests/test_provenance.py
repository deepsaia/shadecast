"""A bundle carries its urban centre and the citation of every layer. No network, no engine."""

import json
from pathlib import Path

from shadecast import build, repair, sources
from shadecast.cities import City
from shadecast.corpus import ucdb
from shadecast.dash import builder

AHMEDABAD = City(
    key="ahmedabad",
    ucdb_id=6143,
    name="Ahmedabad",
    country="India",
    lat=23.0192,
    lon=72.5988,
    koppen="BSh",
    income="LM",
    region="South Asia",
    population=7898650,
    tiles=365,
    note="First Heat Action Plan in South Asia, 2013.",
)


def _old_provenance(path: Path) -> Path:
    payload = {
        "schema": 1,
        "city": {"key": "ahmedabad", "name": "Ahmedabad", "country": "IND"},
        "aoi": {"lat": 23.0139, "lon": 72.5583, "side_m": 1000, "res_m": 1.0},
        "dem": {"source": "Copernicus DEM GLO-30 (AWS Open Data, unsigned)"},
        "met": {"source": "Open-Meteo ERA5 archive (no key)", "design_day": "2024-05-23"},
    }
    target = path / "provenance.json"
    target.write_text(json.dumps(payload))
    return target


def test_urban_centre_record_carries_strata_release_and_citation():
    record = build.urban_centre_record(AHMEDABAD)
    assert record["id"] == 6143
    assert record["release"] == f"{ucdb.RELEASE} {ucdb.VERSION}"
    assert record["name"] == "Ahmedabad"
    assert record["country"] == "India"
    assert record["population"] == 7898650
    assert record["area_km2"] == 365
    assert record["tiles"] == 365
    assert record["koppen"] == "BSh"
    assert record["income"] == "LM"
    assert record["source_key"] == ucdb.SOURCE
    assert record["citation"] == sources.citation(ucdb.SOURCE)


def test_backfill_provenance_adds_the_urban_centre_and_layer_citations(tmp_path):
    target = _old_provenance(tmp_path)
    assert repair.backfill_provenance(tmp_path, AHMEDABAD) == ["urban_centre", "dem", "met"]
    payload = json.loads(target.read_text())
    assert payload["urban_centre"]["id"] == 6143
    assert payload["dem"]["source_key"] == "copernicus_dem"
    assert payload["dem"]["source"] == sources.short("copernicus_dem")
    assert payload["met"]["citation"] == sources.citation("open_meteo_era5")
    assert payload["met"]["design_day"] == "2024-05-23"


def test_backfill_provenance_is_idempotent(tmp_path):
    _old_provenance(tmp_path)
    repair.backfill_provenance(tmp_path, AHMEDABAD)
    assert repair.backfill_provenance(tmp_path, AHMEDABAD) == []


def test_dash_summarises_the_urban_centre_when_present():
    provenance = {"urban_centre": build.urban_centre_record(AHMEDABAD)}
    summary = builder.urban_centre_summary(provenance)
    assert summary == {
        "id": 6143,
        "name": "Ahmedabad",
        "koppen": "BSh",
        "income": "LM",
        "population": 7898650,
        "tiles": 365,
    }


def test_dash_summary_is_none_for_a_bundle_that_predates_the_database():
    assert builder.urban_centre_summary({"city": {"key": "ahmedabad"}}) is None
