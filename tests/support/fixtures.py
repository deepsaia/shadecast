"""Test doubles shared across the command line tests: an offline database and a selection."""

from __future__ import annotations

import pandas as pd

from shadecast.cities import City
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
    "continent",
)
ROWS = [
    (
        6143,
        "Ahmedabad",
        "Ahmedabad; Amdavad",
        "India",
        6,
        7898649.8,
        "Lower Middle",
        "6",
        72.6,
        23.0,
        "Asia",
    ),
    (
        5816,
        "London",
        "London",
        "United Kingdom",
        1649,
        10408332.0,
        "High income",
        "15",
        -0.1,
        51.5,
        "Europe",
    ),
    (
        9001,
        "London",
        "London",
        "Canada",
        150,
        500000.0,
        "High income",
        "25",
        -81.2,
        42.98,
        "North America",
    ),
    (
        9002,
        "San José",
        "San José",
        "Costa Rica",
        300,
        1500000.0,
        "Upper Middle",
        "3",
        -84.1,
        9.93,
        "North America",
    ),
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
        "North America",
    ),
    (
        1289,
        "Lagos",
        "Lagos; Ikeja",
        "Nigeria",
        1199,
        12846045.0,
        "Lower Middle",
        "3",
        3.3,
        6.5,
        "Africa",
    ),
    (3175, "Accra", "Accra", "Ghana", 1121, 5890466.0, "Lower Middle", "3", -0.2, 5.6, "Africa"),
    (
        4155,
        "Khartoum",
        "Khartoum",
        "Sudan",
        958,
        7114789.0,
        "Low income",
        "4",
        32.6,
        15.5,
        "Africa",
    ),
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
        "Africa",
    ),
]

TILE_ROWS = [
    {
        "id": "t43N_249_2547",
        "e_km": 249,
        "n_km": 2547,
        "population_2020": 9000.0,
        "density_2020_per_km2": 9000.0,
        "built_fraction": 0.9,
        "mean_height_m": 9.0,
    },
    {
        "id": "t43N_250_2547",
        "e_km": 250,
        "n_km": 2547,
        "population_2020": 7000.0,
        "density_2020_per_km2": 7000.0,
        "built_fraction": 0.8,
        "mean_height_m": 8.0,
    },
    {
        "id": "t43N_249_2546",
        "e_km": 249,
        "n_km": 2546,
        "population_2020": 5000.0,
        "density_2020_per_km2": 5000.0,
        "built_fraction": 0.5,
        "mean_height_m": 6.0,
    },
    {
        "id": "t43N_250_2546",
        "e_km": 250,
        "n_km": 2546,
        "population_2020": 3000.0,
        "density_2020_per_km2": 3000.0,
        "built_fraction": 0.4,
        "mean_height_m": 5.0,
    },
    {
        "id": "t43N_251_2546",
        "e_km": 251,
        "n_km": 2546,
        "population_2020": 1000.0,
        "density_2020_per_km2": 1000.0,
        "built_fraction": 0.1,
        "mean_height_m": 3.0,
    },
    {
        "id": "t43N_251_2547",
        "e_km": 251,
        "n_km": 2547,
        "population_2020": 0.0,
        "density_2020_per_km2": 0.0,
        "built_fraction": 0.0,
        "mean_height_m": 0.0,
    },
]


def fixture_centres() -> UrbanCentres:
    return UrbanCentres(pd.DataFrame(ROWS, columns=COLUMNS))


def fixture_tiles(centre: object = None) -> list[dict]:
    return [dict(row) for row in TILE_ROWS]


def fixture_corpus(entries: object = None, centres: object = None) -> dict[str, City]:
    ahmedabad = fixture_centres().by_id(6143)
    return {
        "ahmedabad": City(
            "ahmedabad",
            6143,
            ahmedabad.name,
            ahmedabad.country,
            ahmedabad.lat,
            ahmedabad.lon,
            ahmedabad.koppen,
            ahmedabad.income,
            "South Asia",
            ahmedabad.population_2025,
            ahmedabad.tiles,
        ),
        "london": City(
            "london",
            5816,
            "London",
            "United Kingdom",
            51.5,
            -0.1,
            "Cfb",
            "H",
            "Europe",
            10408332,
            1649,
            True,
        ),
    }


def fixture_provenance(key: str, tile_id: str) -> dict:
    """What a build returns, as far as the build table reads it."""
    return {
        "city": {"key": key},
        "tile": {"id": tile_id},
        "quality": {
            "tier": "A",
            "reasons": [],
            "notes": [],
            "metrics": {"built_fraction": 0.3, "canopy_gt2m": 0.1, "population": 50000.0},
        },
        "buildings": {"count": 1234},
        "met": {"design_day": "2024-05-23"},
    }
