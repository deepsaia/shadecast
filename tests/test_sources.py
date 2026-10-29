"""The cited sources registry. Every source the code reads is cited once, here."""

import json

import pytest

from shadecast import build
from shadecast import sources
from shadecast import validation
from shadecast.corpus import ucdb
from shadecast.data import buildings
from shadecast.data import built
from shadecast.data import canopy
from shadecast.data import met
from shadecast.data import population
from shadecast.data import rasters
from shadecast.data import regions
from shadecast.network import graph
from shadecast.sim import runner

DATA_GROUP = "data"


def test_registry_validates_and_has_unique_keys():
    registry = sources.registry()
    keys = [entry["key"] for entry in registry["sources"]]
    assert len(keys) == len(set(keys))
    assert len(keys) >= 25
    group_keys = {group["key"] for group in registry["groups"]}
    for entry in registry["sources"]:
        assert entry["group"] in group_keys, entry["key"]
        for field in sources.REQUIRED_FIELDS:
            assert entry.get(field), (entry["key"], field)
        assert entry.get("access") in (None, *sources.ACCESS_KINDS), entry["key"]


def test_every_data_source_is_anonymous_except_landsat():
    for entry in sources.registry()["sources"]:
        if entry["group"] == DATA_GROUP:
            assert entry["access"] == "anonymous", entry["key"]
    assert sources.source("landsat_c2l2")["access"] == "token broker"


@pytest.mark.parametrize(
    "key",
    [
        buildings.SOURCE,
        canopy.SOURCE,
        rasters.DEM_SOURCE,
        rasters.WORLDCOVER_SOURCE,
        population.SOURCE,
        built.SURFACE_SOURCE,
        built.HEIGHT_SOURCE,
        met.SOURCE,
        regions.SOURCE,
        graph.SOURCE,
        validation.SOURCE,
        runner.SOURCE,
        ucdb.SOURCE,
    ],
)
def test_every_module_names_a_source_the_registry_knows(key):
    assert sources.source(key)["key"] == key


def test_every_data_entry_is_named_by_a_module():
    named = {
        buildings.SOURCE,
        canopy.SOURCE,
        rasters.DEM_SOURCE,
        rasters.WORLDCOVER_SOURCE,
        population.SOURCE,
        built.SURFACE_SOURCE,
        built.HEIGHT_SOURCE,
        met.SOURCE,
        regions.SOURCE,
        graph.SOURCE,
        ucdb.SOURCE,
    }
    data_keys = {e["key"] for e in sources.registry()["sources"] if e["group"] == DATA_GROUP}
    unnamed = data_keys - named
    # Sources reached through another source carry the key of the one that reaches them.
    assert unnamed <= {e["key"] for e in sources.registry()["sources"] if e.get("via")}


def test_citation_is_one_line_with_title_publisher_release_and_licence():
    line = sources.citation("ghs_ucdb")
    assert "\n" not in line
    assert "Urban Centre Database" in line
    assert "R2024A V1_2" in line
    assert "CC BY 4.0" in line


def test_short_name_is_what_a_provenance_chip_shows():
    assert sources.short("copernicus_dem") == "Copernicus DEM GLO-30, AWS Open Data"


def test_unknown_key_is_an_error_naming_it():
    with pytest.raises(KeyError, match="atlantis_lidar"):
        sources.source("atlantis_lidar")


def test_grouped_keeps_registry_group_order_and_only_non_empty_groups():
    grouped = sources.grouped()
    assert [group["key"] for group in grouped] == [group["key"] for group in sources.registry()["groups"]]
    assert all(group["sources"] for group in grouped)
    assert grouped[0]["title"]


def test_a_broken_registry_is_refused_naming_the_file(tmp_path):
    path = tmp_path / "cited_sources.json"
    path.write_text(json.dumps({"groups": [{"key": "data", "title": "Data"}], "sources": [{"key": "x"}]}))
    with pytest.raises(ValueError, match=r"cited_sources\.json.*x"):
        sources.registry(path)


def test_build_records_source_key_and_citation_for_every_layer():
    assert build.LAYER_SOURCES == {
        "dem": rasters.DEM_SOURCE,
        "buildings": buildings.SOURCE,
        "canopy": canopy.SOURCE,
        "landcover": rasters.WORLDCOVER_SOURCE,
        "population": population.SOURCE,
        "met": met.SOURCE,
    }
    record = build.source_record(met.SOURCE)
    assert record["source_key"] == met.SOURCE
    assert record["source"] == sources.short(met.SOURCE)
    assert record["citation"] == sources.citation(met.SOURCE)
