"""Every model lives under one root and belongs to the cities its manifest names, oldest first."""

import json
from pathlib import Path

import pytest

from shadecast.service.missing_stage import MissingStage
from shadecast.service.model_catalog import ModelCatalog
from shadecast.service.model_catalog import model_created
from shadecast.service.unknown_model import UnknownModel

CENTRE = 6143
LAGOS = 1289
TILE = "t43N_249_2547"


def _tile(tile: str = TILE, centre: int = CENTRE) -> str:
    return f"{centre}/{tile}"


def _model(root: Path, name: str, created: str | None, tiles: list[str], weights: bool = True) -> Path:
    """A model directory; a created stamp means a manifest, and no stamp means weights alone."""
    model = root / name
    model.mkdir(parents=True)
    if weights:
        (model / "model.pt").write_bytes(b"w")
    if created:
        manifest = {"created": created, "metrics": {"best_skill": 0.8}, "data": {"tiles": tiles}}
        (model / "manifest.json").write_text(json.dumps(manifest))
    return model


def test_a_centres_models_come_oldest_first_whatever_they_learned_from(tmp_path):
    _model(tmp_path, "response-unet-ahmedabad-20261023T121739", "2026-10-23T12:17:39+00:00", [_tile()])
    _model(tmp_path, "response-unet-ahmedabad-20260826T143800", "2026-08-26T14:38:00+00:00", [_tile()])
    _model(
        tmp_path,
        "response-unet-ahmedabad-2tiles-20261024T090000",
        "2026-10-24T09:00:00+00:00",
        [_tile(), _tile("t43N_250_2547")],
    )
    _model(
        tmp_path,
        "response-unet-lagos-20261024T100000",
        "2026-10-24T10:00:00+00:00",
        [_tile("t31N_537_714", LAGOS)],
    )
    listed = ModelCatalog(tmp_path).models(CENTRE)
    assert [model.id for model in listed] == [
        "response-unet-ahmedabad-20260826T143800",
        "response-unet-ahmedabad-20261023T121739",
        "response-unet-ahmedabad-2tiles-20261024T090000",
    ]
    assert [model.tile for model in listed] == [TILE, TILE, None]
    assert [model.urban_centres for model in listed] == [[CENTRE], [CENTRE], [CENTRE]]
    assert listed[-1].tiles_trained == 2 and listed[-1].channel == "treeshade"


def test_every_model_is_listed_once_and_one_without_a_manifest_belongs_to_no_city(tmp_path):
    pooled = _model(
        tmp_path,
        "response-unet-ahmedabad+lagos-20261024T090000",
        "2026-10-24T09:00:00+00:00",
        [_tile(), _tile("t31N_537_714", LAGOS)],
    )
    bare = _model(tmp_path, "response-unet-ahmedabad-20261025T090000", None, [])
    catalog = ModelCatalog(tmp_path)
    assert [model.id for model in catalog.all_models()] == [pooled.name, bare.name]
    assert catalog.all_models()[0].urban_centres == [CENTRE, LAGOS]
    assert catalog.all_models()[1].urban_centres == [] and catalog.all_models()[1].has_manifest is False
    assert [model.id for model in catalog.models(CENTRE)] == [pooled.name]
    assert [model.id for model in catalog.models(LAGOS)] == [pooled.name]


def test_the_tiles_with_models_are_those_a_finished_model_learned_from(tmp_path):
    _model(tmp_path, "response-unet-ahmedabad-20261023T121739", "2026-10-23T12:17:39+00:00", [_tile()])
    _model(tmp_path, "response-unet-ahmedabad-20261025T090000", None, [])
    catalog = ModelCatalog(tmp_path)
    assert catalog.tiles_with_models(CENTRE) == {TILE}
    assert catalog.tiles_with_models(LAGOS) == set()


def test_the_newest_and_a_named_model_are_found(tmp_path):
    older = _model(tmp_path, "response-unet-ahmedabad-20260826T143800", "2026-08-26T14:38:00+00:00", [_tile()])
    newest = _model(tmp_path, "response-unet-ahmedabad-20261023T121739", "2026-10-23T12:17:39+00:00", [_tile()])
    catalog = ModelCatalog(tmp_path)
    found = catalog.newest(CENTRE)
    assert found.id == newest.name and found.path == str(newest) and found.skill == 0.8
    assert catalog.named(CENTRE, older.name).id == older.name


def test_an_unknown_name_and_a_city_without_models_are_refused(tmp_path):
    catalog = ModelCatalog(tmp_path)
    with pytest.raises(MissingStage, match="sdc surrogate treeshade train"):
        catalog.newest(CENTRE)
    _model(tmp_path, "response-unet-ahmedabad-20261023T121739", "2026-10-23T12:17:39+00:00", [_tile()])
    with pytest.raises(UnknownModel, match="nope"):
        catalog.named(CENTRE, "nope")


def test_a_model_without_weights_is_listed_not_hidden(tmp_path):
    _model(
        tmp_path,
        "response-unet-ahmedabad-20261024T090000",
        "2026-10-24T09:00:00+00:00",
        [_tile()],
        weights=False,
    )
    [model] = ModelCatalog(tmp_path).models(CENTRE)
    assert model.has_weights is False and model.has_manifest is True


def test_model_created_sorts_named_and_manifested_models_together(tmp_path):
    bare = tmp_path / "response-unet-ahmedabad-20261023T121739"
    bare.mkdir()
    assert model_created(bare) == "2026-10-23T12:17:39"
    with_manifest = tmp_path / "response-unet-ahmedabad-2tiles-20261024T090000"
    with_manifest.mkdir()
    (with_manifest / "manifest.json").write_text(json.dumps({"created": "2026-10-24T09:00:00+00:00"}))
    assert model_created(with_manifest) == "2026-10-24T09:00:00"
    assert model_created(bare) < model_created(with_manifest)
    odd = tmp_path / "custom"
    odd.mkdir()
    assert model_created(odd) == "custom"
