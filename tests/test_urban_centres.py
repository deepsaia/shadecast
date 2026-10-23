"""Resolving urban centres and reading their strata. No network: a nine-row fixture stands in."""

from pathlib import Path

import pandas as pd
import pytest

from shadecast.corpus import ucdb
from shadecast.corpus.legend import KOPPEN, income_code, koppen_symbol
from shadecast.corpus.slugs import assign_slugs, slugify
from shadecast.corpus.urban_centre import UrbanCentre
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
    (9004, "北京", "北京", "China", 3000, 20000000.0, "-", "21", 116.4, 39.9),
    (
        9005,
        "Dar es-Salaam",
        "Dar es-Salaam",
        "Tanzania",
        500,
        8918524.0,
        "Lower Middle",
        "-",
        39.2,
        -6.8,
    ),
    (
        9006,
        "Springfield",
        "Springfield",
        "United States",
        50,
        200000.0,
        "High income",
        "25",
        -89.6,
        39.8,
    ),
    (
        9007,
        "Springfield",
        "Springfield",
        "United States",
        40,
        150000.0,
        "High income",
        "25",
        -72.6,
        42.1,
    ),
]


def _frame() -> pd.DataFrame:
    return pd.DataFrame(ROWS, columns=COLUMNS)


def _fixture_table(cache_dir: Path) -> pd.DataFrame:
    return _frame()


def test_koppen_legend_has_thirty_classes_in_beck_order():
    assert len(KOPPEN) == 30
    assert KOPPEN[1] == "Af"
    assert KOPPEN[6] == "BSh"
    assert KOPPEN[14] == "Cfa"
    assert KOPPEN[25] == "Dfa"
    assert KOPPEN[30] == "EF"


def test_koppen_symbol_reads_codes_and_reports_missing_as_none():
    assert koppen_symbol("6") == "BSh"
    assert koppen_symbol(15) == "Cfb"
    assert koppen_symbol("-") is None
    with pytest.raises(ValueError, match="31"):
        koppen_symbol("31")


def test_income_code_maps_the_world_bank_groups():
    assert income_code("Low income") == "L"
    assert income_code("Lower Middle") == "LM"
    assert income_code("Upper Middle") == "UM"
    assert income_code("High income") == "H"
    assert income_code("-") is None
    with pytest.raises(ValueError, match="Middle earth"):
        income_code("Middle earth")


def test_slugify_strips_accents_case_and_punctuation():
    assert slugify("São Paulo") == "saopaulo"
    assert slugify("Dar es-Salaam") == "daressalaam"
    assert slugify("St. Helier") == "sthelier"
    assert slugify("北京") == ""


def test_assign_slugs_gives_the_bare_slug_to_the_most_populous_namesake():
    slugs = assign_slugs(_frame()).set_axis(_frame()["ID_UC_G0"])
    assert slugs[5816] == "london"
    assert slugs[9001] == "london-canada"
    assert slugs[9003] == "sanjose"
    assert slugs[9002] == "sanjose-costarica"
    assert slugs[9004] == "uc9004"
    assert slugs[9006] == "springfield"
    assert slugs[9007] == "springfield-unitedstates"
    assert slugs.is_unique


def test_by_id_returns_an_urban_centre_with_its_strata():
    centre = UrbanCentres(_frame()).by_id(6143)
    assert isinstance(centre, UrbanCentre)
    assert centre.name == "Ahmedabad"
    assert centre.names == ("Ahmedabad", "Amdavad")
    assert centre.slug == "ahmedabad"
    assert centre.country == "India"
    assert centre.population == 7898650
    assert centre.area_km2 == 365
    assert centre.tiles == 365
    assert centre.income == "LM"
    assert centre.koppen_code == 6
    assert centre.koppen == "BSh"
    assert centre.lat == pytest.approx(23.0192)
    assert centre.lon == pytest.approx(72.5988)
    assert centre.global_south


def test_missing_strata_are_none_not_guesses():
    centres = UrbanCentres(_frame())
    assert centres.by_id(9004).income is None
    assert centres.by_id(9005).koppen is None
    assert centres.by_id(9005).koppen_code is None
    assert not centres.by_id(9004).global_south


def test_unknown_id_is_an_error_naming_it():
    with pytest.raises(KeyError, match="4242"):
        UrbanCentres(_frame()).by_id(4242)


@pytest.mark.parametrize("text", ["6143", "ahmedabad", "AHMEDABAD", "Amdavad", "amdavad"])
def test_resolve_accepts_id_slug_and_any_known_name(text):
    assert UrbanCentres(_frame()).resolve(text).id == 6143


def test_resolve_prefers_the_exact_slug_over_a_name_search():
    centres = UrbanCentres(_frame())
    assert centres.resolve("london").id == 5816
    assert centres.resolve("london-canada").id == 9001
    assert centres.resolve("dar es salaam").id == 9005


def test_resolve_refuses_an_ambiguous_fragment_and_lists_the_candidates():
    with pytest.raises(ValueError, match=r"springfield.*springfield-unitedstates"):
        UrbanCentres(_frame()).resolve("spring")


def test_resolve_refuses_an_unknown_name():
    with pytest.raises(ValueError, match="atlantis"):
        UrbanCentres(_frame()).resolve("atlantis")


def test_search_filters_by_text_country_and_population_and_sorts_by_population():
    centres = UrbanCentres(_frame())
    assert [c.id for c in centres.search("san")] == [9003, 9002]
    assert [c.id for c in centres.search("san", min_population=1_600_000)] == [9003]
    assert [c.id for c in centres.search("london", country="Canada")] == [9001]
    assert [c.id for c in centres.search("")][:2] == [9004, 5816]


def test_load_reads_the_table_from_the_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(ucdb, "table", _fixture_table)
    centres = UrbanCentres.load(tmp_path)
    assert len(centres) == 9
    assert next(c.id for c in centres.all()) == 6143
