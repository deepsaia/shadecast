"""Continent, UN subregion and ISO3 of a point come from Natural Earth. No network."""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from shadecast.data import checksum, regions

COUNTRIES = gpd.GeoDataFrame(
    {
        "continent": ["Asia", "Africa"],
        "subregion": ["Southern Asia", "Western Africa"],
        "iso3": ["IND", "NGA"],
    },
    geometry=[box(70, 20, 80, 30), box(0, 0, 10, 10)],
    crs="EPSG:4326",
)


def _fixture_countries(cache_root=None) -> gpd.GeoDataFrame:
    return COUNTRIES


def test_regions_of_points_inside_a_country():
    found = regions.regions_of([72.6, 3.3], [23.0, 6.5], COUNTRIES)
    assert found["continent"].tolist() == ["Asia", "Africa"]
    assert found["subregion"].tolist() == ["Southern Asia", "Western Africa"]
    assert found["iso3"].tolist() == ["IND", "NGA"]


def test_a_coastal_point_just_outside_every_polygon_takes_the_nearest_country():
    found = regions.regions_of([80.5], [25.0], COUNTRIES)
    assert found["iso3"].tolist() == ["IND"]


def test_with_regions_adds_the_three_columns_to_a_table(monkeypatch):
    monkeypatch.setattr(regions, "countries", _fixture_countries)
    table = pd.DataFrame({"ID_UC_G0": [6143, 1289], "lon": [72.6, 3.3], "lat": [23.0, 6.5]})
    out = regions.with_regions(table)
    assert out["continent"].tolist() == ["Asia", "Africa"]
    assert out["iso3"].tolist() == ["IND", "NGA"]
    assert len(out) == 2


def test_checksum_refuses_a_changed_file_and_names_it(tmp_path):
    path = tmp_path / "ne_50m_admin_0_countries.zip"
    path.write_bytes(b"not the file")
    with pytest.raises(ValueError, match=r"ne_50m_admin_0_countries\.zip"):
        checksum.verify(path, "0" * 64)


def test_checksum_accepts_the_recorded_digest(tmp_path):
    path = tmp_path / "f.bin"
    path.write_bytes(b"abc")
    checksum.verify(path, checksum.sha256(path))
