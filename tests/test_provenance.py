"""A bundle carries its urban centre and the citation of every layer. No network, no engine."""

from shadecast import build, sources
from shadecast.cities import City
from shadecast.corpus import ucdb
from shadecast.service.tile_facts import facts_from
from shadecast.service.urban_centre_facts import UrbanCentreFacts

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
    population_2025=7898650,
    tiles=365,
    note="First Heat Action Plan in South Asia, 2013.",
)


def test_urban_centre_record_carries_strata_release_and_citation():
    record = build.urban_centre_record(AHMEDABAD)
    assert record["id"] == 6143
    assert record["release"] == f"{ucdb.RELEASE} {ucdb.VERSION}"
    assert record["name"] == "Ahmedabad"
    assert record["country"] == "India"
    assert record["population_2025"] == 7898650
    assert record["area_km2"] == 365
    assert record["tiles"] == 365
    assert record["koppen"] == "BSh"
    assert record["income"] == "LM"
    assert record["source_key"] == ucdb.SOURCE
    assert record["citation"] == sources.citation(ucdb.SOURCE)


def test_the_tile_facts_carry_the_urban_centre_when_present():
    provenance = {"urban_centre": build.urban_centre_record(AHMEDABAD)}
    assert facts_from(provenance, "ahmedabad").urban_centre == UrbanCentreFacts(
        id=6143,
        name="Ahmedabad",
        koppen="BSh",
        income="LM",
        population_2025=7898650,
        tiles=365,
    )


def test_the_tile_facts_have_no_centre_for_a_bundle_that_predates_the_database():
    assert facts_from({"city": {"key": "ahmedabad"}}, "ahmedabad").urban_centre is None
