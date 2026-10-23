"""Moving legacy bundles and physics into the tile layout: plan first, move only on request."""

import json
from pathlib import Path

import pytest

from shadecast.cities import City
from shadecast.corpus import migrate
from shadecast.corpus.legacy_city import LegacyCity
from shadecast.corpus.tile import Tile
from shadecast.corpus.tile_paths import TilePaths

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
)


def _legacy(root: Path, *, with_physics: bool = True) -> tuple[Path, Path]:
    """A bundle under out/corpus and its physics under data/surrogate, as built before tiles."""
    bundle = root / "out" / "corpus" / "ahmedabad"
    bundle.mkdir(parents=True)
    (bundle / "provenance.json").write_text(
        json.dumps({"aoi": {"lat": 23.013954, "lon": 72.558362, "side_m": 1000, "res_m": 1.0}})
    )
    (bundle / "DEM.tif").write_bytes(b"dem")
    surrogate = root / "data" / "surrogate" / "ahmedabad"
    if with_physics:
        (surrogate / "baseline").mkdir(parents=True)
        (surrogate / "baseline" / "tmrt_daylight.npy").write_bytes(b"field")
        (surrogate / "sparse_probe_0000").mkdir()
        (surrogate / "model.pt").write_bytes(b"weights")
    return bundle, surrogate


def test_the_tile_of_a_legacy_bundle_comes_from_its_recorded_aoi(tmp_path):
    bundle, _ = _legacy(tmp_path)
    assert migrate.tile_of_bundle(bundle) == Tile(6908, 2816)


def test_plan_lists_every_move_without_touching_anything(tmp_path):
    bundle, surrogate = _legacy(tmp_path)
    plan = migrate.plan(
        LegacyCity(AHMEDABAD, bundle, surrogate),
        TilePaths(tmp_path / "tiles", 6143, Tile(6908, 2816)),
    )
    sources = [str(move.source.relative_to(tmp_path)) for move in plan]
    assert sources == ["out/corpus/ahmedabad", "data/surrogate/ahmedabad"]
    assert [move.target.name for move in plan] == ["bundle", "surrogate"]
    assert bundle.exists() and surrogate.exists()


def test_plan_for_a_bundle_without_physics_moves_only_the_bundle(tmp_path):
    bundle, surrogate = _legacy(tmp_path, with_physics=False)
    plan = migrate.plan(
        LegacyCity(AHMEDABAD, bundle, surrogate),
        TilePaths(tmp_path / "tiles", 6143, Tile(6908, 2816)),
    )
    assert [move.target.name for move in plan] == ["bundle"]


def test_apply_moves_the_directories_and_records_the_tile_in_provenance(tmp_path):
    bundle, surrogate = _legacy(tmp_path)
    paths = TilePaths(tmp_path / "tiles", 6143, Tile(6908, 2816))
    migrate.apply(migrate.plan(LegacyCity(AHMEDABAD, bundle, surrogate), paths))
    assert (paths.bundle / "DEM.tif").read_bytes() == b"dem"
    assert (paths.baseline / "tmrt_daylight.npy").read_bytes() == b"field"
    assert (paths.surrogate / "model.pt").read_bytes() == b"weights"
    assert (paths.surrogate / "sparse_probe_0000").is_dir()
    assert not bundle.exists() and not surrogate.exists()
    provenance = json.loads((paths.bundle / "provenance.json").read_text())
    assert provenance["tile"]["id"] == "t6908_2816"
    assert provenance["tile"]["bounds_mollweide"] == [6_908_000, 2_816_000, 6_909_000, 2_817_000]
    assert provenance["tile"]["urban_centre"] == 6143


def test_apply_refuses_while_a_generator_holds_the_lock(tmp_path):
    bundle, surrogate = _legacy(tmp_path)
    (surrogate / ".generating.lock").write_text("12345")
    paths = TilePaths(tmp_path / "tiles", 6143, Tile(6908, 2816))
    with pytest.raises(RuntimeError, match=r"generating\.lock"):
        migrate.apply(migrate.plan(LegacyCity(AHMEDABAD, bundle, surrogate), paths))
    assert bundle.exists()


def test_apply_refuses_to_overwrite_an_existing_target(tmp_path):
    bundle, surrogate = _legacy(tmp_path)
    paths = TilePaths(tmp_path / "tiles", 6143, Tile(6908, 2816))
    paths.bundle.mkdir(parents=True)
    with pytest.raises(FileExistsError, match="bundle"):
        migrate.apply(migrate.plan(LegacyCity(AHMEDABAD, bundle, surrogate), paths))
