"""Corpus and tile statistics are plain counts and quantiles over what the data says."""

from shadecast.corpus.statistics import corpus_stats, tile_stats
from shadecast.corpus.urban_centre import UrbanCentre


def _centre(*, centre_id, country, continent, koppen, income, population, area) -> UrbanCentre:
    return UrbanCentre(
        id=centre_id,
        name=f"City {centre_id}",
        names=(f"City {centre_id}",),
        slug=f"city{centre_id}",
        country=country,
        population_2025=population,
        area_km2=area,
        income=income,
        koppen_code=None,
        koppen=koppen,
        lon=0.0,
        lat=0.0,
        continent=continent,
        subregion=None,
        iso3=None,
    )


CENTRES = [
    _centre(
        centre_id=1,
        country="India",
        continent="Asia",
        koppen="BSh",
        income="LM",
        population=7_000_000,
        area=365,
    ),
    _centre(
        centre_id=2,
        country="India",
        continent="Asia",
        koppen="Aw",
        income="LM",
        population=11_000_000,
        area=1052,
    ),
    _centre(
        centre_id=3,
        country="Nigeria",
        continent="Africa",
        koppen="Aw",
        income="LM",
        population=11_000_000,
        area=1199,
    ),
    _centre(
        centre_id=4,
        country="Kenya",
        continent="Africa",
        koppen="Cfb",
        income="LM",
        population=6_000_000,
        area=598,
    ),
    _centre(
        centre_id=5,
        country="United Kingdom",
        continent="Europe",
        koppen="Cfb",
        income="H",
        population=10_000_000,
        area=1649,
    ),
    _centre(
        centre_id=6,
        country="United Kingdom",
        continent="Europe",
        koppen=None,
        income=None,
        population=600_000,
        area=8,
    ),
]


def test_corpus_totals_count_centres_tiles_people_countries_and_continents():
    totals = corpus_stats(CENTRES)["totals"]
    assert totals == {
        "urban_centres": 6,
        "tiles": 4871,
        "population_2025": 45_600_000,
        "countries": 4,
        "continents": 3,
    }


def test_corpus_stats_by_continent_are_sorted_by_centres_then_population():
    by_continent = corpus_stats(CENTRES)["by_continent"]
    assert [row["continent"] for row in by_continent] == ["Asia", "Africa", "Europe"]
    assert by_continent[0] == {
        "continent": "Asia",
        "urban_centres": 2,
        "tiles": 1417,
        "population_2025": 18_000_000,
    }


def test_corpus_stats_top_countries_are_capped_at_ten_and_sorted():
    top = corpus_stats(CENTRES)["top_countries"]
    assert [row["country"] for row in top][:2] == ["India", "United Kingdom"]
    assert len(top) <= 10


def test_corpus_stats_count_koppen_and_income_with_unknowns_named():
    stats = corpus_stats(CENTRES)
    assert stats["by_koppen"] == {"Aw": 2, "Cfb": 2, "BSh": 1, "unknown": 1}
    assert stats["by_income"] == {"L": 0, "LM": 4, "UM": 0, "H": 1, "unknown": 1}


def test_corpus_stats_size_bands_in_tiles():
    assert corpus_stats(CENTRES)["size_bands"] == {
        "1 to 10": 1,
        "11 to 100": 0,
        "101 to 1,000": 2,
        "over 1,000": 3,
    }


TILES = [
    {
        "id": "a",
        "population_2020": 90_000.0,
        "density_2020_per_km2": 90_000.0,
        "built_fraction": 0.9,
        "mean_height_m": 18.0,
    },
    {
        "id": "b",
        "population_2020": 60_000.0,
        "density_2020_per_km2": 60_000.0,
        "built_fraction": 0.5,
        "mean_height_m": 12.0,
    },
    {
        "id": "c",
        "population_2020": 12_000.0,
        "density_2020_per_km2": 12_000.0,
        "built_fraction": 0.4,
        "mean_height_m": 9.0,
    },
    {
        "id": "d",
        "population_2020": 0.0,
        "density_2020_per_km2": 0.0,
        "built_fraction": 0.0,
        "mean_height_m": 0.0,
    },
]


def test_tile_stats_count_tiles_and_people():
    stats = tile_stats(TILES)
    assert stats["tiles"] == 4
    assert stats["populated_tiles"] == 3
    assert stats["population_2020"] == 162_000.0
    assert stats["tiles_over"] == {
        "tiles with 10,000 people or more": 3,
        "tiles with 50,000 people or more": 2,
    }


def test_tile_stats_quantiles_span_min_to_max():
    quantiles = tile_stats(TILES)["quantiles"]["built_fraction"]
    assert quantiles["min"] == 0.0 and quantiles["max"] == 0.9
    assert quantiles["median"] == 0.45
    assert set(quantiles) == {"min", "p25", "median", "p75", "max"}


def test_tile_stats_of_nothing_are_zero():
    assert tile_stats([])["tiles"] == 0
