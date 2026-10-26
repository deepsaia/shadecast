"""The corpus command group. No network: the database is a nine-row fixture."""

import json

import pandas as pd
import pytest
from typer.testing import CliRunner

from shadecast import corpus_cli
from shadecast.cli import app
from shadecast.corpus import tile_paths
from shadecast.corpus.urban_centres import UrbanCentres

runner = CliRunner()

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
    "continent",
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
        72.6,
        23.0,
    ),
    (5816, "London", "London", "United Kingdom", 1649, 10408332.0, "High income", "15", -0.1, 51.5),
    (9001, "London", "London", "Canada", 150, 500000.0, "High income", "25", -81.2, 42.98),
    (9002, "San José", "San José", "Costa Rica", 300, 1500000.0, "Upper Middle", "3", -84.1, 9.93),
    (
        9003,
        "San Jose",
        "San Jose",
        "United States",
        400,
        1800000.0,
        "High income",
        "8",
        -121.9,
        37.3,
    ),
    (1289, "Lagos", "Lagos", "Nigeria", 1199, 12846045.0, "Lower Middle", "3", 3.3, 6.5),
    (3175, "Accra", "Accra", "Ghana", 1121, 5890466.0, "Lower Middle", "3", -0.2, 5.6),
    (4155, "Khartoum", "Khartoum", "Sudan", 958, 7114789.0, "Low income", "4", 32.6, 15.5),
    (
        9005,
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


CONTINENTS = [
    "Asia",
    "Europe",
    "North America",
    "North America",
    "North America",
    "Africa",
    "Africa",
    "Africa",
    "Africa",
]


def _fixture_centres() -> UrbanCentres:
    rows = [(*row, continent) for row, continent in zip(ROWS, CONTINENTS, strict=True)]
    return UrbanCentres(pd.DataFrame(rows, columns=COLUMNS))


@pytest.fixture(autouse=True)
def _offline_database(monkeypatch, tmp_path):
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setattr(corpus_cli, "load_centres", _fixture_centres)
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)


def test_help_lists_the_corpus_commands():
    result = runner.invoke(app, ["corpus", "--help"])
    assert result.exit_code == 0
    for command in ("search", "show", "sample", "stats"):
        assert command in result.stdout


def test_search_lists_matches_most_populous_first():
    result = runner.invoke(app, ["corpus", "search", "london", "--json"])
    assert result.exit_code == 0
    rows = json.loads(result.stdout)
    assert [row["id"] for row in rows] == [5816, 9001]
    assert rows[0]["slug"] == "london" and rows[0]["koppen"] == "Cfb"


def test_search_filters_by_country_and_population():
    result = runner.invoke(
        app,
        [
            "corpus",
            "search",
            "",
            "--country",
            "United States",
            "--min-population",
            "1000000",
            "--json",
        ],
    )
    assert [row["id"] for row in json.loads(result.stdout)] == [9003]


def test_show_prints_one_centre_with_its_tile_count():
    result = runner.invoke(app, ["corpus", "show", "ahmedabad", "--json"])
    assert result.exit_code == 0
    centre = json.loads(result.stdout)
    assert centre["id"] == 6143
    assert centre["tiles"] == 365
    assert centre["income"] == "LM"
    table = runner.invoke(app, ["corpus", "show", "6143"])
    assert "Ahmedabad" in table.stdout and "365" in table.stdout


def test_show_refuses_an_ambiguous_name_and_names_the_candidates():
    result = runner.invoke(app, ["corpus", "show", "san"])
    assert result.exit_code == 1
    assert "sanjose" in result.output and "sanjose-costarica" in result.output


def test_sample_is_stratified_and_reproducible():
    args = [
        "corpus",
        "sample",
        "--per-stratum",
        "1",
        "--min-population",
        "600000",
        "--seed",
        "7",
        "--json",
    ]
    first = json.loads(runner.invoke(app, args).stdout)
    again = json.loads(runner.invoke(app, args).stdout)
    assert first == again
    strata = {(row["koppen"], row["income"]) for row in first}
    assert strata == {
        ("BSh", "LM"),
        ("Cfb", "H"),
        ("Aw", "UM"),
        ("Csa", "H"),
        ("Aw", "LM"),
        ("BWh", "L"),
    }
    assert all(row["population_2025"] >= 600000 for row in first)


def test_stats_reports_totals_and_continents():
    result = runner.invoke(app, ["corpus", "stats", "--json"])
    assert result.exit_code == 0, result.output
    stats = json.loads(result.stdout)
    assert stats["totals"]["urban_centres"] == 9
    assert stats["totals"]["continents"] == 4
    assert stats["by_continent"][0]["continent"] == "Africa"
    assert "Africa" in runner.invoke(app, ["corpus", "stats"]).stdout


def test_search_says_which_name_matched_when_it_was_an_alias():
    rows = json.loads(runner.invoke(app, ["corpus", "search", "amdavad", "--json"]).stdout)
    assert [row["id"] for row in rows] == [6143]
    assert rows[0]["matched"] == "Amdavad"
    table = runner.invoke(app, ["corpus", "search", "amdavad"]).stdout
    assert "Amdavad" in table


def test_show_reports_how_many_tiles_are_built(tmp_path):
    tile = tmp_path / "6143" / "t43N_249_2547" / "bundle"
    tile.mkdir(parents=True)
    (tile / "provenance.json").write_text("{}")
    centre = json.loads(runner.invoke(app, ["corpus", "show", "ahmedabad", "--json"]).stdout)
    assert centre["status"] == {
        "bundle": 1,
        "baseline": 0,
        "physics": 0,
        "model": 0,
        "results": 0,
    }
    assert "1 of 365 bundle" in runner.invoke(app, ["corpus", "show", "ahmedabad"]).stdout
