"""Fetching and reading the GHS Urban Centre Database. No network: every test works on fixtures."""

import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from shadecast.corpus import ucdb

GENERAL_ROWS = [
    {
        "ID_UC_G0": 6143,
        "GC_UCN_MAI_2025": "Ahmedabad",
        "GC_UCN_LIS_2025": "Ahmedabad; Amdavad",
        "GC_CNT_GAD_2025": "India",
        "GC_UCA_KM2_2025": 365,
        "GC_POP_TOT_2025": 7898649.0,
        "GC_DEV_WIG_2025": "Lower Middle",
        "GC_PLS_SCR_2025": 0.9,
    },
    {
        "ID_UC_G0": 7277,
        "GC_UCN_MAI_2025": "São Paulo",
        "GC_UCN_LIS_2025": "São Paulo",
        "GC_CNT_GAD_2025": "Brazil",
        "GC_UCA_KM2_2025": 2161,
        "GC_POP_TOT_2025": 19485157.0,
        "GC_DEV_WIG_2025": "Upper Middle",
        "GC_PLS_SCR_2025": 0.8,
    },
    {
        "ID_UC_G0": 5816,
        "GC_UCN_MAI_2025": "London",
        "GC_UCN_LIS_2025": "London",
        "GC_CNT_GAD_2025": "United Kingdom",
        "GC_UCA_KM2_2025": 1649,
        "GC_POP_TOT_2025": 10408332.0,
        "GC_DEV_WIG_2025": "High income",
        "GC_PLS_SCR_2025": 0.7,
    },
]
CLIMATE_ROWS = [
    {
        "ID_UC_G0": 6143,
        "GC_UCN_MAI_2025": "Ahmedabad",
        "CL_KOP_CUR_2025": 6,
        "CL_B01_CUR_2010": 27.1,
    },
    {
        "ID_UC_G0": 7277,
        "GC_UCN_MAI_2025": "São Paulo",
        "CL_KOP_CUR_2025": 14,
        "CL_B01_CUR_2010": 19.0,
    },
    {"ID_UC_G0": 5816, "GC_UCN_MAI_2025": "London", "CL_KOP_CUR_2025": 15, "CL_B01_CUR_2010": 11.2},
]


def _refuse_download(theme: str, cache_dir: Path) -> Path:
    raise AssertionError(f"download of {theme} attempted although the theme is cached")


def _write_theme_csv(cache_dir: Path, theme: str, rows: list[dict], encoding: str) -> Path:
    path = ucdb.csv_path(theme, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding=encoding)
    return path


def test_archive_url_names_the_theme_release_and_version():
    url = ucdb.archive_url(ucdb.GENERAL)
    assert url.endswith(
        "/GHS_UCDB_THEME_GENERAL_CHARACTERISTICS_GLOBE_R2024A/V1-2/"
        "GHS_UCDB_THEME_GENERAL_CHARACTERISTICS_GLOBE_R2024A_V1_2.zip"
    )
    assert url.startswith("https://jeodpp.jrc.ec.europa.eu/")


def test_verify_refuses_a_corrupted_archive_and_names_it(tmp_path):
    archive = tmp_path / ucdb.archive_name(ucdb.CLIMATE)
    archive.write_bytes(b"not the archive")
    with pytest.raises(ValueError, match=ucdb.archive_name(ucdb.CLIMATE)):
        ucdb.verify(archive, ucdb.CLIMATE)


def test_theme_dir_is_offline_once_the_csv_is_extracted(tmp_path, monkeypatch):
    monkeypatch.setattr(ucdb, "download", _refuse_download)
    _write_theme_csv(tmp_path, ucdb.GENERAL, GENERAL_ROWS, "utf-8")
    assert ucdb.theme_dir(ucdb.GENERAL, tmp_path) == tmp_path / ucdb.GENERAL


def test_theme_dir_extracts_a_verified_archive_already_in_the_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(ucdb, "download", _refuse_download)
    archive = tmp_path / ucdb.archive_name(ucdb.GENERAL)
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(ucdb.csv_path(ucdb.GENERAL, tmp_path).name, "ID_UC_G0\n1\n")
    monkeypatch.setitem(ucdb.CHECKSUMS, ucdb.GENERAL, ucdb.sha256(archive))
    assert ucdb.theme_dir(ucdb.GENERAL, tmp_path) == tmp_path / ucdb.GENERAL
    assert ucdb.csv_path(ucdb.GENERAL, tmp_path).exists()


def test_read_theme_uses_the_recorded_encoding_for_each_theme(tmp_path):
    _write_theme_csv(tmp_path, ucdb.GENERAL, GENERAL_ROWS, "utf-8")
    _write_theme_csv(tmp_path, ucdb.CLIMATE, CLIMATE_ROWS, "latin-1")
    general = ucdb.read_theme(ucdb.GENERAL, tmp_path)
    climate = ucdb.read_theme(ucdb.CLIMATE, tmp_path)
    assert general["GC_UCN_MAI_2025"].tolist()[1] == "São Paulo"
    assert climate["CL_KOP_CUR_2025"].tolist() == [6, 14, 15]


def test_read_theme_keeps_only_the_fields_the_corpus_needs(tmp_path):
    _write_theme_csv(tmp_path, ucdb.GENERAL, GENERAL_ROWS, "utf-8")
    general = ucdb.read_theme(ucdb.GENERAL, tmp_path)
    assert tuple(general.columns) == ucdb.GENERAL_COLUMNS
    assert "GC_PLS_SCR_2025" not in general.columns


def test_join_pairs_the_themes_on_the_urban_centre_id():
    joined = ucdb.join(pd.DataFrame(GENERAL_ROWS), pd.DataFrame(CLIMATE_ROWS))
    assert len(joined) == 3
    assert joined.set_index("ID_UC_G0").loc[5816, "CL_KOP_CUR_2025"] == 15
    assert list(joined.columns).count("GC_UCN_MAI_2025") == 1


def test_join_refuses_a_climate_theme_missing_an_urban_centre():
    with pytest.raises(ValueError, match="7277"):
        ucdb.join(pd.DataFrame(GENERAL_ROWS), pd.DataFrame(CLIMATE_ROWS[:1] + CLIMATE_ROWS[2:]))


def test_centroids_are_reprojected_from_mollweide_to_degrees(tmp_path):
    ucdb.csv_path(ucdb.GENERAL, tmp_path).parent.mkdir(parents=True)
    ucdb.csv_path(ucdb.GENERAL, tmp_path).write_text("ID_UC_G0\n6143\n")
    points = gpd.GeoDataFrame(
        {"ID_UC_G0": [6143]}, geometry=[Point(6912192.348, 2816722.055)], crs="ESRI:54009"
    )
    points.to_file(ucdb.geopackage_path(ucdb.GENERAL, tmp_path), layer=ucdb.CENTROID_LAYER)
    frame = ucdb.centroids(tmp_path)
    assert frame.loc[0, ucdb.LON] == pytest.approx(72.58, abs=0.05)
    assert frame.loc[0, ucdb.LAT] == pytest.approx(23.02, abs=0.05)
