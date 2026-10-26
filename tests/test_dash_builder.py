"""The walkthrough builder packs a tile's report and its atlases; it computes no score itself."""

from support import synthetic_tile

from shadecast.dash import builder


def test_build_city_packs_the_report_and_the_atlases(tmp_path):
    tile = synthetic_tile.write_bundle(tmp_path)
    synthetic_tile.write_baseline(tile)
    synthetic_tile.write_designs(tile)
    out = tmp_path / "out"
    payload = builder.build_city("ahmedabad", tile, out)
    assert payload["city"] == "ahmedabad" and payload["name"] == "Ahmedabad"
    assert payload["provenance"]["tier"] == "A"
    assert payload["baseline"] == {"exposure": synthetic_tile.BASELINE_C, "at_risk": 512}
    assert len(payload["met"]) == 24
    assert payload["hours"]["count"] == 24 and payload["hours"]["hours"][5]["median"] == 35.0
    assert payload["context"]["count"] == 1
    assert [plan["tile"] for plan in payload["plans"]["list"]] == [0, 1, 2]
    assert payload["plans"]["cooling"]["count"] == 3 and payload["plans"]["placement"]["count"] == 3
    assert payload["physics"]["designs"] == 4
    for name in (
        "ahmedabad_hours.png",
        "ahmedabad_ctx.png",
        "ahmedabad_cool.png",
        "ahmedabad_place.png",
    ):
        assert (out / name).exists(), name


def test_build_city_of_a_tile_without_designs_has_no_plans_and_no_physics(tmp_path):
    tile = synthetic_tile.write_bundle(tmp_path)
    synthetic_tile.write_baseline(tile)
    payload = builder.build_city("ahmedabad", tile, tmp_path / "out")
    assert payload["plans"] == {"list": [], "cooling": {}, "placement": {}}
    assert payload["physics"] == {}
