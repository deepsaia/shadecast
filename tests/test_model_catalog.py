"""Every model that learned from a city's tiles is listed, per tile or pooled, oldest first."""

import json
from pathlib import Path

import pytest

from shadecast.service.missing_stage import MissingStage
from shadecast.service.model_catalog import ModelCatalog, model_created
from shadecast.service.unknown_model import UnknownModel

CENTRE = 6143
TILE = "t43N_249_2547"


def _tile_model(root: Path, name: str, created: str | None = None, weights: bool = True) -> Path:
    model = root / str(CENTRE) / TILE / "models" / name
    model.mkdir(parents=True)
    if weights:
        (model / "model.pt").write_bytes(b"w")
    if created:
        (model / "manifest.json").write_text(
            json.dumps(
                {"created": created, "metrics": {"best_skill": 0.8}, "data": {"tiles": [{}]}}
            )
        )
    return model


def _pooled_model(
    models_root: Path, name: str, created: str, centres: list[int], weights: bool = True
) -> Path:
    model = models_root / name
    model.mkdir(parents=True)
    if weights:
        (model / "model.pt").write_bytes(b"w")
    tiles = [{"urban_centre": centre} for centre in centres]
    (model / "manifest.json").write_text(json.dumps({"created": created, "data": {"tiles": tiles}}))
    return model


def test_models_come_oldest_first_across_tile_and_pooled_directories(tmp_path):
    _tile_model(tmp_path, "response-unet-ahmedabad-20261023T121739")
    _tile_model(tmp_path, "response-unet-ahmedabad-20260826T143800")
    _pooled_model(
        tmp_path / "models",
        "response-unet-ahmedabad-2tiles-20261024T090000",
        "2026-10-24T09:00:00+00:00",
        [CENTRE, CENTRE],
    )
    _pooled_model(
        tmp_path / "models",
        "response-unet-lagos-20261024T100000",
        "2026-10-24T10:00:00+00:00",
        [1289],
    )
    listed = ModelCatalog(tmp_path, tmp_path / "models").models(CENTRE)
    assert [model.id for model in listed] == [
        "response-unet-ahmedabad-20260826T143800",
        "response-unet-ahmedabad-20261023T121739",
        "response-unet-ahmedabad-2tiles-20261024T090000",
    ]
    assert [model.tile for model in listed] == [TILE, TILE, None]
    assert [model.urban_centres for model in listed] == [[CENTRE], [CENTRE], [CENTRE]]


def test_models_across_cities_list_a_pooled_model_once_with_every_centre_it_serves(tmp_path):
    _tile_model(tmp_path, "response-unet-ahmedabad-20261023T121739")
    _pooled_model(
        tmp_path / "models",
        "response-unet-ahmedabad+lagos-20261024T090000",
        "2026-10-24T09:00:00+00:00",
        [CENTRE, 1289],
    )
    listed = ModelCatalog(tmp_path, tmp_path / "models").models_across([CENTRE, 1289])
    assert [model.id for model in listed] == [
        "response-unet-ahmedabad-20261023T121739",
        "response-unet-ahmedabad+lagos-20261024T090000",
    ]
    assert listed[-1].urban_centres == [CENTRE, 1289]
    assert listed[-1].tiles_trained == 2 and listed[-1].channel == "treeshade"


def test_the_newest_and_a_named_model_are_found(tmp_path):
    _tile_model(tmp_path, "response-unet-ahmedabad-20260826T143800")
    newest = _tile_model(
        tmp_path, "response-unet-ahmedabad-20261023T121739", "2026-10-23T12:17:39+00:00"
    )
    catalog = ModelCatalog(tmp_path, tmp_path / "models")
    found = catalog.newest(CENTRE)
    assert found.id == newest.name and found.path == str(newest) and found.skill == 0.8
    assert catalog.named(CENTRE, "response-unet-ahmedabad-20260826T143800").skill is None


def test_an_unknown_name_and_a_city_without_models_are_refused(tmp_path):
    catalog = ModelCatalog(tmp_path, tmp_path / "models")
    with pytest.raises(MissingStage, match="sdc surrogate treeshade train"):
        catalog.newest(CENTRE)
    _tile_model(tmp_path, "response-unet-ahmedabad-20261023T121739")
    with pytest.raises(UnknownModel, match="nope"):
        catalog.named(CENTRE, "nope")


def test_a_pooled_model_without_weights_is_listed_not_hidden(tmp_path):
    _pooled_model(
        tmp_path / "models",
        "response-unet-ahmedabad-2tiles-20261024T090000",
        "2026-10-24T09:00:00+00:00",
        [CENTRE],
        weights=False,
    )
    [model] = ModelCatalog(tmp_path, tmp_path / "models").models(CENTRE)
    assert model.has_weights is False and model.has_manifest is True


def test_model_created_sorts_named_and_manifested_models_together(tmp_path):
    bare = tmp_path / "response-unet-ahmedabad-20261023T121739"
    bare.mkdir()
    assert model_created(bare) == "2026-10-23T12:17:39"
    with_manifest = tmp_path / "response-unet-ahmedabad-2tiles-20261024T090000"
    with_manifest.mkdir()
    (with_manifest / "manifest.json").write_text(
        json.dumps({"created": "2026-10-24T09:00:00+00:00"})
    )
    assert model_created(with_manifest) == "2026-10-24T09:00:00"
    assert model_created(bare) < model_created(with_manifest)
    odd = tmp_path / "custom"
    odd.mkdir()
    assert model_created(odd) == "custom"
